"""Black-Scholes-Merton (1973) Option Greeks calculation module.

Reference:
    Fischer Black and Myron Scholes (1973), "The Pricing of Options and Corporate Liabilities",
    Journal of Political Economy, 81 (3): 637-654.
    Robert C. Merton (1973), "Theory of Rational Option Pricing",
    Bell Journal of Economics and Management Science, 4 (1): 141-183.
"""

import math
from typing import Dict, Union


def norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal distribution N(x)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Probability density function for standard normal distribution N'(x)."""
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)


def _d1_d2(
    spot_price: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    implied_volatility: float,
) -> tuple[float, float]:
    vol = max(implied_volatility, 1e-6)
    t = max(time_to_expiry, 1e-6)
    d1 = (math.log(spot_price / strike) + (risk_free_rate + 0.5 * vol * vol) * t) / (
        vol * math.sqrt(t)
    )
    d2 = d1 - vol * math.sqrt(t)
    return d1, d2


def delta(
    spot_price: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    implied_volatility: float,
    option_type: str = "CE",
) -> float:
    """Calculate Black-Scholes Delta (rate of change of option value with respect to spot price)."""
    is_call = option_type.upper() in ("CE", "CALL", "C")
    if time_to_expiry <= 0.0:
        if is_call:
            return 1.0 if spot_price > strike else (0.5 if spot_price == strike else 0.0)
        else:
            return -1.0 if spot_price < strike else (-0.5 if spot_price == strike else 0.0)

    d1, _ = _d1_d2(spot_price, strike, time_to_expiry, risk_free_rate, implied_volatility)
    return norm_cdf(d1) if is_call else norm_cdf(d1) - 1.0


def gamma(
    spot_price: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    implied_volatility: float,
) -> float:
    """Calculate Black-Scholes Gamma (rate of change of Delta with respect to spot price)."""
    if time_to_expiry <= 0.0:
        return 0.0

    vol = max(implied_volatility, 1e-6)
    d1, _ = _d1_d2(spot_price, strike, time_to_expiry, risk_free_rate, implied_volatility)
    return norm_pdf(d1) / (spot_price * vol * math.sqrt(time_to_expiry))


def vega(
    spot_price: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    implied_volatility: float,
) -> float:
    """Calculate Black-Scholes Vega (rate of change of option value with respect to implied volatility).

    Returns derivative with respect to absolute volatility (e.g. dV/dsigma).
    """
    if time_to_expiry <= 0.0:
        return 0.0

    d1, _ = _d1_d2(spot_price, strike, time_to_expiry, risk_free_rate, implied_volatility)
    return spot_price * norm_pdf(d1) * math.sqrt(time_to_expiry)


def theta(
    spot_price: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    implied_volatility: float,
    option_type: str = "CE",
) -> float:
    """Calculate Black-Scholes Theta (annualized rate of change of option value with respect to time)."""
    if time_to_expiry <= 0.0:
        return 0.0

    is_call = option_type.upper() in ("CE", "CALL", "C")
    vol = max(implied_volatility, 1e-6)
    d1, d2 = _d1_d2(spot_price, strike, time_to_expiry, risk_free_rate, implied_volatility)

    term1 = -(spot_price * norm_pdf(d1) * vol) / (2.0 * math.sqrt(time_to_expiry))
    discount = math.exp(-risk_free_rate * time_to_expiry)

    if is_call:
        term2 = risk_free_rate * strike * discount * norm_cdf(d2)
        return term1 - term2
    else:
        term2 = risk_free_rate * strike * discount * norm_cdf(-d2)
        return term1 + term2


def rho(
    spot_price: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    implied_volatility: float,
    option_type: str = "CE",
) -> float:
    """Calculate Black-Scholes Rho (rate of change of option value with respect to risk-free interest rate)."""
    if time_to_expiry <= 0.0:
        return 0.0

    is_call = option_type.upper() in ("CE", "CALL", "C")
    _, d2 = _d1_d2(spot_price, strike, time_to_expiry, risk_free_rate, implied_volatility)
    discount = math.exp(-risk_free_rate * time_to_expiry)

    if is_call:
        return strike * time_to_expiry * discount * norm_cdf(d2)
    else:
        return -strike * time_to_expiry * discount * norm_cdf(-d2)


def calculate_all_greeks(
    spot_price: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    implied_volatility: float,
    option_type: str = "CE",
) -> Dict[str, float]:
    """Calculate all 5 Black-Scholes Greeks at once for a contract."""
    return {
        "delta": delta(spot_price, strike, time_to_expiry, risk_free_rate, implied_volatility, option_type),
        "gamma": gamma(spot_price, strike, time_to_expiry, risk_free_rate, implied_volatility),
        "vega": vega(spot_price, strike, time_to_expiry, risk_free_rate, implied_volatility),
        "theta": theta(spot_price, strike, time_to_expiry, risk_free_rate, implied_volatility, option_type),
        "rho": rho(spot_price, strike, time_to_expiry, risk_free_rate, implied_volatility, option_type),
    }
