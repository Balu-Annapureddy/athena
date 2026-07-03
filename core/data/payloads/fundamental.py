"""Corporate fundamentals payload value object."""

from dataclasses import dataclass, field
from types import MappingProxyType
from core.data.payloads import IPayload
from core.domain.exceptions import DomainValidationError

@dataclass(frozen=True)
class FundamentalPayload(IPayload):
    """Immutable value object containing balance sheet, income statement, cash flow, and financial ratios.

    Backlog Item (Phase C): Replace internal dictionary mappings with strongly typed Statement value objects.
    """
    balance_sheet: dict = field(default_factory=dict)
    income_statement: dict = field(default_factory=dict)
    cash_flow: dict = field(default_factory=dict)
    ratios: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.balance_sheet, dict):
            raise DomainValidationError("balance_sheet must be a dictionary")
        if not isinstance(self.income_statement, dict):
            raise DomainValidationError("income_statement must be a dictionary")
        if not isinstance(self.cash_flow, dict):
            raise DomainValidationError("cash_flow must be a dictionary")
        if not isinstance(self.ratios, dict):
            raise DomainValidationError("ratios must be a dictionary")
        
        # Enforce nested immutability via MappingProxyType
        object.__setattr__(self, "balance_sheet", MappingProxyType(dict(self.balance_sheet)))
        object.__setattr__(self, "income_statement", MappingProxyType(dict(self.income_statement)))
        object.__setattr__(self, "cash_flow", MappingProxyType(dict(self.cash_flow)))
        object.__setattr__(self, "ratios", MappingProxyType(dict(self.ratios)))
