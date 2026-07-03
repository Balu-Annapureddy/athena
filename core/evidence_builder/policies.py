"""Threshold policies supplying configurable parameters to EvidenceCandidateRules.

Policies are deliberately decoupled from rules so that:
- Region-specific thresholds can be swapped without rewriting rules.
- Strategy-specific parameter sets (value vs growth) can coexist.
- Backtesting under different threshold assumptions is straightforward.
- Policy versions are tracked independently from rule versions.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ThresholdPolicy:
    """Base threshold policy carrying configurable numeric parameters."""
    version: str = "1.0.0"


@dataclass(frozen=True)
class FundamentalThresholdPolicy(ThresholdPolicy):
    """Threshold parameters for fundamental financial measurements."""
    min_roe: float = 0.15               # 15% minimum return on equity
    max_debt_to_equity: float = 1.0     # 1.0x maximum leverage
    min_net_margin: float = 0.10        # 10% minimum net profit margin
    min_current_ratio: float = 1.5      # 1.5x minimum current ratio
    version: str = "1.0.0"


@dataclass(frozen=True)
class PriceThresholdPolicy(ThresholdPolicy):
    """Threshold parameters for price-action measurements."""
    momentum_window_days: int = 20      # Days for moving average comparison
    volume_percentile: float = 0.75     # Volume must exceed this percentile
    min_return_threshold: float = 0.05  # 5% minimum return to flag as notable
    version: str = "1.0.0"


@dataclass(frozen=True)
class MacroThresholdPolicy(ThresholdPolicy):
    """Threshold parameters for macroeconomic measurements."""
    min_gdp_growth: float = 0.04        # 4% minimum GDP growth
    max_inflation: float = 0.06         # 6% maximum acceptable inflation
    version: str = "1.0.0"
