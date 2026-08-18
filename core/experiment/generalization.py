"""Cross-Sectional Universe Generalization Experiment Framework for Athena.

Executes formal 3-stage cross-sectional universe generalization evaluation:
Development Universe (NIFTY 50) -> Unseen Generalization Universe (NIFTY 100) -> Broader Universe (NIFTY 500).

Strictly enforces Point-In-Time survivorship safety, capital isolation, execution timing,
and explicit partitioning of development vs. unseen tickers.
"""

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.backtest.metrics import BacktestMetrics
from core.backtest.validation import PortfolioResearchConfig
from core.backtest.walk_forward import WalkForwardWindow
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.universe import (
    MissingPointInTimeUniverseDataError,
    PointInTimeUniverseProvider,
)


@dataclass(frozen=True)
class UniversePartition:
    """Explicitly partitions tickers into development, overlapping, and unseen subsets."""
    dev_universe_name: str
    target_universe_name: str
    dev_tickers: List[str]
    target_tickers: List[str]
    overlapping_tickers: List[str]
    unseen_tickers: List[str]
    unseen_percentage: float

    @classmethod
    def partition(cls, dev_name: str, target_name: str, dev_tickers: List[str], target_tickers: List[str]) -> "UniversePartition":
        dev_set = set(dev_tickers)
        target_set = set(target_tickers)
        overlap = sorted(list(dev_set.intersection(target_set)))
        unseen = sorted(list(target_set - dev_set))
        pct = (len(unseen) / len(target_tickers) * 100.0) if target_tickers else 0.0

        return cls(
            dev_universe_name=dev_name,
            target_universe_name=target_name,
            dev_tickers=sorted(dev_tickers),
            target_tickers=sorted(target_tickers),
            overlapping_tickers=overlap,
            unseen_tickers=unseen,
            unseen_percentage=pct,
        )


@dataclass(frozen=True)
class GeneralizationStepResult:
    """Out-of-sample portfolio evaluation metrics for a single generalization stage."""
    universe_name: str
    tickers_evaluated: List[str]
    is_unseen_subset: bool
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    total_trades: int
    total_costs: float
    rejected_signals_count: int
    metrics: BacktestMetrics
    equity_curve: List[float]


@dataclass(frozen=True)
class GeneralizationExperimentReport:
    """Structured report capturing NIFTY 50 -> NIFTY 100 -> NIFTY 500 generalization results."""
    strategy_name: str
    strategy_config: Dict[str, Any]
    research_config: Dict[str, Any]
    dev_nifty50_result: GeneralizationStepResult
    gen_nifty100_unseen_result: GeneralizationStepResult
    gen_nifty500_unseen_result: GeneralizationStepResult
    nifty100_partition: UniversePartition
    nifty500_partition: UniversePartition
    is_pit_real: bool
    pit_provider_present: bool
    data_limitation_warning: Optional[str]
    reproducibility_hash: str


