"""Unit tests for Athena domain value objects."""

import unittest
from datetime import datetime, timezone
from dataclasses import FrozenInstanceError
from core.domain.value_objects import Candle, Indicator, RiskAssessment, Confidence
from core.domain.enums import RiskSeverity
from core.domain.exceptions import DomainValidationError

class TestCandleValueObject(unittest.TestCase):
    """Verifies candle logic checks and frozen state integrity."""

    def test_valid_candle(self) -> None:
        candle = Candle(
            timestamp=datetime.now(timezone.utc),
            open_price=100.0,
            high_price=105.0,
            low_price=99.0,
            close_price=102.0,
            volume=5000.0
        )
        self.assertEqual(candle.open_price, 100.0)
        self.assertEqual(candle.high_price, 105.0)

    def test_invalid_candle_high_low(self) -> None:
        with self.assertRaises(DomainValidationError):
            Candle(
                timestamp=datetime.now(timezone.utc),
                open_price=100.0,
                high_price=95.0,  # High less than Open & Low
                low_price=96.0,
                close_price=98.0,
                volume=100.0
            )

    def test_invalid_candle_high_less_than_close(self) -> None:
        with self.assertRaises(DomainValidationError):
            Candle(
                timestamp=datetime.now(timezone.utc),
                open_price=100.0,
                high_price=101.0,
                low_price=99.0,
                close_price=102.0,  # Close is higher than high!
                volume=100.0
            )

    def test_candle_immutability(self) -> None:
        candle = Candle(
            timestamp=datetime.now(timezone.utc),
            open_price=100.0,
            high_price=105.0,
            low_price=99.0,
            close_price=102.0,
            volume=5000.0
        )
        with self.assertRaises(FrozenInstanceError):
            candle.open_price = 101.0  # type: ignore


class TestIndicatorValueObject(unittest.TestCase):
    """Verifies indicator configurations and parameter protection."""

    def test_valid_indicator(self) -> None:
        ind = Indicator(name="RSI", value=71.2, parameters={"period": 14})
        self.assertEqual(ind.name, "RSI")
        self.assertEqual(ind.parameters["period"], 14)

    def test_indicator_parameters_readonly(self) -> None:
        ind = Indicator(name="EMA", value=124.5, parameters={"length": 50})
        with self.assertRaises(TypeError):
            ind.parameters["length"] = 100  # Should trigger type error because of MappingProxyType


class TestRiskAssessmentValueObject(unittest.TestCase):
    """Verifies risk categories and descriptors validation."""

    def test_valid_risk(self) -> None:
        risk = RiskAssessment(
            category="Liquidity",
            severity=RiskSeverity.HIGH,
            description="Average daily volume is lower than threshold."
        )
        self.assertEqual(risk.severity, RiskSeverity.HIGH)


class TestConfidenceValueObject(unittest.TestCase):
    """Verifies multi-dimensional confidence metrics bounds checking."""

    def test_valid_confidence(self) -> None:
        conf = Confidence(
            score=0.85,
            evidence_quality=0.90,
            model_agreement=0.80,
            evidence_count=15,
            last_updated=datetime.now(timezone.utc),
            rationale="Robust technical consensus supported by positive SEC filings."
        )
        self.assertEqual(conf.score, 0.85)

    def test_invalid_score_bounds(self) -> None:
        with self.assertRaises(DomainValidationError):
            Confidence(
                score=1.2,  # > 1.0
                evidence_quality=0.90,
                model_agreement=0.80,
                evidence_count=5,
                last_updated=datetime.now(timezone.utc),
                rationale="Invalid score check"
            )


if __name__ == "__main__":
    unittest.main()
