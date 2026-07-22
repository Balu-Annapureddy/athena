"""Validation Campaign module enforcing multi-regime statistical significance constraints.

Requires a configurable passing ratio (defaulting to 2/3 or 0.67) and a hard trade count gate
to prevent false-positive strategy promotions.
"""

import dataclasses
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from core.domain.enums import ValidationStatus
from core.backtest.engine import BacktestEngine


@dataclass(frozen=True)
class CampaignResult:
    """Immutable representation of a ValidationCampaign evaluation outcome."""
    passed: bool
    total_trades_count: int
    min_required_trades: int
    passing_runs_count: int
    total_runs_count: int
    passing_ratio: float
    required_passing_ratio: float
    reason: str
    run_details: List[Dict[str, Any]]


class ValidationCampaign:
    """Enforces multi-ticker and multi-date-range backtest validation rules.

    The validation campaign is a deliberate, configurable quality gate:
      - A strategy must generate at least min_total_trades to prevent statistical noise.
      - A strategy must clear a configured proportion of regimes (min_passing_ratio,
        defaulting to 0.67 - meaning roughly two-thirds of tested runs) to be promoted
        to BACKTESTED. This is a design choice to ensure strategy robustness.

    DATA SOURCE REQUIREMENT (see ADR-030):
      Promotion to BACKTESTED is only meaningful when this campaign is executed against
      REAL historical market data — either live-fetched via YFinanceConnector over a
      real date range, or replayed from JSONL fixtures recorded from such a fetch and
      committed to the repository.

      Running a campaign against synthetic or procedurally generated price data
      demonstrates that the engine mechanics are correct (gates, no-lookahead,
      tie-break) but does NOT constitute evidence of real-world strategy viability.
      A campaign result of "passed" on synthetic data must NOT be used to register a
      strategy with status=ValidationStatus.BACKTESTED in StrategyRegistry.
    """


    def __init__(
        self,
        tickers: List[str],
        date_ranges: List[Tuple[str, str]],
        min_total_trades: int = 20,
        min_passing_ratio: float = 0.67,
        fixture_dir: str = "fixtures/yfinance"
    ) -> None:
        """Initialize the ValidationCampaign.

        Args:
            tickers: List of ticker symbol strings.
            date_ranges: List of (start_date, end_date) string tuples.
            min_total_trades: Minimum cumulative trades across all runs. Defaults to 20.
            min_passing_ratio: Required ratio of positive runs. Defaults to 0.67 (2/3).
            fixture_dir: Directory for offline payload replay data.
        """
        self._tickers = tickers
        self._date_ranges = date_ranges
        self._min_total_trades = min_total_trades
        self._min_passing_ratio = min_passing_ratio
        self._engine = BacktestEngine(fixture_dir=fixture_dir)

    def execute(self, strategy: Any, account_size: float, risk_percent: float = 0.01) -> CampaignResult:
        """Run the validation campaign by executing backtests over all regimes.

        Args:
            strategy: Pluggable strategy instance.
            account_size: Starting capital for each individual backtest run.
            risk_percent: Max risk per trade.

        Returns:
            A CampaignResult instance.
        """
        run_details = []
        total_trades = 0
        passing_runs = 0
        total_runs = 0

        # Execute backtest runs for every ticker and date range combination
        for ticker in self._tickers:
            for start_date, end_date in self._date_ranges:
                res = self._engine.run_backtest(
                    strategy=strategy,
                    ticker=ticker,
                    start_date=start_date,
                    end_date=end_date,
                    account_size=account_size,
                    risk_percent=risk_percent
                )
                
                metrics = res["metrics"]
                trades = res["trades"]
                
                run_trade_count = metrics.total_trades
                total_trades += run_trade_count
                total_runs += 1
                
                # A run passes if the average PnL per trade is positive
                is_passing = metrics.avg_pnl_per_trade > 0.0
                if is_passing:
                    passing_runs += 1

                run_details.append({
                    "ticker": ticker,
                    "start_date": start_date,
                    "end_date": end_date,
                    "trade_count": run_trade_count,
                    "avg_pnl_per_trade": metrics.avg_pnl_per_trade,
                    "total_return": metrics.total_return,
                    "win_rate": metrics.win_rate,
                    "is_passing": is_passing,
                    "metrics": metrics,
                })

        passing_ratio = passing_runs / total_runs if total_runs > 0 else 0.0

        # Enforce validation rules
        if total_trades < self._min_total_trades:
            passed = False
            reason = (
                f"Campaign rejected due to insufficient trade count ({total_trades} trades executed, "
                f"minimum required is {self._min_total_trades})."
            )
        elif passing_ratio < self._min_passing_ratio:
            passed = False
            reason = (
                f"Campaign rejected due to insufficient passing ratio ({passing_runs}/{total_runs} runs passed, "
                f"ratio {passing_ratio:.2f} is below the required {self._min_passing_ratio:.2f})."
            )
        else:
            passed = True
            reason = (
                f"Campaign approved. {passing_runs}/{total_runs} runs passed (ratio {passing_ratio:.2f} >= "
                f"{self._min_passing_ratio:.2f}) with {total_trades} total trades."
            )

        return CampaignResult(
            passed=passed,
            total_trades_count=total_trades,
            min_required_trades=self._min_total_trades,
            passing_runs_count=passing_runs,
            total_runs_count=total_runs,
            passing_ratio=passing_ratio,
            required_passing_ratio=self._min_passing_ratio,
            reason=reason,
            run_details=run_details
        )

    def promote_records(self, thesis_records: List[Any], decision_records: List[Any]) -> Tuple[List[Any], List[Any]]:
        """Promote thesis and decision records to BACKTESTED status.

        Args:
            thesis_records: List of ThesisRecord objects.
            decision_records: List of DecisionRecord objects.

        Returns:
            A tuple of (promoted_thesis_records, promoted_decision_records).
        """
        promoted_thesis = [
            dataclasses.replace(t, validation_status=ValidationStatus.BACKTESTED)
            for t in thesis_records
        ]
        promoted_decisions = [
            dataclasses.replace(d, validation_status=ValidationStatus.BACKTESTED)
            for d in decision_records
        ]
        return promoted_thesis, promoted_decisions
