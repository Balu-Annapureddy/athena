"""Risk Engine calculating position sizing, stop-loss, and risk/reward parameters."""

import math
from dataclasses import dataclass
from typing import Optional

from core.domain.enums import RecommendationAction

# This is a configurable default choice for the target price calculation, NOT an established
# professional consensus standard. It is distinct from the well-supported 1:2 minimum reward-to-risk
# threshold used for flagging high-risk trades.
DEFAULT_TARGET_REWARD_RISK_RATIO: float = 3.0


@dataclass(frozen=True)
class RiskAssessment:
    """Immutable record of the calculated risk profile for a Decision candidate."""
    position_size: int
    stop_loss_price: float
    risk_per_share: float
    total_risk_amount: float
    reward_to_risk_ratio: float
    is_ratio_flagged: bool
    entry_price: float
    target_price: float


class RiskEngine:
    """Calculates risk parameters, enforcing regulatory and professional limits.

    Conventions:
      - Position sizing: shares = floor((account_size * risk_percent) / risk_per_share).
      - ATR-based stop-loss: stop_loss = entry_price - (ATR * multiplier) for longs,
        and entry_price + (ATR * multiplier) for shorts.
      - Minimum reward:risk ratio: 1:2 (reward_to_risk_ratio >= 2.0). Flagged if below.
    """

    @staticmethod
    def calculate(
        decision,
        account_size: Optional[float],
        atr_value: Optional[float],
        risk_percent: float = 0.01,
        entry_price: Optional[float] = None,
        target_price: Optional[float] = None,
        atr_multiplier: float = 2.0
    ) -> Optional[RiskAssessment]:
        """Assess and calculate the risk profile for the given decision candidate.

        Args:
            decision: The candidate Decision or DecisionRecord entity.
            account_size: The total account capital size (required, no default).
            atr_value: The Average True Range indicator value (required).
            risk_percent: Maximum capital risk percent per trade, professional range 1-2%, capped at 2%.
            entry_price: The entry execution price (optional, resolved from decision if None).
            target_price: Potential exit target price (optional, resolved from decision or defaulted if None).
            atr_multiplier: ATR multiplier for stop-loss buffer, default 2.0.

        Returns:
            A RiskAssessment object if calculations succeed, or None if input parameters
            are missing/invalid.
        """
        # Refuse to size position if account_size is missing, <= 0, or invalid
        if account_size is None or account_size <= 0.0:
            return None

        # Refuse to calculate if other required inputs are missing/invalid
        if atr_value is None or atr_value <= 0.0:
            return None

        # Resolve entry_price from decision properties if not explicitly provided
        if entry_price is None:
            entry_price = getattr(decision, "entry_price", None)
            if entry_price is None and hasattr(decision, "execution_parameters"):
                entry_price = decision.execution_parameters.get("entry_price")

        if entry_price is None or entry_price <= 0.0:
            return None

        # Resolve target_price from decision properties if not explicitly provided
        if target_price is None:
            target_price = getattr(decision, "target_price", None)
            if target_price is None and hasattr(decision, "execution_parameters"):
                target_price = decision.execution_parameters.get("target_price")

        # Enforce maximum risk percentage cap: professional standard is 1-2%, never silently exceed 2%.
        if risk_percent > 0.02:
            raise ValueError("Professional risk limit exceeded. risk_percent cannot exceed 2% (0.02).")

        # Resolve trade direction
        action = getattr(decision, "action", None)
        if action is None:
            # Fallback for DecisionRecord or DecisionCandidate properties
            action = getattr(decision, "proposed_action", None)
        
        is_long = action == RecommendationAction.BUY

        # Calculate ATR-based stop loss
        if is_long:
            stop_loss = entry_price - (atr_value * atr_multiplier)
        else:
            stop_loss = entry_price + (atr_value * atr_multiplier)

        # Risk per share
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share <= 0.0:
            return None

        # Position sizing (shares)
        position_size = math.floor((account_size * risk_percent) / risk_per_share)

        # Default target price based on DEFAULT_TARGET_REWARD_RISK_RATIO reward:risk if target_price is not provided
        if target_price is None:
            if is_long:
                target_price = entry_price + DEFAULT_TARGET_REWARD_RISK_RATIO * risk_per_share
            else:
                target_price = entry_price - DEFAULT_TARGET_REWARD_RISK_RATIO * risk_per_share

        # Reward to risk ratio
        reward = abs(target_price - entry_price)
        reward_to_risk_ratio = reward / risk_per_share

        # Flag ratio if below the 1:2 minimum professional threshold
        is_ratio_flagged = reward_to_risk_ratio < 2.0

        total_risk_amount = position_size * risk_per_share

        return RiskAssessment(
            position_size=position_size,
            stop_loss_price=stop_loss,
            risk_per_share=risk_per_share,
            total_risk_amount=total_risk_amount,
            reward_to_risk_ratio=reward_to_risk_ratio,
            is_ratio_flagged=is_ratio_flagged,
            entry_price=entry_price,
            target_price=target_price
        )
