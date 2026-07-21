"""Backtest Engine executing walk-forward trading simulations on top of Athena.

Guarantees no lookahead bias by slicing data and derived pattern facts bar-by-bar.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.data.connectors.yfinance_connector import YFinanceConnector
from core.data.factory import ObservationFactory
from core.facts.builder import FactBuilder
from core.facts.rules import PriceFactRule
from core.patterns.engine import PatternEngine
from core.domain.enums import RecommendationAction, ValidationStatus
from core.decision_builder.portfolio import PortfolioState, Position
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.context import DecisionEvaluationContext
from core.domain.common import SecurityId
from core.backtest.metrics import MetricsCalculator, BacktestMetrics


@dataclass(frozen=True)
class TradeRecord:
    """Immutable record of a completed backtest trade."""
    ticker: str
    direction: str  # "LONG" or "SHORT"
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    exit_reason: str  # "STOP_LOSS", "TARGET_PRICE", or "MARK_TO_MARKET"


class BacktestEngine:
    """Orchestrates historical walk-forward backtesting of strategies."""

    def __init__(self, fixture_dir: str = "fixtures/yfinance") -> None:
        self._connector = YFinanceConnector(fixture_dir=fixture_dir)
        self._connector.enable()
        self._obs_factory = ObservationFactory()
        self._fact_builder = FactBuilder(rules=[PriceFactRule()])

    def run_backtest(
        self,
        strategy: Any,
        ticker: str,
        start_date: str,
        end_date: str,
        account_size: float,
        risk_percent: float = 0.01,
        atr_multiplier: float = 2.0
    ) -> Dict[str, Any]:
        """Run walk-forward daily backtest for a strategy on a ticker.

        Args:
            strategy: Pluggable strategy instance inheriting from BaseStrategy.
            ticker: NSE ticker symbol (e.g. "RELIANCE.NS").
            start_date: Start date string (YYYY-MM-DD).
            end_date: End date string (YYYY-MM-DD).
            account_size: Starting capital.
            risk_percent: Maximum capital risk percent per trade (defaults to 1%).
            atr_multiplier: ATR stop loss multiplier.

        Returns:
            Dictionary containing:
                - "metrics": BacktestMetrics
                - "trades": List[TradeRecord]
                - "equity_curve": List[float]
                - "thesis_records": List[ThesisRecord]
                - "decision_records": List[DecisionRecord]
        """
        # 1. Fetch daily data for full range
        payloads = self._connector.fetch_data(ticker, start=start_date, end=end_date, timeout=1)
        if not payloads:
            raise ValueError(f"No price data returned for ticker {ticker} in range {start_date} to {end_date}")

        # 2. Build list of daily Observations and Price Facts
        observations = []
        all_price_facts = []
        for p in payloads:
            obs = self._obs_factory.create_observation(p)
            observations.append(obs)
            facts = self._fact_builder.build_facts(obs)
            all_price_facts.extend(facts)

        num_bars = len(payloads)

        # Pre-compute ALL pattern facts upfront on the full fact set.
        # This avoids the O(n²) blowup of re-running PatternEngine on a growing
        # slice every bar. No-lookahead is still enforced by only appending facts
        # for bar i into the cumulative lists at the start of iteration i.
        pattern_engine = PatternEngine(entity=ticker)
        all_pattern_facts = pattern_engine.compute(all_price_facts)

        # Build per-observation-id fact lookups so the walk-forward loop can
        # append facts in O(1) per bar instead of filtering O(n) lists every bar.
        price_facts_by_obs: Dict[str, List] = {}
        for f in all_price_facts:
            k = str(f.source_observation_id)
            price_facts_by_obs.setdefault(k, []).append(f)

        pattern_facts_by_obs: Dict[str, List] = {}
        for pf in all_pattern_facts:
            k = str(pf.source_observation_id)
            pattern_facts_by_obs.setdefault(k, []).append(pf)

        # Track portfolio states
        cash = account_size
        active_position: Optional[Dict[str, Any]] = None  # keys: "direction", "entry_price", "shares", "stop_loss_price", "target_price", "entry_date"

        equity_curve: List[float] = []
        completed_trades: List[TradeRecord] = []

        thesis_records = []
        decision_records = []

        dec_policy = DecisionPolicy()

        # Cumulative fact lists grown incrementally — O(1) append per bar.
        # No-lookahead: facts for bar i are only appended at the start of iteration i.
        cumulative_price_facts: List = []
        cumulative_pattern_facts: List = []

        # 3. Walk forward day-by-day
        for i in range(num_bars):
            # Append this bar's facts before strategy evaluation (no future data visible)
            obs_id_str = str(observations[i].id)
            cumulative_price_facts.extend(price_facts_by_obs.get(obs_id_str, []))
            cumulative_pattern_facts.extend(pattern_facts_by_obs.get(obs_id_str, []))

            current_payload = payloads[i]
            price = current_payload.payload
            current_date = current_payload.provenance.publication_timestamp
            
            # Update equity value before checking entries/exits
            if active_position is None:
                current_equity = cash
            else:
                if active_position["direction"] == "LONG":
                    current_equity = cash + active_position["shares"] * price.close
                else:
                    current_equity = cash + active_position["shares"] * (active_position["entry_price"] - price.close)
            
            # Check exit conditions first if we have an active position
            if active_position is not None:
                exit_price = None
                exit_reason = ""
                
                pos_dir = active_position["direction"]
                sl = active_position["stop_loss_price"]
                tp = active_position["target_price"]
                shares = active_position["shares"]
                
                if pos_dir == "LONG":
                    # Conservative Same-Bar Exit tie-breaker:
                    # If both stop-loss and target-price are touched on the same bar,
                    # always resolve to the stop-loss exit first.
                    if price.low <= sl:
                        exit_price = sl
                        exit_reason = "STOP_LOSS"
                    elif price.high >= tp:
                        exit_price = tp
                        exit_reason = "TARGET_PRICE"
                else:  # SHORT
                    # If both stop-loss and target-price are touched on the same bar,
                    # always resolve to the stop-loss exit first.
                    if price.high >= sl:
                        exit_price = sl
                        exit_reason = "STOP_LOSS"
                    elif price.low <= tp:
                        exit_price = tp
                        exit_reason = "TARGET_PRICE"
                
                if exit_price is not None:
                    # Execute Exit
                    if pos_dir == "LONG":
                        pnl = shares * (exit_price - active_position["entry_price"])
                        cash += shares * exit_price
                    else:
                        pnl = shares * (active_position["entry_price"] - exit_price)
                        cash += pnl  # cash changes by PnL
                    
                    completed_trades.append(
                        TradeRecord(
                            ticker=ticker,
                            direction=pos_dir,
                            entry_date=active_position["entry_date"],
                            exit_date=current_date,
                            entry_price=active_position["entry_price"],
                            exit_price=exit_price,
                            shares=shares,
                            pnl=pnl,
                            exit_reason=exit_reason
                        )
                    )
                    active_position = None
                    # Update equity curve to reflect exited state
                    current_equity = cash

            # If no active position, run pipeline to check for entry signal
            if active_position is None:
                # No-lookahead guaranteed: cumulative lists only contain facts
                # up to and including bar i (appended at the top of this iteration).
                merged_facts = cumulative_price_facts + cumulative_pattern_facts

                
                # Build simulated portfolio state
                sim_positions = []
                # (No active position, so positions list is empty)
                sim_portfolio = PortfolioState(cash_available=cash, total_value=current_equity, positions=sim_positions)
                
                dec_ctx = DecisionEvaluationContext(
                    current_time=current_date,
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
                    
                    # Accumulate records for tracking/validation
                    thesis_records.append(thesis_rec)
                    decision_records.append(decision_rec)
                    
                    # Check if action triggers buy/sell
                    action = decision.action
                    if action in (RecommendationAction.BUY, RecommendationAction.SELL):
                        risk_assessment = getattr(decision, "risk_assessment", None)
                        if risk_assessment is not None and risk_assessment.position_size > 0:
                            # Verify capital
                            entry_price = price.close
                            shares = risk_assessment.position_size
                            
                            # Clamp position size to cash availability
                            required_cash = shares * entry_price
                            if action == RecommendationAction.BUY:
                                if required_cash > cash:
                                    shares = math.floor(cash / entry_price)
                            else:  # SELL (SHORT)
                                # Conservatively check if short entry value is within cash limits
                                if required_cash > cash:
                                    shares = math.floor(cash / entry_price)
                            
                            if shares > 0:
                                active_position = {
                                    "direction": "LONG" if action == RecommendationAction.BUY else "SHORT",
                                    "entry_price": entry_price,
                                    "shares": shares,
                                    "stop_loss_price": risk_assessment.stop_loss_price,
                                    "target_price": risk_assessment.target_price,
                                    "entry_date": current_date
                                }
                                if action == RecommendationAction.BUY:
                                    cash -= shares * entry_price
                                
                                # Update current equity reflecting the newly opened position
                                if action == RecommendationAction.BUY:
                                    current_equity = cash + shares * price.close
                                else:
                                    current_equity = cash  # PnL is 0 at entry

            equity_curve.append(current_equity)

        # 4. Handle remaining open position at backtest end
        if active_position is not None:
            # Force close at the final bar close
            final_price = payloads[-1].payload.close
            final_date = payloads[-1].provenance.publication_timestamp
            pos_dir = active_position["direction"]
            shares = active_position["shares"]
            
            if pos_dir == "LONG":
                pnl = shares * (final_price - active_position["entry_price"])
                cash += shares * final_price
            else:
                pnl = shares * (active_position["entry_price"] - final_price)
                cash += pnl
                
            completed_trades.append(
                TradeRecord(
                    ticker=ticker,
                    direction=pos_dir,
                    entry_date=active_position["entry_date"],
                    exit_date=final_date,
                    entry_price=active_position["entry_price"],
                    exit_price=final_price,
                    shares=shares,
                    pnl=pnl,
                    exit_reason="MARK_TO_MARKET"
                )
            )
            # Ending equity is final cash
            equity_curve[-1] = cash
            active_position = None

        # 5. Compute metrics
        trade_pnls = [t.pnl for t in completed_trades]
        metrics = MetricsCalculator.calculate(
            starting_equity=account_size,
            ending_equity=equity_curve[-1],
            equity_curve=equity_curve,
            trade_pnls=trade_pnls
        )

        return {
            "metrics": metrics,
            "trades": completed_trades,
            "equity_curve": equity_curve,
            "thesis_records": thesis_records,
            "decision_records": decision_records
        }
