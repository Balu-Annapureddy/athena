"""Validation Campaign module enforcing multi-regime statistical significance constraints.

Requires a configurable passing ratio (defaulting to 2/3 or 0.67) and a hard trade count gate
to prevent false-positive strategy promotions.
"""

import dataclasses
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.domain.enums import ValidationStatus
from core.backtest.engine import BacktestEngine, TransactionCostModel


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
    benchmark_return: float = 0.0
    strategy_return: float = 0.0
    excess_return: float = 0.0
    benchmark_underperformance_flag: bool = False


class ValidationCampaign:
    """Enforces multi-ticker and multi-date-range backtest validation rules.

    The validation campaign is a deliberate, configurable quality gate:
      - A strategy must generate at least min_total_trades to prevent statistical noise.
      - A strategy must clear a configured proportion of regimes (min_passing_ratio,
        defaulting to 0.67 - meaning roughly two-thirds of tested runs) to be promoted
        to BACKTESTED. This is a design choice to ensure strategy robustness.
      - Evaluates portfolio-level net returns against a passive equal-weight buy-and-hold
        benchmark over the exact same tickers and date ranges, prominently flagging
        any severe underperformance (cash drag / premature exit penalties).

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
        fixture_dir: str = "fixtures/yfinance",
        cost_model: Optional[TransactionCostModel] = None,
    ) -> None:
        """Initialize the ValidationCampaign.

        Args:
            tickers: List of ticker symbol strings.
            date_ranges: List of (start_date, end_date) string tuples.
            min_total_trades: Minimum cumulative trades across all runs. Defaults to 20.
            min_passing_ratio: Required ratio of positive runs. Defaults to 0.67 (2/3).
            fixture_dir: Directory for offline payload replay data.
            cost_model: Transaction cost model applied to every backtest run.
                        Defaults to the standard Indian-market model.
                        Pass ZERO_COST_MODEL for gross-only (legacy) runs.
        """
        self._tickers = tickers
        self._date_ranges = date_ranges
        self._min_total_trades = min_total_trades
        self._min_passing_ratio = min_passing_ratio
        self._fixture_dir = fixture_dir
        self._engine = BacktestEngine(fixture_dir=fixture_dir, cost_model=cost_model)

    def _compute_passive_benchmark(self) -> float:
        """Compute the simple equal-weight buy-and-hold benchmark return across all tickers and date ranges.

        Returns:
            The average buy-and-hold percentage return across all valid ticker/date-range combinations.
        """
        all_rets: List[float] = []
        for ticker in self._tickers:
            date_closes: Dict[str, float] = {}
            fpath = os.path.join(self._fixture_dir, f"YFinanceConnector_{ticker}.jsonl")
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        for line in f:
                            if not line.strip():
                                continue
                            d = json.loads(line).get("normalized", {})
                            dt = d.get("provenance", {}).get("publication_timestamp", "")[:10]
                            c = d.get("payload", {}).get("close")
                            if dt and c is not None:
                                date_closes[dt] = float(c)
                except Exception:
                    pass

            if not date_closes:
                try:
                    payloads = self._engine._connector.fetch_data(ticker, start="2010-01-01", end="2026-08-01")
                    for p in payloads:
                        raw = p.get("raw", {})
                        dt = raw.get("__timestamp__", "")[:10]
                        c = p.get("payload", {}).get("close")
                        if dt and c is not None:
                            date_closes[dt] = float(c)
                except Exception:
                    pass

            if not date_closes:
                continue

            sorted_dates = sorted(date_closes.keys())
            for start_date, end_date in self._date_ranges:
                sub_dates = [d for d in sorted_dates if start_date <= d <= end_date]
                if len(sub_dates) >= 2:
                    p_start = date_closes[sub_dates[0]]
                    p_end = date_closes[sub_dates[-1]]
                    if p_start > 0:
                        all_rets.append((p_end - p_start) / p_start)

        if all_rets:
            return sum(all_rets) / len(all_rets)
        return 0.0

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
        total_expected = len(self._tickers) * len(self._date_ranges)
        # Execute backtest runs for every ticker and date range combination
        for ticker in self._tickers:
            for start_date, end_date in self._date_ranges:
                total_runs += 1
                if total_expected > 5:
                    print(f"  [{total_runs}/{total_expected}] Backtesting {ticker} ({start_date} to {end_date})...", flush=True)

                try:
                    res = self._engine.run_backtest(
                        strategy=strategy,
                        ticker=ticker,
                        start_date=start_date,
                        end_date=end_date,
                        account_size=account_size,
                        risk_percent=risk_percent
                    )
                    
                    metrics       = res["metrics"]
                    gross_metrics = res.get("gross_metrics", metrics)  # gross provided by cost-aware engine
                    trades        = res["trades"]
                    total_costs   = res.get("total_costs", 0.0)

                    run_trade_count = metrics.total_trades
                    total_trades += run_trade_count

                    # Passing gate uses net-of-cost avg PnL per trade
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
                        "max_drawdown": metrics.max_drawdown,
                        "sharpe_ratio": metrics.sharpe_ratio,
                        "profit_factor": metrics.profit_factor,
                        "is_passing": is_passing,
                        "metrics": metrics,
                        "gross_metrics": gross_metrics,
                        "total_costs": total_costs,
                    })
                except Exception as err:
                    import traceback
                    tb_text = traceback.format_exc()
                    print(f"    -> ERROR backtesting {ticker} ({start_date} to {end_date}):\n{tb_text}", flush=True)
                    run_details.append({
                        "ticker": ticker,
                        "start_date": start_date,
                        "end_date": end_date,
                        "trade_count": 0,
                        "avg_pnl_per_trade": 0.0,
                        "total_return": 0.0,
                        "win_rate": 0.0,
                        "max_drawdown": 0.0,
                        "sharpe_ratio": 0.0,
                        "profit_factor": 0.0,
                        "is_passing": False,
                        "error": tb_text or str(err) or repr(err)
                    })

        passing_ratio = passing_runs / total_runs if total_runs > 0 else 0.0

        # Passive equal-weight benchmark computation & relative performance comparison
        benchmark_return = self._compute_passive_benchmark()
        strategy_return = (
            sum(d.get("total_return", 0.0) for d in run_details) / len(run_details)
            if run_details else 0.0
        )
        excess_return = strategy_return - benchmark_return

        # Flag underperformance if benchmark is positive and strategy lags by > 20pp or < 50% benchmark return
        benchmark_underperformance_flag = (
            (benchmark_return > 0.0 and excess_return < -0.20) or
            (benchmark_return > 0.10 and strategy_return < 0.5 * benchmark_return)
        )

        if total_expected > 5:
            print("=" * 85, flush=True)
            print("PASSIVE BENCHMARK RELATIVE EVALUATION:", flush=True)
            print(f"  Passive Equal-Weight Benchmark Return : {benchmark_return * 100:+.2f}%", flush=True)
            print(f"  Strategy Portfolio Net Return (Net)    : {strategy_return * 100:+.2f}%", flush=True)
            print(f"  Excess Return over Benchmark           : {excess_return * 100:+.2f}%", flush=True)
            if benchmark_underperformance_flag:
                print("  [BENCHMARK UNDERPERFORMANCE FLAG] Strategy portfolio return dramatically underperforms buy-and-hold!", flush=True)
            print("=" * 85, flush=True)

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

        if benchmark_underperformance_flag:
            reason += (
                f" [BENCHMARK FLAG: Strategy net return ({strategy_return * 100:+.1f}%) "
                f"dramatically underperforms passive buy-and-hold benchmark ({benchmark_return * 100:+.1f}%)]"
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
            run_details=run_details,
            benchmark_return=benchmark_return,
            strategy_return=strategy_return,
            excess_return=excess_return,
            benchmark_underperformance_flag=benchmark_underperformance_flag,
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