class CrossSectionalGeneralizationExperiment:
    """Orchestrates the 3-stage cross-sectional universe generalization experiment."""

    def __init__(
        self,
        strategy: Any,
        nifty50_tickers: List[str],
        nifty100_tickers: List[str],
        nifty500_tickers: List[str],
        research_config: Optional[PortfolioResearchConfig] = None,
        pit_provider: Optional[PointInTimeUniverseProvider] = None,
        fixture_dir: str = "fixtures/yfinance",
    ) -> None:
        """Initialize the experiment runner.

        Args:
            strategy: Pluggable CrossSectionalMomentumStrategy policy object.
            nifty50_tickers: Development universe tickers.
            nifty100_tickers: Nifty 100 universe tickers.
            nifty500_tickers: Nifty 500 universe tickers.
            research_config: Optional PortfolioResearchConfig instance.
            pit_provider: Optional PointInTimeUniverseProvider.
            fixture_dir: Replay payload directory.
        """
        self._strategy = strategy
        self._nifty50_tickers = nifty50_tickers
        self._nifty100_tickers = nifty100_tickers
        self._nifty500_tickers = nifty500_tickers
        self._config = research_config if research_config is not None else PortfolioResearchConfig()
        self._pit_provider = pit_provider
        self._fixture_dir = fixture_dir

        # Partition universes explicitly
        self._partition_100 = UniversePartition.partition(
            "NIFTY_50", "NIFTY_100", self._nifty50_tickers, self._nifty100_tickers
        )
        self._partition_500 = UniversePartition.partition(
            "NIFTY_50", "NIFTY_500", self._nifty50_tickers, self._nifty500_tickers
        )

    def execute_experiment(
        self,
        start_date: str,
        end_date: str,
        walk_forward_windows: Optional[List[WalkForwardWindow]] = None,
    ) -> GeneralizationExperimentReport:
        """Run the formal 3-stage generalization experiment.

        Args:
            start_date: Backtest start ISO string ('YYYY-MM-DD').
            end_date: Backtest end ISO string ('YYYY-MM-DD').
            walk_forward_windows: Optional WalkForwardWindow list for walk-forward evaluation.

        Returns:
            A GeneralizationExperimentReport object.
        """
        # Audit PIT requirement
        data_limitation_warning = None
        if self._config.require_pit and self._pit_provider is None:
            raise MissingPointInTimeUniverseDataError(
                "Cross-Sectional Generalization Experiment requires an explicit PointInTimeUniverseProvider when require_pit=True."
            )

        if self._config.require_pit and not self._config.allow_synthetic:
            if self._pit_provider is not None and getattr(self._pit_provider, "dataset_status", "") != "PRODUCTION_VALIDATED":
                from core.portfolio.universe import UnvalidatedPointInTimeDatasetError
                raise UnvalidatedPointInTimeDatasetError(
                    f"Production quantitative research mode (require_pit=True, allow_synthetic=False) refused! "
                    f"The attached PointInTimeUniverseProvider dataset status is '{getattr(self._pit_provider, 'dataset_status', 'UNKNOWN')}'. "
                    f"Production historical research claims require a PRODUCTION_VALIDATED dataset with complete index coverage."
                )

        if self._pit_provider is None or getattr(self._pit_provider, "dataset_status", "") != "PRODUCTION_VALIDATED":
            data_limitation_warning = (
                "WARNING [RESEARCH INTEGRITY]: Real historical Point-In-Time constituent datasets for NIFTY 50/100/500 "
                "are unavailable or only partial in the local repository. Evaluation executed in synthetic/fixture test mode. "
                "Real-world survivorship-free generalization claims remain blocked until production PIT data is ingested."
            )

        p_engine = MultiAssetPortfolioEngine(
            fixture_dir=self._fixture_dir,
            pit_provider=self._pit_provider,
            index_symbol=self._config.index_symbol,
            strict_pit=self._config.require_pit,
        )

        def _run_stage(universe_name: str, tickers: List[str], is_unseen: bool) -> GeneralizationStepResult:
            if not tickers:
                # Empty fallback
                empty_metrics = BacktestMetrics(
                    total_trades=0, winning_trades=0, losing_trades=0, win_rate=0.0,
                    avg_pnl_per_trade=0.0, avg_win=0.0, avg_loss=0.0, total_return=0.0, max_drawdown=0.0,
                    sharpe_ratio=0.0, profit_factor=0.0
                )
                return GeneralizationStepResult(
                    universe_name=universe_name, tickers_evaluated=[], is_unseen_subset=is_unseen,
                    total_return=0.0, max_drawdown=0.0, sharpe_ratio=0.0, total_trades=0,
                    total_costs=0.0, rejected_signals_count=0, metrics=empty_metrics, equity_curve=[self._config.initial_capital]
                )

            res = p_engine.run_portfolio_backtest(
                strategy=self._strategy,
                tickers=tickers,
                start_date=start_date,
                end_date=end_date,
                initial_capital=self._config.initial_capital,
                risk_per_trade=self._config.risk_per_trade,
                max_position_equity_pct=self._config.max_position_equity_pct,
                max_positions=self._config.max_positions,
                timeframe=self._config.timeframe,
                require_pit=self._config.require_pit,
                allow_synthetic=self._config.allow_synthetic,
                execution_delay_bars=self._config.execution_delay_bars,
                short_borrow_rate_annual=self._config.short_borrow_rate_annual,
            )

            return GeneralizationStepResult(
                universe_name=universe_name,
                tickers_evaluated=tickers,
                is_unseen_subset=is_unseen,
                total_return=res.total_return,
                max_drawdown=res.metrics.max_drawdown,
                sharpe_ratio=res.metrics.sharpe_ratio,
                total_trades=len(res.trades),
                total_costs=res.total_costs,
                rejected_signals_count=res.rejected_signals_count,
                metrics=res.metrics,
                equity_curve=res.equity_curve,
            )

        # Stage 1: Development Universe (NIFTY 50)
        step1_res = _run_stage("NIFTY_50_DEV", self._nifty50_tickers, is_unseen=False)

        # Stage 2: Unseen NIFTY 100 Universe
        step2_res = _run_stage("NIFTY_100_UNSEEN", self._partition_100.unseen_tickers, is_unseen=True)

        # Stage 3: Unseen NIFTY 500 Universe
        step3_res = _run_stage("NIFTY_500_UNSEEN", self._partition_500.unseen_tickers, is_unseen=True)

        # Compute deterministic reproducibility hash using structured, explicitly-typed inputs
        strat_class_name = type(self._strategy).__name__
        raw_payload = (
            f"{strat_class_name}_{start_date}_{end_date}_"
            f"{step1_res.total_return:.6f}_{step2_res.total_return:.6f}_{step3_res.total_return:.6f}_"
            f"{step1_res.total_trades}_{step2_res.total_trades}_{step3_res.total_trades}"
        )
        reproducibility_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

        strat_display_name = getattr(self._strategy, "name", strat_class_name)
        if not isinstance(strat_display_name, str):
            strat_display_name = strat_class_name

        return GeneralizationExperimentReport(
            strategy_name=strat_display_name,
            strategy_config={
                "lookback_period": getattr(self._strategy, "_lookback_period", 63),
                "top_n": getattr(self._strategy, "_top_n", 10),
                "atr_multiplier": getattr(self._strategy, "_atr_multiplier", 2.0),
            },
            research_config=self._config.to_dict(),
            dev_nifty50_result=step1_res,
            gen_nifty100_unseen_result=step2_res,
            gen_nifty500_unseen_result=step3_res,
            nifty100_partition=self._partition_100,
            nifty500_partition=self._partition_500,
            is_pit_real=(self._pit_provider is not None),
            pit_provider_present=(self._pit_provider is not None),
            data_limitation_warning=data_limitation_warning,
            reproducibility_hash=reproducibility_hash,
        )
