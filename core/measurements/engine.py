"""Measurement engine orchestrating dynamic formula calculations."""

import logging
from typing import List, Dict, Set
from core.domain.entities import Fact
from core.domain.value_objects import Measurement
from core.mathematics.formulas import Formula
from core.measurements.taxonomy import FormulaId
from core.measurements.resolver import FormulaDependencyResolver
from core.measurements.executor import FormulaExecutor
from core.measurements.factory import DerivedMeasurement, MeasurementFactory

class MeasurementEngine:
    """Orchestrates DAG-based formula calculations with topological sorting and lineage audits."""

    def __init__(
        self,
        formulas: Dict[FormulaId, Formula],
        resolver: FormulaDependencyResolver = None,
        executor: FormulaExecutor = None,
        factory: MeasurementFactory = None
    ) -> None:
        self._formulas = dict(formulas)
        self._resolver = resolver or FormulaDependencyResolver()
        self._executor = executor or FormulaExecutor()
        self._factory = factory or MeasurementFactory()

    def calculate_measurements(self, facts: List[Fact]) -> Dict[FormulaId, DerivedMeasurement]:
        """Resolve dependency sequences and calculate derived measurements, logging lineage."""
        # 1. Map available input fact names
        fact_names = {fact.name.upper() for fact in facts}
        
        # 2. Topologically sort the executable order of formulas
        try:
            execution_order = self._resolver.resolve_execution_order(fact_names, self._formulas)
        except Exception as e:
            logging.error(f"Failed to resolve execution order: {str(e)}")
            raise

        # Lookup maps for calculation traversal
        derived_results: Dict[FormulaId, DerivedMeasurement] = {}
        fact_lookup: Dict[str, Fact] = {fact.name.upper(): fact for fact in facts}

        # 3. Process execution order
        for fid in execution_order:
            formula = self._formulas[fid]
            
            # Resolve inputs from facts or preceding calculations
            inputs: Dict[str, Measurement] = {}
            source_facts = []
            source_measurements = []
            inputs_satisfied = True

            for inp in formula.inputs:
                inp_upper = inp.upper()
                
                # Check facts first
                if inp_upper in fact_lookup:
                    fact = fact_lookup[inp_upper]
                    inputs[inp] = fact.value
                    source_facts.append(fact.id)
                else:
                    # Check previously derived measurements
                    found_derived = False
                    for dfid, dmeas in derived_results.items():
                        if self._formulas[dfid].output.upper() == inp_upper:
                            inputs[inp] = dmeas.measurement
                            source_measurements.append(str(dfid.value))
                            # Add its parent facts to consolidate the complete lineage tree
                            source_facts.extend(dmeas.source_fact_ids)
                            source_measurements.extend(dmeas.source_measurement_ids)
                            found_derived = True
                            break
                    if not found_derived:
                        inputs_satisfied = False
                        break

            if not inputs_satisfied:
                logging.warning(f"Unsatisfied inputs for formula '{fid.value}', skipping execution.")
                continue

            # Execute calculation with error isolation
            try:
                result_vo = self._executor.execute(formula, inputs)
                
                # Uniquify source IDs
                unique_facts = list(set(source_facts))
                unique_meas = list(set(source_measurements))

                derived = self._factory.create_derived_measurement(
                    measurement=result_vo,
                    formula_id=fid,
                    formula_version="1.0.0",
                    source_fact_ids=unique_facts,
                    source_measurement_ids=unique_meas
                )
                
                derived_results[fid] = derived
                
                # Propagate output key as available fact input for subsequent calculations
                fact_names.add(formula.output.upper())
            except Exception as e:
                logging.error(f"Calculation failed for formula '{fid.value}': {str(e)}")
                # Error isolation: catch exception, skip, and continue execution of other formulas
                continue

        return derived_results
