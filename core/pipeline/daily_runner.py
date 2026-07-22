"""Daily runner executing daily strategy evaluations."""

from dataclasses import dataclass
import datetime
from datetime import timedelta
from typing import List

from core.domain.enums import RecommendationAction, ValidationStatus
from core.portfolio.registry import StrategyRegistry
from core.pipeline.signal_report import SignalReport
from core.data.connectors.yfinance_connector import YFinanceConnector
from core.data.factory import ObservationFactory
from core.facts.builder import FactBuilder
from core.facts.rules import PriceFactRule
from core.patterns.engine import PatternEngine
from core.decision_builder.portfolio import PortfolioState
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.context import DecisionEvaluationContext


@dataclass(frozen=True)
class RunnerBatchResult:
    """Dataclass encapsulating batch execution outcome and aggregate health status."""
    reports: List[SignalReport]
    total_tickers: int
    success_count: int
    failed_count: int
    is_degraded: bool


class DailySignalRunner:
    """Orchestrates daily strategy evaluation for a list of tickers and date."""

    def __init__(
        self,
        registry: StrategyRegistry,
        include_unvalidated: bool = False,
        fixture_dir: str = "fixtures/yfinance"
    ) -> None:
        self._registry = registry
        self._include_unvalidated = include_unvalidated
        self._connector = YFinanceConnector(fixture_dir=fixture_dir)
        self._connector.enable()
        self._obs_factory = ObservationFactory()
        self._fact_builder = FactBuilder(rules=[PriceFactRule()])

    def run_ticker(self, ticker: str, run_date: datetime.date) -> List[SignalReport]:
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
                existing_records=[]
            )

            # Evaluate strategy rules
            result = strategy.evaluate(
                facts=merged_facts,
                portfolio=sim_portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx
            )

            if result is not None:
                thesis, thesis_rec, decision, decision_rec = result
                action = decision.action
                entry_price = decision_rec.entry_price
                stop_loss_price = None
                target_price = None
                position_size = None
                if getattr(decision_rec, "risk_assessment", None) is not None:
                    stop_loss_price = decision_rec.risk_assessment.stop_loss_price
                    target_price = decision_rec.risk_assessment.target_price
                    position_size = decision_rec.risk_assessment.position_size

                reasoning = ""
                if decision_rec.rationale:
                    reasoning = getattr(decision_rec.rationale, "explanation", "")
                if not reasoning and thesis_rec:
                    reasoning = f"{thesis_rec.rule_name} direction: {thesis_rec.thesis_direction.value}"

                reports.append(SignalReport(
                    run_date=run_date,
                    ticker=ticker,
                    strategy_name=strategy.name,
                    action=action,
                    entry_price=entry_price,
                    stop_loss_price=stop_loss_price,
                    target_price=target_price,
                    position_size=position_size,
                    validation_status=status,
                    reasoning=reasoning
                ))
            else:
                reports.append(SignalReport(
                    run_date=run_date,
                    ticker=ticker,
                    strategy_name=strategy.name,
                    action=RecommendationAction.HOLD,
                    validation_status=status,
                    reasoning=f"No crossover signal generated at {run_date} close."
                ))

        return reports

    def run(self, tickers: List[str], run_date: datetime.date, verbose: bool = True) -> RunnerBatchResult:
        """Run daily evaluations across multiple tickers with aggregate health tracking."""
        all_reports: List[SignalReport] = []
        success_count = 0
        failed_count = 0
        total_tickers = len(tickers)

        for idx, ticker in enumerate(tickers, start=1):
            if verbose and (idx % 25 == 1 or idx == total_tickers):
                print(f"  [{idx}/{total_tickers}] Evaluating {ticker}...")
            try:
                reports = self.run_ticker(ticker, run_date)
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
