"""Unit tests for the Mathematics Formulas engine."""

import unittest
from datetime import datetime, timezone
from core.domain.value_objects import Measurement
from core.domain.exceptions import DomainValidationError
from core.mathematics import CORE_FORMULAS

class TestMathematicsFormulas(unittest.TestCase):
    """Verifies calculation accuracy, constraint enforcement, and propagation of metadata."""

    def test_ebitda_calculation(self) -> None:
        formula = CORE_FORMULAS["EBITDA"]
        
        inputs = {
            "NetIncome": Measurement(100.0, "INR", "AUDITED", datetime.now(timezone.utc), "Source", 0.95),
            "Interest": Measurement(10.0, "INR", "AUDITED", datetime.now(timezone.utc), "Source", 0.90),
            "Tax": Measurement(20.0, "INR", "VERIFIED", datetime.now(timezone.utc), "Source", 0.92),
            "Depreciation": Measurement(15.0, "INR", "AUDITED", datetime.now(timezone.utc), "Source", 0.88),
            "Amortization": Measurement(5.0, "INR", "AUDITED", datetime.now(timezone.utc), "Source", 0.95),
        }
        
        result = formula.calculate(inputs)
        
        # 100 + 10 + 20 + 15 + 5 = 150.0
        self.assertEqual(result.value, 150.0)
        self.assertEqual(result.units, "currency")
        
        # Verify confidence propagation (min confidence of inputs: 0.88)
        self.assertEqual(result.confidence_score, 0.88)
        
        # Verify quality propagation (lowest quality should be VERIFIED since Tax is VERIFIED)
        self.assertEqual(result.quality, "VERIFIED")

    def test_pe_ratio_calculation(self) -> None:
        formula = CORE_FORMULAS["PE_Ratio"]
        
        inputs = {
            "Price": Measurement(150.0, "INR", "AUDITED", datetime.now(timezone.utc), "Ticker", 1.0),
            "EPS": Measurement(10.0, "INR", "AUDITED", datetime.now(timezone.utc), "Filing", 0.95)
        }
        
        result = formula.calculate(inputs)
        self.assertEqual(result.value, 15.0)
        self.assertEqual(result.units, "ratio")

    def test_pe_ratio_constraint_failure(self) -> None:
        formula = CORE_FORMULAS["PE_Ratio"]
        
        inputs = {
            "Price": Measurement(150.0, "INR", "AUDITED", datetime.now(timezone.utc), "Ticker", 1.0),
            "EPS": Measurement(0.0, "INR", "AUDITED", datetime.now(timezone.utc), "Filing", 0.95) # EPS is zero!
        }
        
        with self.assertRaises(DomainValidationError):
            formula.calculate(inputs)

    def test_missing_input_failure(self) -> None:
        formula = CORE_FORMULAS["PE_Ratio"]
        
        inputs = {
            "Price": Measurement(150.0, "INR", "AUDITED", datetime.now(timezone.utc), "Ticker", 1.0)
            # Missing EPS
        }
        
        with self.assertRaises(DomainValidationError):
            formula.calculate(inputs)


if __name__ == "__main__":
    unittest.main()
