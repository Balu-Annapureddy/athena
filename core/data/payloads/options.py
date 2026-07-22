"""OptionContractPayload strongly typed payload value object."""

from dataclasses import dataclass
from core.data.payloads import IPayload


@dataclass(frozen=True)
class OptionContractPayload(IPayload):
    """Immutable payload value object for derivative option contracts."""
    strike: float
    expiry_date: str
    option_type: str  # "CE" or "PE"
    underlying: str
    open_interest: int
    change_in_open_interest: int
    implied_volatility: float
    last_price: float
    bid: float
    ask: float
    volume: int
    underlying_value: float
