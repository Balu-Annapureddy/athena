"""Financial Knowledge Graph implementation mapping standard accounting and balance sheet structures."""

from core.knowledge.taxonomy import TaxonomyCategory
from core.knowledge.graphs.base import KnowledgeGraph, Concept, Relationship, PredicateType, Constraint

class FinancialGraph(KnowledgeGraph):
    """Represents objective corporate financial structures, statement line items, and accounting equations."""

    def __init__(self) -> None:
        super().__init__("Financial Graph")
        self._build_financial_graph()

    def _build_financial_graph(self) -> None:
        # Define base concept nodes
        revenue = Concept(id="REVENUE", name="Revenue", category=TaxonomyCategory.ACCOUNTING)
        ebitda = Concept(id="EBITDA", name="EBITDA", category=TaxonomyCategory.ACCOUNTING)
        net_income = Concept(id="NET_INCOME", name="Net Income", category=TaxonomyCategory.ACCOUNTING)
        
        assets = Concept(id="ASSETS", name="Total Assets", category=TaxonomyCategory.ACCOUNTING)
        liabilities = Concept(id="LIABILITIES", name="Total Liabilities", category=TaxonomyCategory.ACCOUNTING)
        equity = Concept(id="EQUITY", name="Shareholders Equity", category=TaxonomyCategory.ACCOUNTING)
        debt = Concept(id="DEBT", name="Total Debt", category=TaxonomyCategory.ACCOUNTING)
        cash = Concept(id="CASH", name="Cash and Equivalents", category=TaxonomyCategory.ACCOUNTING)

        self.add_concept(revenue)
        self.add_concept(ebitda)
        self.add_concept(net_income)
        self.add_concept(assets)
        self.add_concept(liabilities)
        self.add_concept(equity)
        self.add_concept(debt)
        self.add_concept(cash)

        # Add relationships
        self.add_relationship(Relationship(source_id="REVENUE", target_id="EBITDA", predicate=PredicateType.DERIVES))
        self.add_relationship(Relationship(source_id="EBITDA", target_id="NET_INCOME", predicate=PredicateType.DERIVES))
        self.add_relationship(Relationship(source_id="ASSETS", target_id="CASH", predicate=PredicateType.CONTAINS))
        self.add_relationship(Relationship(source_id="LIABILITIES", target_id="DEBT", predicate=PredicateType.CONTAINS))

        # Add balance sheet identity constraint (Assets = Liabilities + Equity)
        self.add_constraint(
            Constraint(
                id="BALANCE_SHEET_IDENTITY",
                description="Total Assets must equal Liabilities + Equity",
                expression_name="ASSETS == LIABILITIES + EQUITY",
                target_concept_ids=["ASSETS", "LIABILITIES", "EQUITY"]
            )
        )
