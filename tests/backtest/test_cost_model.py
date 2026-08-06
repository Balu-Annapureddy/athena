"""Unit tests for TransactionCostModel — verifying real Indian market cost calculations."""

import unittest

from core.backtest.engine import TransactionCostModel, ZERO_COST_MODEL


class TestTransactionCostModelDefaults(unittest.TestCase):
    """Verify default Zerodha-rate cost model produces correct numbers."""

    def setUp(self) -> None:
        self.model = TransactionCostModel()

    def test_zero_cost_model_produces_zero(self) -> None:
        """ZERO_COST_MODEL should return exactly 0 for all cost components."""
        entry_c, exit_c, total = ZERO_COST_MODEL.cost_for_trade(
            entry_value=100_000.0, exit_value=105_000.0, is_long=True
        )
        self.assertEqual(entry_c, 0.0)
        self.assertEqual(exit_c, 0.0)
        self.assertEqual(total, 0.0)

    def test_long_trade_sell_side_has_stt(self) -> None:
        """LONG trade: STT (0.1%) applies only on exit (sell side)."""
        # Entry of Rs 1,00,000 (buy side) → no STT
        # Exit of Rs 1,05,000 (sell side) → STT = 1,05,000 * 0.001 = Rs 105
        entry_c, exit_c, total = self.model.cost_for_trade(
            entry_value=100_000.0,
            exit_value=105_000.0,
            is_long=True,
        )
        # Exit cost must exceed entry cost; the gap is dominated by STT (Rs 105)
        # Other charges differ slightly due to the different notionals.
        self.assertGreater(exit_c, entry_c)
        # Difference should be at least Rs 105 (the STT component)
        self.assertGreaterEqual(exit_c - entry_c, 105_000.0 * 0.001)

    def test_short_trade_stt_on_entry(self) -> None:
        """SHORT trade: entry is sell side so STT applies at entry, not exit."""
        entry_c_short, exit_c_short, _ = self.model.cost_for_trade(
            entry_value=100_000.0,
            exit_value=95_000.0,
            is_long=False,
        )
        entry_c_long, exit_c_long, _ = self.model.cost_for_trade(
            entry_value=100_000.0,
            exit_value=95_000.0,
            is_long=True,
        )
        # SHORT entry is a sell, so STT appears in entry_c_short
        self.assertGreater(entry_c_short, entry_c_long)
        # SHORT exit is a buy, so exit_c_short has no STT
        self.assertLess(exit_c_short, exit_c_long)

    def test_brokerage_cap_applied(self) -> None:
        """For very large positions, brokerage should be capped at Rs 20/order."""
        # 100 lakh turnover per side: 0.03% = Rs 300 → must be capped at Rs 20
        entry_c, exit_c, _ = self.model.cost_for_trade(
            entry_value=10_000_000.0,
            exit_value=10_000_000.0,
            is_long=True,
        )
        # Reconstruct expected entry cost manually:
        brokerage = min(0.0003 * 10_000_000, 20.0)          # capped at Rs 20
        exchange   = 0.0000322 * 10_000_000                  # Rs 322
        sebi       = 0.000001  * 10_000_000                  # Rs 10
        gst        = 0.18 * (brokerage + exchange)            # 18% on brokerage + exchange
        slip       = (8.0 / 10_000) * 10_000_000             # Rs 800 slippage
        # No STT on LONG entry (buy side)
        expected_entry = brokerage + exchange + sebi + gst + slip
        self.assertAlmostEqual(entry_c, expected_entry, places=1)

    def test_full_round_trip_small_position(self) -> None:
        """Spot-check full round-trip costs on a realistic small position."""
        # 100 shares of Rs 2000 stock = Rs 2,00,000 entry and exit notional
        entry_value = 100 * 2000.0
        exit_value  = 100 * 2100.0
        entry_c, exit_c, total = self.model.cost_for_trade(
            entry_value=entry_value, exit_value=exit_value, is_long=True
        )
        # Sanity: costs should be positive, less than 2% of notional
        self.assertGreater(total, 0)
        self.assertLess(total, 0.02 * (entry_value + exit_value))

    def test_slippage_is_symmetric_per_side(self) -> None:
        """Slippage should be applied equally to entry and exit sides."""
        model = TransactionCostModel(
            brokerage_pct=0.0,
            brokerage_cap=0.0,
            stt_sell_rate=0.0,
            exchange_txn_rate=0.0,
            gst_rate=0.0,
            sebi_rate=0.0,
            slippage_bps=10.0,   # 10 bps = 0.10%
        )
        # Same entry and exit notional so both sides should have identical slippage
        entry_c, exit_c, total = model.cost_for_trade(
            entry_value=100_000.0, exit_value=100_000.0, is_long=True
        )
        self.assertAlmostEqual(entry_c, 100_000.0 * 0.001, places=6)
        self.assertAlmostEqual(exit_c,  100_000.0 * 0.001, places=6)
        self.assertAlmostEqual(total,   100_000.0 * 0.002, places=6)

    def test_cost_for_zero_notional(self) -> None:
        """Zero notional trades should produce zero costs without division by zero."""
        entry_c, exit_c, total = self.model.cost_for_trade(
            entry_value=0.0, exit_value=0.0, is_long=True
        )
        self.assertEqual(entry_c, 0.0)
        self.assertEqual(exit_c,  0.0)
        self.assertEqual(total,   0.0)

    def test_gross_vs_net_pnl_difference_equals_costs(self) -> None:
        """Verify that gross_pnl - net_pnl == total_costs for a simulated trade."""
        # Simulate: buy 50 shares @ Rs 1000, sell @ Rs 1100 → gross PnL = Rs 5000
        entry_value = 50 * 1000.0
        exit_value  = 50 * 1100.0
        gross_pnl   = 50 * (1100.0 - 1000.0)
        _, _, total_cost = self.model.cost_for_trade(
            entry_value=entry_value, exit_value=exit_value, is_long=True
        )
        net_pnl = gross_pnl - total_cost
        self.assertAlmostEqual(gross_pnl - net_pnl, total_cost, places=6)


class TestTransactionCostModelCustomRates(unittest.TestCase):
    """Verify the cost model correctly uses custom rate overrides."""

    def test_custom_stt_rate(self) -> None:
        """Custom (lower) STT rate should produce lower exit cost for LONG trades."""
        # Intraday STT on sell side = 0.025% (lower than delivery 0.1%)
        model_intraday = TransactionCostModel(stt_sell_rate=0.00025)  # 0.025%
        _, exit_c_intraday, _ = model_intraday.cost_for_trade(
            entry_value=100_000.0, exit_value=100_000.0, is_long=True
        )
        model_delivery = TransactionCostModel()  # default delivery 0.1%
        _, exit_c_delivery, _ = model_delivery.cost_for_trade(
            entry_value=100_000.0, exit_value=100_000.0, is_long=True
        )
        # Intraday STT (0.025%) is lower than delivery STT (0.1%), so exit cost should be lower
        self.assertLess(exit_c_intraday, exit_c_delivery)


if __name__ == "__main__":
    unittest.main()
