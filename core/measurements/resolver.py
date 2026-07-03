"""Formula dependency resolver and cycle detection logic for the Measurement Engine."""

from typing import List, Dict, Set
from core.domain.exceptions import DomainValidationError
from core.mathematics.formulas import Formula
from core.measurements.taxonomy import FormulaId

class FormulaDependencyResolver:
    """Resolves formula execution order, building a DAG and detecting cycles."""

    def resolve_execution_order(
        self,
        available_fact_names: Set[str],
        formulas: Dict[FormulaId, Formula]
    ) -> List[FormulaId]:
        """Resolve a topologically sorted execution order of formulas.

        Raises DomainValidationError if a circular dependency is detected.
        """
        # Map output concept names to FormulaIds
        output_to_formula: Dict[str, FormulaId] = {}
        for fid, f in formulas.items():
            output_to_formula[f.output.upper()] = fid

        # Build adjacency list: formula A depends on formula B if B's output is an input to A.
        adj: Dict[FormulaId, List[FormulaId]] = {fid: [] for fid in formulas}
        for fid, f in formulas.items():
            for inp in f.inputs:
                inp_upper = inp.upper()
                if inp_upper in output_to_formula:
                    dep_id = output_to_formula[inp_upper]
                    adj[fid].append(dep_id)

        # DFS for cycle detection and topological sorting
        visited: Set[FormulaId] = set()
        visiting: Set[FormulaId] = set()
        order: List[FormulaId] = []

        def dfs(node: FormulaId) -> None:
            if node in visiting:
                raise DomainValidationError(
                    f"Cyclic dependency detected in formula registry involving: {node.value}"
                )
            if node in visited:
                return
            
            visiting.add(node)
            for dep in adj[node]:
                dfs(dep)
            visiting.remove(node)
            visited.add(node)
            order.append(node)

        for fid in formulas:
            if fid not in visited:
                dfs(fid)

        # Filter the sorted order to only return formulas whose inputs can be satisfied
        satisfied_outputs = {fact.upper() for fact in available_fact_names}
        executable_order: List[FormulaId] = []

        for fid in order:
            f = formulas[fid]
            if all(inp.upper() in satisfied_outputs for inp in f.inputs):
                executable_order.append(fid)
                satisfied_outputs.add(f.output.upper())

        return executable_order
