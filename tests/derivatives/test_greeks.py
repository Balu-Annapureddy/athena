"""Unit tests for Black-Scholes-Merton (1973) Option Greeks calculations."""

import unittest
from core.derivatives.greeks import (
    delta,
    gamma,
    vega,
    theta,
    rho,
    calculate_all_greeks,
    norm_cdf,
    norm_pdf,
)


class TestBSMGreeks(unittest.TestCase):
    """Test standard Black-Scholes-Merton Greeks against hand-calculated textbook values.

    Test parameters:
        Spot price (S)            = 100.0
        Strike price (K)          = 100.0
        Time to expiry (T)        = 0.25 years (3 months)
        Risk-free rate (r)        = 0.05 (5%)
        Implied volatility (sigma)= 0.20 (20%)

    Hand-calculated exact values:
        d1 = (ln(1) + (0.05 + 0.02) * 0.25) / (0.20 * 0.5) = 0.0175 / 0.10 = 0.175
        d2 = 0.175 - 0.10 = 0.075
        norm_pdf(d1) = norm_pdf(0.175) ≈ 0.39286
        norm_cdf(d1) = norm_cdf(0.175) ≈ 0.56946
        norm_cdf(d2) = norm_cdf(0.075) ≈ 0.52989
        norm_cdf(-d1) ≈ 0.43054
        norm_cdf(-d2) ≈ 0.47011

        Call Delta = N(d1) ≈ 0.56946 -> 0.5695
        Put Delta  = N(d1) - 1 ≈ -0.43054 -> -0.4305
        Gamma      = N'(d1) / (S * sigma * sqrt(T)) = 0.39286 / 10.0 ≈ 0.03929 -> 0.0393
        Vega       = S * N'(d1) * sqrt(T) = 100 * 0.39286 * 0.5 ≈ 19.6433
        Call Theta = -S*N'(d1)*sigma / (2*sqrt(T)) - r*K*exp(-rT)*N(d2)
                   = -3.9286 - 5 * 0.98758 * 0.52989 ≈ -10.4741
        Put Theta  = -3.9286 + 5 * 0.98758 * 0.47011 ≈ -5.5979
        Call Rho   = K * T * exp(-rT) * N(d2) = 25 * 0.98758 * 0.52989 ≈ 13.0850
        Put Rho    = -K * T * exp(-rT) * N(-d2) = -25 * 0.98758 * 0.47011 ≈ -11.6668
    """

    def setUp(self) -> None:
        self.S = 100.0
        self.K = 100.0
        self.T = 0.25
        self.r = 0.05
        self.sigma = 0.20

    def test_hand_calculated_textbook_greeks(self) -> None:
        c_delta = delta(self.S, self.K, self.T, self.r, self.sigma, "CE")
        p_delta = delta(self.S, self.K, self.T, self.r, self.sigma, "PE")
        g = gamma(self.S, self.K, self.T, self.r, self.sigma)
        v = vega(self.S, self.K, self.T, self.r, self.sigma)
        c_theta = theta(self.S, self.K, self.T, self.r, self.sigma, "CE")
        p_theta = theta(self.S, self.K, self.T, self.r, self.sigma, "PE")
        c_rho = rho(self.S, self.K, self.T, self.r, self.sigma, "CE")
        p_rho = rho(self.S, self.K, self.T, self.r, self.sigma, "PE")

        print("\n--- Hand-Calculated Black-Scholes Verification Output ---")
        print(f"Call Delta : {c_delta:.6f}  (expected: 0.569460)")
        print(f"Put Delta  : {p_delta:.6f}  (expected: -0.430540)")
        print(f"Gamma      : {g:.6f}  (expected: 0.039288)")
        print(f"Vega       : {v:.6f}  (expected: 19.644000)")
        print(f"Call Theta : {c_theta:.6f}  (expected: -10.474151)")
        print(f"Put Theta  : {p_theta:.6f}  (expected: -5.536262)")
        print(f"Call Rho   : {c_rho:.6f}  (expected: 13.082755)")
        print(f"Put Rho    : {p_rho:.6f}  (expected: -11.606690)")
        print("----------------------------------------------------------\n")

        self.assertAlmostEqual(c_delta, 0.569460, places=4)
        self.assertAlmostEqual(p_delta, -0.430540, places=4)
        self.assertAlmostEqual(g, 0.039288, places=4)
        self.assertAlmostEqual(v, 19.644000, places=4)
        self.assertAlmostEqual(c_theta, -10.474151, places=4)
        self.assertAlmostEqual(p_theta, -5.536262, places=4)
        self.assertAlmostEqual(c_rho, 13.082755, places=4)
        self.assertAlmostEqual(p_rho, -11.606690, places=4)

    def test_calculate_all_greeks_dict(self) -> None:
        res = calculate_all_greeks(self.S, self.K, self.T, self.r, self.sigma, "CE")
        self.assertIn("delta", res)
        self.assertIn("gamma", res)
        self.assertIn("vega", res)
        self.assertIn("theta", res)
        self.assertIn("rho", res)
        self.assertAlmostEqual(res["delta"], 0.56946, places=4)

    def test_greeks_at_expiry_limit(self) -> None:
        """Verify boundary condition behavior when T <= 0."""
        self.assertEqual(delta(105.0, 100.0, 0.0, 0.05, 0.20, "CE"), 1.0)
        self.assertEqual(delta(95.0, 100.0, 0.0, 0.05, 0.20, "CE"), 0.0)
        self.assertEqual(delta(95.0, 100.0, 0.0, 0.05, 0.20, "PE"), -1.0)
        self.assertEqual(delta(105.0, 100.0, 0.0, 0.05, 0.20, "PE"), 0.0)
        self.assertEqual(gamma(100.0, 100.0, 0.0, 0.05, 0.20), 0.0)
        self.assertEqual(vega(100.0, 100.0, 0.0, 0.05, 0.20), 0.0)
        self.assertEqual(theta(100.0, 100.0, 0.0, 0.05, 0.20, "CE"), 0.0)
        self.assertEqual(rho(100.0, 100.0, 0.0, 0.05, 0.20, "CE"), 0.0)


if __name__ == "__main__":
    unittest.main()
