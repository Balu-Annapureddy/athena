"""Agreement, Conflict, Coverage, and Diversity logic for the Athena Evidence Engine."""

from typing import List, Set
from core.evidence.accumulator import EvidenceRecord, EvidenceState

def calculate_agreement(evidences: List[EvidenceRecord]) -> float:
    """Calculate the agreement index (0.0 to 1.0) of a collection of evidence.

    Returns 0.5 (neutral uncertainty) if total weight is zero.
    """
    active_ev = [ev for ev in evidences if ev.state in (EvidenceState.NEW, EvidenceState.VERIFIED, EvidenceState.ACTIVE)]
    if not active_ev:
        return 0.5

    supporting_weight = 0.0
    total_weight = 0.0

    for ev in active_ev:
        effective_w = ev.weight * ev.trust * ev.relevance * ev.freshness
        total_weight += effective_w
        if ev.supports:
            supporting_weight += effective_w

    if total_weight == 0.0:
        return 0.5

    return supporting_weight / total_weight


def calculate_conflict(evidences: List[EvidenceRecord]) -> float:
    """Calculate the conflict index (0.0 to 1.0) indicating internal cognitive tension.

    A score of 1.0 indicates maximum conflict (even support vs contradiction),
    while 0.0 indicates absolute consensus.
    """
    agreement = calculate_agreement(evidences)
    return 2.0 * min(agreement, 1.0 - agreement)


def calculate_coverage(evidences: List[EvidenceRecord], required_fact_ids: Set[str]) -> float:
    """Calculate the coverage index (0.0 to 1.0) indicating completeness of required fields."""
    if not required_fact_ids:
        return 1.0

    represented_ids = set()
    for ev in evidences:
        if ev.state in (EvidenceState.NEW, EvidenceState.VERIFIED, EvidenceState.ACTIVE):
            for fid in ev.source_fact_ids:
                # We can check string representation or value
                represented_ids.add(str(fid).upper())

    matched = 0
    for req in required_fact_ids:
        if req.upper() in represented_ids:
            matched += 1

    return matched / len(required_fact_ids)


def calculate_diversity(evidences: List[EvidenceRecord]) -> float:
    """Calculate the source diversity index (0.0 to 1.0).

    Categories tracked: REGULATORY, FINANCIAL_STATEMENT, MARKET_DATA, NEWS, SOCIAL, INTERNAL.
    """
    possible_categories = {"REGULATORY", "FINANCIAL_STATEMENT", "MARKET_DATA", "NEWS", "SOCIAL", "INTERNAL"}
    
    active_categories = set()
    for ev in evidences:
        if ev.state in (EvidenceState.NEW, EvidenceState.VERIFIED, EvidenceState.ACTIVE):
            cat = ev.source_category.upper()
            if cat in possible_categories:
                active_categories.add(cat)

    return len(active_categories) / len(possible_categories)
