"""ValidationStatus enum — tracks whether a strategy has been backtested."""

from enum import Enum


class ValidationStatus(Enum):
    """Lifecycle validation state for a thesis or decision produced by Athena rules.

    UNVALIDATED: Default for all rules that have not been through backtesting.
                 Every thesis and decision in the system carries this status until
                 Sprint 29 introduces the backtesting framework.
    BACKTESTED:  Set explicitly by the backtesting layer once a rule has been
                 validated against historical data. Not used until Sprint 29.
    """
    UNVALIDATED = "UNVALIDATED"
    BACKTESTED  = "BACKTESTED"
