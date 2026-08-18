"""ValidationStatus enum — tracks whether a strategy has been backtested."""

from enum import Enum


class ValidationStatus(Enum):
    """Lifecycle validation state for a thesis, decision, or strategy in Athena.

    UNVALIDATED: Default for all rules that have not been validated against the PIT benchmark.
    RISK_ADJUSTED_VALIDATED: Proven out-of-sample risk-adjusted outperformance (Sharpe >= Benchmark * 1.05,
                             MaxDD <= Benchmark * 0.60, Trade Count >= 30, Positive Net Return).
    BACKTESTED:  Validated raw out-of-sample outperformance exceeding the benchmark total return
                 net of transaction costs and slippage with statistically meaningful trade count.
    """
    UNVALIDATED              = "UNVALIDATED"
    RISK_ADJUSTED_VALIDATED  = "RISK_ADJUSTED_VALIDATED"
    BACKTESTED               = "BACKTESTED"
