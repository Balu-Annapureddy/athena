"""Multi-Asset Shared-Capital Portfolio Backtesting Engine.

Executes synchronized bar-by-bar portfolio simulations across multiple equity tickers,
enforcing exact financial accounting, PointInTime universe validation, signal ranking,
all-or-nothing cash gating, and a 10% equity concentration cap per position.
"""

import json
import copy
import logging
import math
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Set, Tuple

from core.backtest.engine import TransactionCostModel
from core.backtest.metrics import MetricsCalculator
from core.data.connectors.yfinance_connector import YFinanceConnector
from core.data.factory import ObservationFactory
from core.domain.common import ObservationId, DomainMetadata
from core.domain.entities import Fact
from core.domain.enums import RecommendationAction, ThesisDirection
from core.domain.value_objects import Measurement
from core.facts.builder import FactBuilder
from core.facts.rules import PriceFactRule
from core.facts.taxonomy import FactType
from core.patterns.engine import PatternEngine
from core.portfolio.results import MultiAssetBacktestResult
from core.portfolio.state import PortfolioPosition, PortfolioStateSnapshot
from core.portfolio.universe import PointInTimeUniverseProvider, MissingPointInTimeUniverseDataError
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.risk.engine import RiskEngine

logger = logging.getLogger(__name__)


