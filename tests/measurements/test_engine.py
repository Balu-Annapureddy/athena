"""Unit tests for the Measurement Engine calculations orchestration."""

import unittest
from datetime import datetime, timezone
from core.domain.entities import Fact
from core.domain.common import ObservationId, FactId, DomainMetadata
from core.domain.value_objects import Measurement
from core.mathematics.formulas import Formula
from core.measurements import MeasurementEngine, FormulaId, DerivedMeasurement

class TestMeasurementEngine(unittest.TestCase):
    """Verifies that the engine performs deterministic calculations with isolated error handling and complete lineage."""

    def _create_fact(self, name: str, value: float, units: str) -> Fact:
        fact_id = FactId.generate()
        meas = Measurement(
            value=value,
            units=units,
            quality="AUDITED",
            timestamp=datetime.now(timezone.utc),
            source="Source",
            confidence_score=1.0
        )
        return Fact(
            metadata=DomainMetadata.create(fact_id),
            source_observation_id=ObservationId.generate(),
            name=name,
            value=meas,
            extracted_at=datetime.now(timezone.utc)
        )

    def test_engine_calculations_success(self) -> None:
        # Inputs: NetIncome=15.0, Equity=80.0
        fact_ni = self._create_fact("NetIncome", 15.0, "currency")
        fact_eq = self._create_fact("Equity", 80.0, "currency")
        
        formulas = {
            FormulaId.ROE: Formula(
                name="Return on Equity",
                inputs=["NetIncome", "Equity"],
                expression=lambda NetIncome, Equity: NetIncome / Equity,
                output="ROE",
                units="%"
            )
        }

        engine = MeasurementEngine(formulas)
        results = engine.calculate_measurements([fact_ni, fact_eq])

        self.assertEqual(len(results), 1)
        self.assertIn(FormulaId.ROE, results)
        
        derived = results[FormulaId.ROE]
        self.assertEqual(derived.measurement.value, 15.0 / 80.0)
        self.assertEqual(derived.measurement.units, "%")
        
        # Verify confidence is exact 1.0
        self.assertEqual(derived.measurement.confidence_score, 1.0)
        
        # Verify source fact lineage
        self.assertIn(fact_ni.id, derived.source_fact_ids)
        self.assertIn(fact_eq.id, derived.source_fact_ids)

    def test_error_isolation(self) -> None:
        fact_ni = self._create_fact("NetIncome", 15.0, "currency")
        fact_eq = self._create_fact("Equity", 80.0, "currency")
        
        # Formula 1: Crashes due to division by zero (NetMargin)
        # Formula 2: Success (ROE)
        formulas = {
            FormulaId.NET_MARGIN: Formula(
                name="Crashing Net Margin",
                inputs=["NetIncome"],
                expression=lambda NetIncome: NetIncome / 0.0,
                output="NetMargin"
            ),
            FormulaId.ROE: Formula(
                name="Return on Equity",
                inputs=["NetIncome", "Equity"],
                expression=lambda NetIncome, Equity: NetIncome / Equity,
                output="ROE",
                units="%"
            )
        }

        engine = MeasurementEngine(formulas)
        results = engine.calculate_measurements([fact_ni, fact_eq])

        # Verify net margin crashed, but ROE succeeded
        self.assertEqual(len(results), 1)
        self.assertIn(FormulaId.ROE, results)
        self.assertNotIn(FormulaId.NET_MARGIN, results)

    def test_multistep_dependencies(self) -> None:
        # Fact: Revenue=100.0, NetIncome=15.0, Equity=80.0, Liabilities=20.0
        # Formula 1: Equity = Assets - Liabilities (Wait, let's reverse it to have: Assets = Equity + Liabilities)
        # Formula 2: ROE = NetIncome / Equity
        # Let's check a pipeline:
        # A (Assets) = Equity + Liabilities
        # B (DebtToAssets) = Debt / Assets
        fact_eq = self._create_fact("Equity", 80.0, "currency")
        fact_liab = self._create_fact("Liabilities", 20.0, "currency")
        fact_debt = self._create_fact("Debt", 40.0, "currency")

        formulas = {
            FormulaId.CURRENT_RATIO: Formula(
                name="Total Assets",
                inputs=["Equity", "Liabilities"],
                expression=lambda Equity, Liabilities: Equity + Liabilities,
                output="Assets"
            ),
            FormulaId.DEBT_TO_EQUITY: Formula(
                name="Debt to Assets Ratio",
                inputs=["Debt", "Assets"],
                expression=lambda Debt, Assets: Debt / Assets,
                output="DebtToAssets"
            )
        }

        engine = MeasurementEngine(formulas)
        results = engine.calculate_measurements([fact_eq, fact_liab, fact_debt])

        self.assertEqual(len(results), 2)
        
        # Verify assets = 80 + 20 = 100
        self.assertEqual(results[FormulaId.CURRENT_RATIO].measurement.value, 100.0)
        
        # Verify debt_to_assets = 40 / 100 = 0.4
        derived_ratio = results[FormulaId.DEBT_TO_EQUITY]
        self.assertEqual(derived_ratio.measurement.value, 0.4)
        
        # Check parent fact lineage (Debt, Equity, Liabilities must all be present in DebtToAssets)
        self.assertIn(fact_eq.id, derived_ratio.source_fact_ids)
        self.assertIn(fact_liab.id, derived_ratio.source_fact_ids)
        self.assertIn(fact_debt.id, derived_ratio.source_fact_ids)
        
        # Check source measurement lineage (CURRENT_RATIO must be in source_measurement_ids)
        self.assertIn(str(FormulaId.CURRENT_RATIO.value), derived_ratio.source_measurement_ids)


if __name__ == "__main__":
    unittest.main()
