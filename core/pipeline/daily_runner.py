"""Daily runner executing daily strategy evaluations with hybrid historical + live Upstox feeds."""

import datetime
import os
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional

from core.data.connectors.upstox_connector import UpstoxConnector
from core.data.connectors.yfinance_connector import YFinanceConnector
from core.data.contract import (
    ConnectorPayload,
    PayloadType,
    Provenance,
    SourceType,
    VerificationStatus,
)
from core.data.factory import ObservationFactory
from core.data.payloads.price import PricePayload
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.domain.enums import RecommendationAction, ValidationStatus
from core.facts.builder import FactBuilder
from core.facts.rules import PriceFactRule
from core.patterns.engine import PatternEngine
from core.pipeline.signal_report import SignalReport
from core.portfolio.registry import StrategyRegistry


@dataclass(frozen=True)
class RunnerBatchResult:
    """Dataclass encapsulating batch execution outcome and aggregate health status."""
    reports: List[SignalReport]
    total_tickers: int
    success_count: int
    failed_count: int
    is_degraded: bool


class DailySignalRunner:
    """Orchestrates daily strategy evaluation for a list of tickers and date.

    Supports hybrid data streaming: uses offline/historical fixtures for long lookback
    windows (200 SMA, ADX, ATR), and live Upstox V2 quotes for today's market price.
    """

    def __init__(
        self,
        registry: StrategyRegistry,
        include_unvalidated: bool = False,
        fixture_dir: str = "fixtures/yfinance",
        use_upstox: bool = False,
        upstox_access_token: Optional[str] = None,
    ) -> None:
        self._registry = registry
        self._include_unvalidated = include_unvalidated
        self._connector = YFinanceConnector(fixture_dir=fixture_dir)
        self._connector.enable()
        self._obs_factory = ObservationFactory()
        self._fact_builder = FactBuilder(rules=[PriceFactRule()])

        self._use_upstox = use_upstox
        self._upstox_connector: Optional[UpstoxConnector] = None

        if self._use_upstox:
            token = upstox_access_token or os.environ.get("UPSTOX_ACCESS_TOKEN")
            if not token:
                raise ValueError(
                    "Upstox live market data requested, but UPSTOX_ACCESS_TOKEN environment "
                    "variable is not set. Set UPSTOX_ACCESS_TOKEN or run with use_upstox=False."
                )
            self._upstox_connector = UpstoxConnector(access_token=token)
            self._upstox_connector.enable()

    def _fetch_upstox_batch_quotes(self, tickers: List[str]) -> Dict[str, Any]:
        """Fetch live quotes for a list of NSE tickers in batches from Upstox."""
        if not self._upstox_connector:
            return {}

        # Upstox key mapping: RELIANCE.NS -> NSE_EQ|RELIANCE
        ticker_to_key = {t: f"NSE_EQ|{t.replace('.NS', '')}" for t in tickers}
        keys = list(ticker_to_key.values())
        quotes_by_ticker = {}

        # Batch in chunks of 500
        batch_size = 500
        for i in range(0, len(keys), batch_size):
            batch_keys = keys[i : i + batch_size]
            try:
                raw_quotes = self._upstox_connector.fetch_market_quotes(batch_keys)
                for t, key in ticker_to_key.items():
                    # Upstox returns keys formatted like "NSE_EQ:RELIANCE" or "NSE_EQ|RELIANCE"
                    alt_key = key.replace("|", ":")
                    if key in raw_quotes:
                        quotes_by_ticker[t] = raw_quotes[key]
                    elif alt_key in raw_quotes:
                        quotes_by_ticker[t] = raw_quotes[alt_key]
            except Exception as e:
                # Log batch failure; individual tickers will fall back to historical bar
                print(f"  [Warning] Upstox live batch fetch failed: {e}")

        return quotes_by_ticker

    def _create_live_payload(self, ticker: str, quote: Dict[str, Any], run_date: datetime.date) -> Optional[ConnectorPayload]:
        """Convert a live Upstox quote into a normalized ConnectorPayload for today."""
        ohlc = quote.get("ohlc", {})
        last_price = quote.get("last_price")
        if not last_price and not ohlc.get("close"):
            return None

        open_p = float(ohlc.get("open") or last_price)
        high_p = float(ohlc.get("high") or last_price)
        low_p = float(ohlc.get("low") or last_price)
        close_p = float(last_price or ohlc.get("close"))
        vol_p = float(quote.get("volume") or 0.0)

        pub_dt = datetime.datetime.combine(run_date, datetime.time(15, 30), tzinfo=datetime.timezone.utc)

        prov = Provenance(
            connector_name="UpstoxConnector",
            provider="UpstoxV2",
            retrieval_timestamp=datetime.datetime.now(datetime.timezone.utc),
            publication_timestamp=pub_dt,
            raw_source_id=f"UPSTOX_LIVE:{ticker}:{run_date.isoformat()}",
            checksum="upstox_live_feed",
            connector_version="1.0.0",
            ingestion_run_id=f"run-daily-{uuid.uuid4().hex[:8]}",
        )

        price_payload = PricePayload(
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=vol_p,
            timeframe="1D",
        )

        return ConnectorPayload(
            source_id=f"UPSTOX_LIVE_{ticker}",
            entity=ticker,
            payload_type=PayloadType.PRICE,
            payload=price_payload,
            source_type=SourceType.BROKER,
            verification=VerificationStatus.VERIFIED,
            provenance=prov,
        )

    def run_ticker(
        self,
        ticker: str,
        run_date: datetime.date,
        live_quote: Optional[Dict[str, Any]] = None,
    ) -> List[SignalReport]:
        """Run daily evaluations for a single ticker on the target date."""
        reports = []
        active_strategies = self._registry.get_active_strategies()

        for strategy, status, weight in active_strategies:
            if status == ValidationStatus.UNVALIDATED and not self._include_unvalidated:
                continue

            # Calculate lookback window
            start_date_dt = run_date - timedelta(days=strategy.required_lookback_days)
            start_date_str = start_date_dt.isoformat()
            end_date_str = run_date.isoformat()

            # Fetch trailing daily OHLCV
            payloads = self._connector.fetch_data(ticker, start=start_date_str, end=end_date_str, timeout=1)

            # If live quote is provided, append/replace today's live bar
            if live_quote:
                live_payload = self._create_live_payload(ticker, live_quote, run_date)
                if live_payload:
                    if payloads:
                        last_ts = str(payloads[-1].provenance.publication_timestamp)[:10]
                        if last_ts == run_date.isoformat():
                            payloads[-1] = live_payload
                        else:
                            payloads.append(live_payload)
                    else:
                        payloads = [live_payload]

            if len(payloads) < strategy.required_history_bars:
                raise ValueError(
                    f"Insufficient history for {ticker} under {strategy.name}: "
                    f"got {len(payloads)} bars, required {strategy.required_history_bars}"
                )

            # Build observations and facts
            observations = []
            all_price_facts = []
            for p in payloads:
                obs = self._obs_factory.create_observation(p)
                observations.append(obs)
                facts = self._fact_builder.build_facts(obs)
                all_price_facts.extend(facts)

            # Compute pattern facts
            pattern_engine = PatternEngine(entity=ticker)
            all_pattern_facts = pattern_engine.compute(all_price_facts)

            merged_facts = all_price_facts + all_pattern_facts

            # Portfolio state & context
            sim_portfolio = PortfolioState(cash_available=1_000_000.0, total_value=1_000_000.0, positions=[])
            dec_policy = DecisionPolicy()
            last_date = payloads[-1].provenance.publication_timestamp
            dec_ctx = DecisionEvaluationContext(
                current_time=last_date,
                active_policy=dec_policy,
                portfolio=sim_portfolio,
                existing_records=[],
                target_security_id=ticker,
            )

            # Evaluate strategy rules
            result = strategy.evaluate(
                facts=merged_facts,
                portfolio=sim_portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
            )

            if result is not None:
                thesis, thesis_rec, decision, decision_rec = result
                action = decision.action
                entry_price = decision_rec.entry_price
                stop_loss_price = None
                target_price = None
                position_size = None
                reward_to_risk = None
                risk_ass = getattr(decision_rec, "risk_assessment", None)
                if risk_ass is not None:
                    stop_loss_price = risk_ass.stop_loss_price
                    target_price = risk_ass.target_price
                    position_size = risk_ass.position_size
                    reward_to_risk = risk_ass.reward_to_risk_ratio

                reasoning = ""
                if decision_rec.rationale:
                    reasoning = getattr(decision_rec.rationale, "explanation", "")
                if not reasoning and thesis_rec:
                    reasoning = f"{thesis_rec.rule_name} direction: {thesis_rec.thesis_direction.value}"

                if status == ValidationStatus.BACKTESTED:
                    base_score = 50.0
                elif status == ValidationStatus.RISK_ADJUSTED_VALIDATED:
                    base_score = 40.0
                else:
                    base_score = 25.0
                rr_boost = 0.0
                if reward_to_risk is not None:
                    if reward_to_risk >= 3.0:
                        rr_boost = 20.0
                    elif reward_to_risk >= 2.0:
                        rr_boost = 10.0

                pattern_boost = 15.0 if len(all_pattern_facts) > 0 else 0.0
                trend_boost = 10.0

                confidence = min(95.0, base_score + rr_boost + pattern_boost + trend_boost)
                if confidence >= 70.0:
                    quality = "HIGH"
                elif confidence >= 50.0:
                    quality = "MEDIUM"
                else:
                    quality = "LOW"

                reports.append(
                    SignalReport(
                        run_date=run_date,
                        ticker=ticker,
                        strategy_name=strategy.name,
                        action=action,
                        entry_price=entry_price,
                        stop_loss_price=stop_loss_price,
                        target_price=target_price,
                        position_size=position_size,
                        validation_status=status,
                        reasoning=reasoning,
                        confidence_score=confidence,
                        reward_to_risk=reward_to_risk,
                        signal_quality=quality,
                    )
                )
            else:
                reports.append(
                    SignalReport(
                        run_date=run_date,
                        ticker=ticker,
                        strategy_name=strategy.name,
                        action=RecommendationAction.HOLD,
                        validation_status=status,
                        reasoning=f"No crossover signal generated at {run_date} close.",
                    )
                )

        return reports

    def run(self, tickers: List[str], run_date: datetime.date, verbose: bool = True) -> RunnerBatchResult:
        """Run daily evaluations across multiple tickers with aggregate health tracking."""
        all_reports: List[SignalReport] = []
        success_count = 0
        failed_count = 0
        total_tickers = len(tickers)

        # Pre-fetch live quotes from Upstox if enabled
        live_quotes: Dict[str, Any] = {}
        if self._use_upstox and self._upstox_connector:
            if verbose:
                print(f"Fetching live Upstox quotes for {len(tickers)} tickers in batch...")
            live_quotes = self._fetch_upstox_batch_quotes(tickers)
            if verbose:
                print(f"  Received live quotes for {len(live_quotes)} tickers.")

        for idx, ticker in enumerate(tickers, start=1):
            if verbose and (idx % 25 == 1 or idx == total_tickers):
                print(f"  [{idx}/{total_tickers}] Evaluating {ticker}...")
            try:
                t_quote = live_quotes.get(ticker)
                reports = self.run_ticker(ticker, run_date, live_quote=t_quote)
                all_reports.extend(reports)
                success_count += 1
            except Exception as e:
                failed_count += 1
                if verbose:
                    print(f"  [ERROR {idx}/{total_tickers}] {ticker}: {e}")

        fail_ratio = (failed_count / total_tickers) if total_tickers > 0 else 0.0
        is_degraded = fail_ratio > 0.20

        return RunnerBatchResult(
            reports=all_reports,
            total_tickers=total_tickers,
            success_count=success_count,
            failed_count=failed_count,
            is_degraded=is_degraded,
        )