def _safe_float(value: Any, default: float) -> float:
    """Defensive type coercion converting value to float or returning default."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


class MultiAssetPortfolioEngine:
    """Orchestrates multi-asset portfolio simulation with shared capital."""

    def __init__(
        self,
        fixture_dir: str = "fixtures/yfinance",
        cost_model: Optional[TransactionCostModel] = None,
        pit_provider: Optional[PointInTimeUniverseProvider] = None,
        index_symbol: str = "NIFTY_500",
        strict_pit: bool = False,
    ) -> None:
        """Initialize the MultiAssetPortfolioEngine.

        Args:
            fixture_dir: Directory containing recorded JSONL YFinance market payloads.
            cost_model: Transaction cost model (defaults to IndianMarketTransactionCostModel).
            pit_provider: Optional PointInTimeUniverseProvider for survivorship-bias-free research.
            index_symbol: Index identifier for PIT queries (default NIFTY_500).
            strict_pit: If True, raises error if PIT data is missing during a historical run.
        """
        self._fixture_dir = fixture_dir
        self._cost_model = cost_model if cost_model is not None else TransactionCostModel()
        self._pit_provider = pit_provider
        self._index_symbol = index_symbol
        self._strict_pit = strict_pit
        self._connector = YFinanceConnector(fixture_dir=fixture_dir)
        self._obs_factory = ObservationFactory()
        self._fact_builder = FactBuilder(rules=[PriceFactRule()])

    def _payload_to_facts(self, payload: Any, ticker: str) -> List[Fact]:
        """Convert a ConnectorPayload or mock bar into domain Fact entities."""
        if hasattr(payload, "payload_type") and hasattr(payload, "provenance"):
            try:
                obs = self._obs_factory.create_observation(payload)
                facts = self._fact_builder.build_facts(obs)
                if facts:
                    return facts
            except Exception:
                pass

        obs_id = ObservationId.generate()
        md = DomainMetadata.create(entity_id=obs_id, source="engine", created_by="MultiAssetPortfolioEngine")
        p_load = getattr(payload, "payload", payload)

        open_val = float(getattr(p_load, "open", 0.0))
        high_val = float(getattr(p_load, "high", 0.0))
        low_val = float(getattr(p_load, "low", 0.0))
        close_val = float(getattr(p_load, "close", 0.0))
        vol_val = float(getattr(p_load, "volume", 0.0))
        tf_val = str(getattr(p_load, "timeframe", "1d"))

        source_uri = f"yfinance/{ticker}"
        now_dt = datetime.now(timezone.utc)

        meas_open = Measurement(value=open_val, units="currency", quality="VERIFIED", timestamp=now_dt, source=source_uri, confidence_score=1.0)
        meas_high = Measurement(value=high_val, units="currency", quality="VERIFIED", timestamp=now_dt, source=source_uri, confidence_score=1.0)
        meas_low = Measurement(value=low_val, units="currency", quality="VERIFIED", timestamp=now_dt, source=source_uri, confidence_score=1.0)
        meas_close = Measurement(value=close_val, units="currency", quality="VERIFIED", timestamp=now_dt, source=source_uri, confidence_score=1.0)
        meas_vol = Measurement(value=vol_val, units="shares", quality="VERIFIED", timestamp=now_dt, source=source_uri, confidence_score=1.0)
        meas_tf = Measurement(value=tf_val, units="timeframe", quality="VERIFIED", timestamp=now_dt, source=source_uri, confidence_score=1.0)

        return [
            Fact(metadata=md, source_observation_id=obs_id, name=FactType.PRICE_OPEN.value, value=meas_open, extracted_at=now_dt),
            Fact(metadata=md, source_observation_id=obs_id, name=FactType.PRICE_HIGH.value, value=meas_high, extracted_at=now_dt),
            Fact(metadata=md, source_observation_id=obs_id, name=FactType.PRICE_LOW.value, value=meas_low, extracted_at=now_dt),
            Fact(metadata=md, source_observation_id=obs_id, name=FactType.PRICE_CLOSE.value, value=meas_close, extracted_at=now_dt),
            Fact(metadata=md, source_observation_id=obs_id, name=FactType.PRICE_VOLUME.value, value=meas_vol, extracted_at=now_dt),
            Fact(metadata=md, source_observation_id=obs_id, name=FactType.PRICE_TIMEFRAME.value, value=meas_tf, extracted_at=now_dt),
        ]

    def _load_ticker_payloads(
        self, ticker: str, start_date: str, end_date: str
    ) -> List[Any]:
        """Load and filter market data payloads for a single ticker."""
        try:
            payloads = self._connector.fetch_data(ticker, start=start_date, end=end_date)
            return [p for p in payloads if start_date <= str(p.provenance.publication_timestamp)[:10] <= end_date]
        except (KeyError, ValueError, FileNotFoundError, RuntimeError, TypeError) as err:
            logger.warning("Failed loading market payloads for ticker %s: %s", ticker, err)
            return []

    def run_portfolio_backtest(
        self,
        strategy: Any,
        tickers: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 1_000_000.0,
        risk_per_trade: float = 0.01,
        max_position_equity_pct: float = 0.10,
        max_positions: int = 10,
        timeframe: str = "1d",
        require_pit: bool = False,
        allow_synthetic: bool = True,
        execution_delay_bars: int = 0,
        short_borrow_rate_annual: float = 0.0,
    ) -> MultiAssetBacktestResult:
        """Execute synchronized multi-asset shared-capital backtest.

        Args:
            strategy: Policy strategy instance.
            tickers: List of ticker symbols to evaluate.
            start_date: Backtest start date ISO string ('YYYY-MM-DD').
            end_date: Backtest end date ISO string ('YYYY-MM-DD').
            initial_capital: Starting total cash capital (e.g. ₹10,00,000).
            risk_per_trade: Risk fraction per trade (default 0.01 = 1%).
            max_position_equity_pct: Concentration cap per position (default 0.10 = 10%).
            timeframe: Bar timeframe ('1d', '1h', '15m').
            require_pit: If True, fails loudly if pit_provider is missing.
            allow_synthetic: If False, enforces PIT provider presence for historical research mode.
            execution_delay_bars: 0 = execute on signal bar T Close, 1 = execute on next bar T+1 Open.
            short_borrow_rate_annual: Annual borrowing cost rate for synthetic shorts (e.g. 0.05 = 5%).

        Returns:
            A MultiAssetBacktestResult object.
        """
        if (require_pit or not allow_synthetic) and self._pit_provider is None:
            raise MissingPointInTimeUniverseDataError(
                f"Historical research mode requires an explicit PointInTimeUniverseProvider for index '{self._index_symbol}'."
            )

        # 1. Load payloads for all tickers
        ticker_payloads: Dict[str, List[Any]] = {}
        all_timestamps: Set[str] = set()
        
        for ticker in tickers:
            p_list = self._load_ticker_payloads(ticker, start_date, end_date)
            if p_list:
                ticker_payloads[ticker] = p_list
                for p in p_list:
                    all_timestamps.add(str(p.provenance.publication_timestamp)[:10])

        sorted_timestamps = sorted(list(all_timestamps))
        if not sorted_timestamps:
            # Empty backtest
            empty_metrics = MetricsCalculator.calculate(
                starting_equity=initial_capital,
                ending_equity=initial_capital,
                equity_curve=[initial_capital],
                trade_pnls=[],
                timeframe=timeframe,
            )
            return MultiAssetBacktestResult(
                initial_capital=initial_capital,
                ending_equity=initial_capital,
                total_return=0.0,
                metrics=empty_metrics,
                equity_curve=[initial_capital],
                snapshots=[],
                trades=[],
                total_costs=0.0,
                rejected_signals_count=0,
                execution_log=[],
            )

        # Map timestamp -> ticker -> payload bar
        bar_matrix: Dict[str, Dict[str, Any]] = {ts: {} for ts in sorted_timestamps}
        # Per-ticker sorted list of all bars and pre-computed facts
        ticker_history: Dict[str, List[Any]] = {}  # ticker -> [bar0, bar1, ...] in date order
        ticker_fact_history: Dict[str, List[List[Fact]]] = {}  # ticker -> [[f1, f2, ...], ...]
        for ticker, p_list in ticker_payloads.items():
            sorted_bars = sorted(p_list, key=lambda p: str(p.provenance.publication_timestamp)[:10])
            ticker_history[ticker] = sorted_bars

            # 1. Price facts per bar
            raw_facts_per_bar = [self._payload_to_facts(b, ticker) for b in sorted_bars]
            all_price_facts = [f for b_facts in raw_facts_per_bar for f in b_facts]

            # 2. Pattern facts across all bars
            pattern_engine = PatternEngine(entity=ticker)
            all_pattern_facts = pattern_engine.compute(all_price_facts)

            pattern_facts_by_obs: Dict[str, List[Fact]] = {}
            for pf in all_pattern_facts:
                pattern_facts_by_obs.setdefault(str(pf.source_observation_id), []).append(pf)

            combined_bar_facts = []
            for b_facts in raw_facts_per_bar:
                if b_facts:
                    obs_id_str = str(b_facts[0].source_observation_id)
                    pfs = pattern_facts_by_obs.get(obs_id_str, [])
                    combined_bar_facts.append(b_facts + pfs)
                else:
                    combined_bar_facts.append([])
            ticker_fact_history[ticker] = combined_bar_facts

            for p in sorted_bars:
                ts = str(p.provenance.publication_timestamp)[:10]
                if ts in bar_matrix:
                    bar_matrix[ts][ticker] = p

        # 2. Portfolio Accounting Initialization
        cash = float(initial_capital)
        open_positions: Dict[str, PortfolioPosition] = {}  # ticker -> Position
        completed_trades: List[PortfolioPosition] = []
        equity_curve: List[float] = []
        snapshots: List[PortfolioStateSnapshot] = []
        execution_log: List[Dict[str, Any]] = []
        rejected_signals_count = 0
        total_costs_paid = 0.0
        position_counter = 1

        # Pending order queue for execution_delay_bars == 1
        pending_orders: List[Dict[str, Any]] = []

        # Historical price memory for forward-filling
        latest_prices: Dict[str, float] = {}

        # 3. Synchronized Timeline Loop
        for ts in sorted_timestamps:
            bar_dict = bar_matrix[ts]

            # Update latest price memory
            for ticker, p in bar_dict.items():
                latest_prices[ticker] = p.payload.close

            # Calculate preliminary equity before resolving pending orders/exits
            unrealized_sum = sum(p.unrealized_pnl for p in open_positions.values())
            margin_sum = sum(p.margin_reserved for p in open_positions.values())
            long_val_sum = sum(p.shares * p.current_price for p in open_positions.values() if p.direction == "LONG")
            current_equity = cash + long_val_sum + margin_sum + sum(p.unrealized_pnl for p in open_positions.values() if p.direction == "SHORT")

            # --- STEP 1: Resolve Pending Orders Scheduled for Timestamp T (execution_delay_bars == 1) ---
            if execution_delay_bars == 1 and pending_orders:
                orders_to_process = pending_orders
                pending_orders = []
                for order in orders_to_process:
                    tk = order["ticker"]
                    if tk in open_positions:
                        continue  # Position already active
                    if tk not in bar_dict:
                        continue  # Cannot execute if no bar exists on timestamp T

                    entry_p = bar_dict[tk].payload.open
                    act = order["action"]
                    is_long = (act == RecommendationAction.BUY)

                    desired_shares = order["desired_shares"]
                    entry_notional = desired_shares * entry_p

                    # Concentration Cap Check (10% equity cap): clamp, don't reject outright
                    max_allowed_notional = current_equity * max_position_equity_pct
                    if entry_notional > max_allowed_notional:
                        capped_shares = int(max_allowed_notional / entry_p)
                        if capped_shares < 1:
                            rejected_signals_count += 1
                            execution_log.append({
                                "timestamp": ts, "action": "REJECT", "ticker": tk,
                                "reason": f"Pending order: even 1 share ({entry_p:.2f}) exceeds 10% equity cap ({max_allowed_notional:.2f})"
                            })
                            continue
                        desired_shares = capped_shares
                        entry_notional = desired_shares * entry_p

                    # Cash Availability Check
                    entry_c, _xc, _tc = self._cost_model.cost_for_trade(
                        entry_value=entry_notional, exit_value=entry_notional, is_long=is_long
                    )
                    required_cash = (entry_notional + entry_c) if is_long else (entry_notional + entry_c)

                    if required_cash > cash:
                        rejected_signals_count += 1
                        execution_log.append({
                            "timestamp": ts, "action": "REJECT", "ticker": tk,
                            "reason": f"Required cash {required_cash:.2f} exceeds available cash {cash:.2f}"
                        })
                        continue

                    # Execute Pending Entry
                    total_costs_paid += entry_c
                    margin_res = entry_notional if not is_long else 0.0

                    if is_long:
                        cash -= required_cash
                    else:  # SHORT
                        cash -= (margin_res + entry_c)

                    pos = PortfolioPosition(
                        position_id=f"POS-{position_counter:04d}",
                        ticker=tk,
                        direction="LONG" if is_long else "SHORT",
                        shares=desired_shares,
                        entry_price=entry_p,
                        current_price=entry_p,
                        stop_loss_price=order.get("stop_loss_price") or order["risk_ass"].stop_loss_price,
                        target_price=order.get("target_price") or order["risk_ass"].target_price,
                        entry_timestamp=ts,
                        signal_timestamp=order["signal_ts"],
                        execution_timestamp=ts,
                        margin_reserved=margin_res,
                        entry_cost=entry_c,
                        strategy_name=getattr(strategy, "name", "Strategy"),
                    )
                    open_positions[tk] = pos
                    position_counter += 1
                    execution_log.append({
                        "timestamp": ts, "action": "ENTRY", "ticker": tk,
                        "direction": pos.direction, "shares": desired_shares, "entry_price": entry_p,
                        "signal_ts": order["signal_ts"], "exec_ts": ts
                    })

            # --- STEP 2: Mark Active Positions to Market ---
            for ticker, pos in open_positions.items():
                cur_p = bar_dict[ticker].payload.close if ticker in bar_dict else latest_prices[ticker]
                pos.current_price = cur_p
                if pos.direction == "LONG":
                    pos.unrealized_pnl = pos.shares * (cur_p - pos.entry_price)
                else:
                    pos.unrealized_pnl = pos.shares * (pos.entry_price - cur_p)

            # --- STEP 3: Deduct Short Borrowing Costs for Open Short Positions ---
            if short_borrow_rate_annual > 0.0 and open_positions:
                for pos in open_positions.values():
                    if pos.direction == "SHORT":
                        short_notional = pos.shares * pos.entry_price
                        daily_borrow_cost = short_notional * (short_borrow_rate_annual / 365.0)
                        cash -= daily_borrow_cost
                        total_costs_paid += daily_borrow_cost
                        pos.borrowing_costs_paid += daily_borrow_cost

            # Calculate total equity before processing exits
            unrealized_sum = sum(p.unrealized_pnl for p in open_positions.values())
            margin_sum = sum(p.margin_reserved for p in open_positions.values())
            long_val_sum = sum(p.shares * p.current_price for p in open_positions.values() if p.direction == "LONG")
            current_equity = cash + long_val_sum + margin_sum + sum(p.unrealized_pnl for p in open_positions.values() if p.direction == "SHORT")

            # --- STEP 4: Process Exits for Active Positions ---
            exited_tickers: List[str] = []
            for ticker, pos in open_positions.items():
                if ticker not in bar_dict:
                    continue  # Cannot exit on missing bar

                price_bar = bar_dict[ticker].payload
                exit_price = None
                exit_reason = None

                if pos.direction == "LONG":
                    if price_bar.low <= pos.stop_loss_price or price_bar.open < pos.stop_loss_price:
                        exit_reason = "STOP_LOSS"
                        exit_price = min(pos.stop_loss_price, price_bar.open)
                    elif price_bar.high >= pos.target_price:
                        exit_reason = "TARGET_PRICE"
                        exit_price = max(pos.target_price, price_bar.open)
                else:  # SHORT
                    if price_bar.high >= pos.stop_loss_price or price_bar.open > pos.stop_loss_price:
                        exit_reason = "STOP_LOSS"
                        exit_price = max(pos.stop_loss_price, price_bar.open)
                    elif price_bar.low <= pos.target_price:
                        exit_reason = "TARGET_PRICE"
                        exit_price = min(pos.target_price, price_bar.open)

                # Check for Strategy-driven Exit Signals (e.g. Death Cross, Bearish MACD, VWAP break, Trailing Stop)
                if exit_reason is None and hasattr(strategy, "evaluate"):
                    req_bars = max(1, int(_safe_float(getattr(strategy, "required_history_bars", 1), 1.0)))
                    hist = ticker_history.get(ticker, [])
                    curr_ts_idx = next(
                        (i for i, b in enumerate(hist)
                         if str(b.provenance.publication_timestamp)[:10] == ts),
                        None
                    )
                    if curr_ts_idx is not None:
                        start_idx = max(0, curr_ts_idx - req_bars + 1)
                        fact_slices = ticker_fact_history.get(ticker, [])[start_idx:curr_ts_idx + 1]
                        pos_facts = [f for b_facts in fact_slices for f in b_facts]
                    else:
                        pos_facts = self._payload_to_facts(bar_dict[ticker], ticker)

                    try:
                        eval_dt = datetime.strptime(ts, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    except Exception:
                        eval_dt = datetime.now(timezone.utc)

                    dec_ctx = DecisionEvaluationContext(
                        current_time=eval_dt,
                        active_policy=DecisionPolicy(),
                        portfolio=PortfolioState(cash_available=cash, total_value=current_equity),
                        existing_records=[],
                        target_security_id=ticker
                    )

                    try:
                        exit_eval_res = strategy.evaluate(
                            facts=pos_facts,
                            portfolio=None,
                            dec_policy=None,
                            dec_ctx=dec_ctx
                        )
                        if exit_eval_res is not None and isinstance(exit_eval_res, tuple) and len(exit_eval_res) == 4:
                            _te, t_rec, d_ent, d_rec = exit_eval_res
                            t_dir = getattr(t_rec, "thesis_direction", None)
                            d_act = getattr(d_ent, "action", None)
                            if pos.direction == "LONG" and (d_act == RecommendationAction.SELL or t_dir == ThesisDirection.BEARISH):
                                exit_reason = getattr(d_rec, "exit_reason", "STRATEGY_EXIT") or "STRATEGY_EXIT"
                                exit_price = price_bar.close
                            elif pos.direction == "SHORT" and (d_act == RecommendationAction.BUY or t_dir == ThesisDirection.BULLISH):
                                exit_reason = getattr(d_rec, "exit_reason", "STRATEGY_EXIT") or "STRATEGY_EXIT"
                                exit_price = price_bar.close
                    except Exception as err:
                        logger.debug("Strategy exit evaluation failed for %s on %s: %s", ticker, ts, err)

                if exit_reason is not None and exit_price is not None:
                    entry_notional = pos.shares * pos.entry_price
                    exit_notional = pos.shares * exit_price
                    _ec, exit_cost, total_c = self._cost_model.cost_for_trade(
                        entry_value=entry_notional,
                        exit_value=exit_notional,
                        is_long=(pos.direction == "LONG"),
                    )
                    total_costs_paid += exit_cost

                    if pos.direction == "LONG":
                        gross_pnl = pos.shares * (exit_price - pos.entry_price)
                        net_pnl = gross_pnl - (pos.entry_cost + exit_cost + pos.borrowing_costs_paid)
                        cash += exit_notional - exit_cost
                    else:  # SHORT
                        gross_pnl = pos.shares * (pos.entry_price - exit_price)
                        net_pnl = gross_pnl - (pos.entry_cost + exit_cost + pos.borrowing_costs_paid)
                        cash += pos.margin_reserved + gross_pnl - exit_cost
                        pos.margin_reserved = 0.0

                    pos.exit_timestamp = ts
                    pos.exit_price = exit_price
                    pos.exit_reason = exit_reason
                    pos.realized_pnl = net_pnl
                    pos.unrealized_pnl = 0.0

                    completed_trades.append(pos)
                    exited_tickers.append(ticker)
                    execution_log.append({
                        "timestamp": ts, "action": "EXIT", "ticker": ticker,
                        "direction": pos.direction, "exit_price": exit_price,
                        "exit_reason": exit_reason, "net_pnl": net_pnl
                    })

            for t_ex in exited_tickers:
                del open_positions[t_ex]

            # Re-calculate total equity & cash available after exits
            unrealized_sum = sum(p.unrealized_pnl for p in open_positions.values())
            margin_sum = sum(p.margin_reserved for p in open_positions.values())
            long_val_sum = sum(p.shares * p.current_price for p in open_positions.values() if p.direction == "LONG")
            current_equity = cash + long_val_sum + margin_sum + sum(p.unrealized_pnl for p in open_positions.values() if p.direction == "SHORT")

            # --- STEP 5: Collect & Rank Candidate Entry Signals ---
            candidate_signals: List[Dict[str, Any]] = []

            for ticker, p in bar_dict.items():
                if ticker in open_positions:
                    continue  # Already hold position
                if ticker in exited_tickers:
                    continue  # Exited this bar; no same-bar re-entry

                # PIT Universe Filtering Check
                if self._pit_provider is not None:
                    if not self._pit_provider.is_constituent(ticker, self._index_symbol, ts):
                        continue

                try:
                    cs_rank = None
                    cs_ret = None
                    rank_prov = getattr(strategy, "_rank_provider", None)
                    if rank_prov is not None and hasattr(rank_prov, "get_rank_and_return"):
                        try:
                            rank_res = rank_prov.get_rank_and_return(
                                ticker=ticker, date_str=ts, lookback=int(_safe_float(getattr(strategy, "lookback_period", 63), 63.0)),
                                pit_provider=self._pit_provider, index_symbol=self._index_symbol
                            )
                            if rank_res is not None and isinstance(rank_res, (tuple, list)) and len(rank_res) == 2:
                                cs_rank, cs_ret = rank_res
                        except Exception:
                            cs_rank, cs_ret = None, None

                    signal_action = None
                    signal_thesis_dir = None
                    sig_stop_loss = None
                    sig_target_price = None
                    sig_risk_ass = None
                    conf_score = _safe_float(getattr(strategy, "confidence_score", 0.8), 0.8)

                    if hasattr(strategy, "evaluate"):
                        req_bars = max(1, int(_safe_float(getattr(strategy, "required_history_bars", 1), 1.0)))
                        hist = ticker_history.get(ticker, [])
                        curr_ts_idx = next(
                            (i for i, b in enumerate(hist)
                             if str(b.provenance.publication_timestamp)[:10] == ts),
                            None
                        )
                        if curr_ts_idx is not None:
                            start_idx = max(0, curr_ts_idx - req_bars + 1)
                            fact_slices = ticker_fact_history.get(ticker, [])[start_idx:curr_ts_idx + 1]
                            history_facts = [f for b_facts in fact_slices for f in b_facts]
                        else:
                            history_facts = self._payload_to_facts(p, ticker)

                        try:
                            eval_dt = datetime.strptime(ts, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        except Exception:
                            eval_dt = datetime.now(timezone.utc)

                        dec_ctx = DecisionEvaluationContext(
                            current_time=eval_dt,
                            active_policy=DecisionPolicy(),
                            portfolio=PortfolioState(cash_available=cash, total_value=current_equity),
                            existing_records=[],
                            target_security_id=ticker
                        )

                        try:
                            eval_res = strategy.evaluate(
                                facts=history_facts,
                                portfolio=None,
                                dec_policy=None,
                                dec_ctx=dec_ctx
                            )
                            if eval_res is not None and isinstance(eval_res, tuple) and len(eval_res) == 4:
                                t_ent, t_rec, d_ent, d_rec = eval_res
                                if hasattr(d_ent, "action") and isinstance(d_ent.action, RecommendationAction):
                                    signal_action = d_ent.action
                                signal_thesis_dir = getattr(t_rec, "thesis_direction", None)
                                sig_stop_loss = getattr(d_rec, "stop_loss_price", None) or getattr(d_ent, "stop_loss_price", None)
                                sig_target_price = getattr(d_rec, "target_price", None) or getattr(d_ent, "target_price", None)
                                sig_risk_ass = getattr(d_ent, "risk_assessment", None) or getattr(d_rec, "risk_assessment", None)
                                conf_obj = getattr(d_ent, "confidence", None) or getattr(t_rec, "confidence", None)
                                if conf_obj is not None:
                                    conf_score = _safe_float(getattr(conf_obj, "score", conf_score), conf_score)
                        except (AttributeError, TypeError, ValueError, KeyError) as err:
                            logger.debug("strategy.evaluate() failed for ticker %s on %s: %s", ticker, ts, err)

                    # Only CrossSectionalMomentumStrategy falls back to rank provider if evaluate() returned None
                    if signal_action is None and cs_rank is not None and getattr(strategy, "name", "") == "CrossSectionalMomentumStrategy":
                        top_n = int(_safe_float(getattr(strategy, "top_n", 10), 10.0))
                        min_mom = _safe_float(getattr(strategy, "min_momentum_pct", 0.0), 0.0)
                        if cs_rank <= top_n and cs_ret is not None and cs_ret > min_mom:
                            signal_action = RecommendationAction.BUY
                            signal_thesis_dir = ThesisDirection.BULLISH

                    # Fall back to default_action if strategy explicitly declares one
                    if signal_action is None:
                        def_act = getattr(strategy, "default_action", None)
                        if isinstance(def_act, RecommendationAction):
                            signal_action = def_act
                            signal_thesis_dir = ThesisDirection.BULLISH
                        else:
                            continue  # No signal produced — do not trade

                    if signal_action in (RecommendationAction.BUY, RecommendationAction.SELL):
                        candidate_signals.append({
                            "ticker": ticker,
                            "price": p.payload.close,
                            "action": signal_action,
                            "thesis_dir": signal_thesis_dir,
                            "cs_rank": cs_rank if cs_rank is not None else 999999,
                            "confidence": conf_score,
                            "stop_loss_price": sig_stop_loss,
                            "target_price": sig_target_price,
                            "risk_assessment": sig_risk_ass,
                        })
                except (AttributeError, TypeError, ValueError, KeyError) as err:
                    logger.warning("Skipping candidate signal collection for %s on %s: %s", ticker, ts, err)
                    continue

            # Sort candidate signals by:
            # 1. Cross-Sectional Rank (1 is best, asc)
            # 2. Confidence Score (desc)
            # 3. Ticker symbol (deterministic alphabetical asc)
            candidate_signals.sort(key=lambda s: (s["cs_rank"], -s["confidence"], s["ticker"]))

            # --- STEP 6: Process Entry Executions or Queue Pending Orders ---
            for sig in candidate_signals:
                tk = sig["ticker"]
                entry_p = sig["price"]
                act = sig["action"]
                is_long = (act == RecommendationAction.BUY)

                if len(open_positions) >= max_positions:
                    rejected_signals_count += 1
                    execution_log.append({
                        "timestamp": ts, "action": "REJECT", "ticker": tk,
                        "reason": f"MAX_POSITIONS_REACHED: Currently holding {len(open_positions)} / {max_positions} max positions",
                        "reason_code": "MAX_POSITIONS_REACHED"
                    })
                    continue

                atr_val = entry_p * 0.02
                atr_mult = _safe_float(getattr(strategy, "atr_multiplier", 2.0), 2.0)
                _risk_decision = SimpleNamespace(action=act)
                risk_ass = sig.get("risk_assessment")
                if risk_ass is None or getattr(risk_ass, "position_size", 0) <= 0:
                    risk_ass = RiskEngine.calculate(
                        decision=_risk_decision,
                        account_size=current_equity,
                        atr_value=atr_val,
                        risk_percent=risk_per_trade,
                        entry_price=entry_p,
                        atr_multiplier=atr_mult,
                    )
                if risk_ass is None or risk_ass.position_size <= 0:
                    rejected_signals_count += 1
                    execution_log.append({
                        "timestamp": ts, "action": "REJECT", "ticker": tk,
                        "reason": "INVALID_POSITION_SIZE: RiskEngine calculated 0 shares",
                        "reason_code": "INVALID_POSITION_SIZE"
                    })
                    continue

                desired_shares = risk_ass.position_size
                entry_notional = desired_shares * entry_p

                if execution_delay_bars == 1:
                    # Queue pending order for next bar T+1 Open
                    pending_orders.append({
                        "ticker": tk,
                        "action": act,
                        "thesis_dir": sig["thesis_dir"],
                        "cs_rank": sig["cs_rank"],
                        "confidence": sig["confidence"],
                        "signal_price": entry_p,
                        "signal_ts": ts,
                        "desired_shares": desired_shares,
                        "risk_ass": risk_ass,
                        "stop_loss_price": sig.get("stop_loss_price"),
                        "target_price": sig.get("target_price"),
                    })
                else:
                    # Immediate Same-Bar Close Execution (execution_delay_bars == 0)
                    max_allowed_notional = current_equity * max_position_equity_pct
                    if entry_notional > max_allowed_notional:
                        capped_shares = int(max_allowed_notional / entry_p)
                        if capped_shares < 1:
                            rejected_signals_count += 1
                            execution_log.append({
                                "timestamp": ts, "action": "REJECT", "ticker": tk,
                                "reason": f"CONCENTRATION_LIMIT: Even 1 share ({entry_p:.2f}) exceeds 10% equity cap ({max_allowed_notional:.2f})",
                                "reason_code": "CONCENTRATION_LIMIT"
                            })
                            continue
                        desired_shares = capped_shares
                        entry_notional = desired_shares * entry_p

                    entry_c, _xc, _tc = self._cost_model.cost_for_trade(
                        entry_value=entry_notional, exit_value=entry_notional, is_long=is_long
                    )
                    required_cash = (entry_notional + entry_c) if is_long else (entry_notional + entry_c)

                    if required_cash > cash:
                        rejected_signals_count += 1
                        execution_log.append({
                            "timestamp": ts, "action": "REJECT", "ticker": tk,
                            "reason": f"INSUFFICIENT_CASH: Required cash {required_cash:.2f} exceeds available cash {cash:.2f}",
                            "reason_code": "INSUFFICIENT_CASH"
                        })
                        continue

                    total_costs_paid += entry_c
                    margin_res = entry_notional if not is_long else 0.0

                    if is_long:
                        cash -= required_cash
                    else:  # SHORT
                        cash -= (margin_res + entry_c)

                    pos_stop_loss = sig.get("stop_loss_price") or risk_ass.stop_loss_price
                    pos_target_price = sig.get("target_price") or risk_ass.target_price

                    pos = PortfolioPosition(
                        position_id=f"POS-{position_counter:04d}",
                        ticker=tk,
                        direction="LONG" if is_long else "SHORT",
                        shares=desired_shares,
                        entry_price=entry_p,
                        current_price=entry_p,
                        stop_loss_price=pos_stop_loss,
                        target_price=pos_target_price,
                        entry_timestamp=ts,
                        signal_timestamp=ts,
                        execution_timestamp=ts,
                        margin_reserved=margin_res,
                        entry_cost=entry_c,
                        strategy_name=getattr(strategy, "name", "Strategy"),
                    )
                    open_positions[tk] = pos
                    position_counter += 1
                    execution_log.append({
                        "timestamp": ts, "action": "ENTRY", "ticker": tk,
                        "direction": pos.direction, "shares": desired_shares, "entry_price": entry_p,
                        "signal_ts": ts, "exec_ts": ts
                    })

            # --- STEP 7: Portfolio State Snapshot & Equity Curve ---
            unrealized_sum = sum(p.unrealized_pnl for p in open_positions.values())
            margin_sum = sum(p.margin_reserved for p in open_positions.values())
            long_val_sum = sum(p.shares * p.current_price for p in open_positions.values() if p.direction == "LONG")
            final_ts_equity = cash + long_val_sum + margin_sum + sum(p.unrealized_pnl for p in open_positions.values() if p.direction == "SHORT")
            equity_curve.append(final_ts_equity)

            snap = PortfolioStateSnapshot(
                timestamp=ts,
                starting_capital=initial_capital,
                cash_available=cash,
                margin_reserved=margin_sum,
                realized_pnl=sum(t.realized_pnl for t in completed_trades),
                unrealized_pnl=unrealized_sum,
                total_equity=final_ts_equity,
                gross_exposure=long_val_sum + margin_sum,
                net_exposure=long_val_sum - margin_sum,
                active_positions_count=len(open_positions),
                open_positions=list(copy.copy(p) for p in open_positions.values()),
            )
            snapshots.append(snap)

        # 4. Final Mark-to-Market Exit at Backtest End for Open Positions
        if open_positions and sorted_timestamps:
            final_ts = sorted_timestamps[-1]
            for tk, pos in list(open_positions.items()):
                final_p = pos.current_price
                entry_notional = pos.shares * pos.entry_price
                exit_notional = pos.shares * final_p
                _ec, exit_cost, _tc = self._cost_model.cost_for_trade(
                    entry_value=entry_notional, exit_value=exit_notional, is_long=(pos.direction == "LONG")
                )
                total_costs_paid += exit_cost

                if pos.direction == "LONG":
                    gross_pnl = pos.shares * (final_p - pos.entry_price)
                    net_pnl = gross_pnl - (pos.entry_cost + exit_cost + pos.borrowing_costs_paid)
                    cash += exit_notional - exit_cost
                else:
                    gross_pnl = pos.shares * (pos.entry_price - final_p)
                    net_pnl = gross_pnl - (pos.entry_cost + exit_cost + pos.borrowing_costs_paid)
                    cash += pos.margin_reserved + gross_pnl - exit_cost

                pos.exit_timestamp = final_ts
                pos.exit_price = final_p
                pos.exit_reason = "MARK_TO_MARKET"
                pos.realized_pnl = net_pnl
                pos.unrealized_pnl = 0.0
                completed_trades.append(pos)

        final_equity = equity_curve[-1] if equity_curve else initial_capital
        trade_pnls = [t.realized_pnl for t in completed_trades]

        # Calculate final portfolio BacktestMetrics
        metrics = MetricsCalculator.calculate(
            starting_equity=initial_capital,
            ending_equity=final_equity,
            equity_curve=equity_curve,
            trade_pnls=trade_pnls,
            timeframe=timeframe,
        )

        return MultiAssetBacktestResult(
            initial_capital=initial_capital,
            ending_equity=final_equity,
            total_return=metrics.total_return,
            metrics=metrics,
            equity_curve=equity_curve,
            snapshots=snapshots,
            trades=completed_trades,
            total_costs=total_costs_paid,
            rejected_signals_count=rejected_signals_count,
            execution_log=execution_log,
        )
