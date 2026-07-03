"""Unit tests for the Formula dependency resolver."""

import unittest
from core.domain.exceptions import DomainValidationError
from core.mathematics.formulas import Formula
from core.measurements import FormulaDependencyResolver, FormulaId

class TestDependencyResolver(unittest.TestCase):
    """Verifies that resolver handles DAG sorting and catches circular dependencies."""

    def test_topological_sort_no_cycle(self) -> None:
        resolver = FormulaDependencyResolver()
        
        # Define clean formulas:
        # ROE requires NetIncome and Equity
        # NET_MARGIN requires NetIncome and Revenue
        formulas = {
            FormulaId.ROE: Formula(
                name="Return on Equity",
                inputs=["NetIncome", "Equity"],
                expression=lambda NetIncome, Equity: NetIncome / Equity,
                output="ROE"
            ),
            FormulaId.NET_MARGIN: Formula(
                name="Net Profit Margin",
                inputs=["NetIncome", "Revenue"],
                expression=lambda NetIncome, Revenue: NetIncome / Revenue,
                output="NetMargin"
            )
        }

        # Available facts: NetIncome, Equity, Revenue
        order = resolver.resolve_execution_order({"NetIncome", "Equity", "Revenue"}, formulas)
        self.assertEqual(len(order), 2)
        self.assertIn(FormulaId.ROE, order)
        self.assertIn(FormulaId.NET_MARGIN, order)

    def test_circular_dependency_fails(self) -> None:
        resolver = FormulaDependencyResolver()
        
        # A depends on B, B depends on A
        formulas = {
            FormulaId.ROE: Formula(
                name="Formula A",
                inputs=["NetMargin"],
                expression=lambda NetMargin: NetMargin * 2.0,
                output="ROE"
            ),
            FormulaId.NET_MARGIN: Formula(
                name="Formula B",
                inputs=["ROE"],
                expression=lambda ROE: ROE * 0.5,
                output="NetMargin"
            )
        }

        with self.assertRaises(DomainValidationError):
            resolver.resolve_execution_order(set(), formulas)


if __name__ == "__main__":
    unittest.main()
