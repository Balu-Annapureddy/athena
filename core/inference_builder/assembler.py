"""InferenceAssembler materializing candidates to domain Inference models."""

from typing import List
from core.domain.entities import Inference
from core.domain.entities.inference import ReasoningStep
from core.domain.common import DomainMetadata
from core.inference_builder.candidate import InferenceCandidate
from core.inference_builder.ledger import InferenceLedger

class InferenceAssembler:
    """Materializes candidates to domain Inference models and records them in the ledger."""

    def __init__(self, ledger: InferenceLedger = None) -> None:
        self._ledger = ledger or InferenceLedger()

    @property
    def ledger(self) -> InferenceLedger:
        """Expose the inference ledger for auditing and state retrieval."""
        return self._ledger

    def assemble_inferences(self, candidates: List[InferenceCandidate]) -> List[Inference]:
        """Materialize candidates to domain Inference models and append ledger entries."""
        materialized = []

        for candidate in candidates:
            # Build structured reasoning steps
            steps = [
                ReasoningStep(
                    source_evidence_id=eid,
                    rule_id=candidate.rule_name,
                    generated_statement=candidate.statement
                )
                for eid in candidate.source_evidence_ids
            ]

            # Enforce domain metadata tracing
            metadata = DomainMetadata.create(
                entity_id=candidate.candidate_id,
                source="InferenceAssembler",
                created_by=candidate.rule_name
            )

            inference = Inference(
                metadata=metadata,
                evidence_ids=candidate.source_evidence_ids,
                reasoning_path=steps,
                conclusion=candidate.statement
            )

            # Record to the ledger
            self._ledger.record_inference(
                inference_id=candidate.candidate_id,
                entity_id=candidate.entity_id,
                evidence_ids=candidate.source_evidence_ids,
                reasoning_path=steps,
                conclusion=candidate.statement,
                rule_name=candidate.rule_name,
                rule_version=candidate.rule_version,
                policy_version=candidate.policy_version
            )

            materialized.append(inference)

        return materialized
