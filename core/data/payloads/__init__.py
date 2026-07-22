"""Athena strongly typed payload Value Objects.

"Build abstractions first. Implement behavior second."
"""

from abc import ABC

class IPayload(ABC):
    """Marker interface for all strongly typed connector payload value objects."""
    pass

from core.data.payloads.price import PricePayload
from core.data.payloads.fundamental import FundamentalPayload
from core.data.payloads.news import NewsPayload
from core.data.payloads.economic import EconomicPayload
from core.data.payloads.options import OptionContractPayload

__all__ = [
    "IPayload",
    "PricePayload",
    "FundamentalPayload",
    "NewsPayload",
    "EconomicPayload",
    "OptionContractPayload",
]
