"""Unit tests for the Temporal Memory layer (Sprint 18)."""

import unittest
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

from core.knowledge import KnowledgeGraphEngine, TaxonomyCategory, Concept, KnowledgeLoader
from core.memory import (
    MemoryEventType,
    MemoryEventCategory,
    MemoryEvent,
    MemoryStore,
    MemoryLoader,
    get_category_for_type,
)
from core.domain.exceptions.validation import DomainValidationError


class TestTemporalMemory(unittest.TestCase):
    """Verifies that the Memory layer constructs, indexes, and queries temporal states correctly."""

    def setUp(self) -> None:
        self.engine = KnowledgeGraphEngine()
        # Pre-load mock concepts into Knowledge Graph
        data = {
            "concepts": [
                {"id": "AAPL", "name": "Apple Inc.", "category": "COMPANIES"},
                {"id": "MSFT", "name": "Microsoft Corp.", "category": "COMPANIES"},
                {"id": "TSMC", "name": "TSMC", "category": "COMPANIES"}
            ]
        }
        KnowledgeLoader.load_from_dict(self.engine, data)
        self.store = MemoryStore()

    def test_leadership_and_category_mapping(self) -> None:
        self.assertEqual(get_category_for_type(MemoryEventType.LEADERSHIP_CHANGE), MemoryEventCategory.MANAGEMENT)
        self.assertEqual(get_category_for_type(MemoryEventType.ACQUISITION), MemoryEventCategory.CORPORATE)
        self.assertEqual(get_category_for_type(MemoryEventType.DIVIDEND), MemoryEventCategory.FINANCIAL)
        self.assertEqual(get_category_for_type(MemoryEventType.REGULATORY), MemoryEventCategory.REGULATORY)

    def test_load_event_validates_against_knowledge_graph(self) -> None:
        now = datetime.now(timezone.utc)
        
        # Valid entity AAPL (exists in graph)
        data = [{
            "entity_id": "AAPL",
            "event_type": "LEADERSHIP_CHANGE",
            "timestamp": now.isoformat(),
            "properties": {"ceo": "Tim Cook"},
            "source_observation_id": "obs-1",
            "source_connector": "connector-sec"
        }]
        MemoryLoader.load_from_dict(self.store, self.engine, data)
        self.assertEqual(self.store.count, 1)

        # Invalid entity NONEXISTENT (should fail)
        invalid_data = [{
            "entity_id": "NONEXISTENT",
            "event_type": "LEADERSHIP_CHANGE",
            "timestamp": now.isoformat(),
            "properties": {"ceo": "Alice"},
            "source_observation_id": "obs-2",
            "source_connector": "connector-sec"
        }]
        with self.assertRaises(DomainValidationError) as context:
            MemoryLoader.load_from_dict(self.store, self.engine, invalid_data)
        self.assertIn("Reference validation failed", str(context.exception))

    def test_load_missing_mandatory_fields_raises(self) -> None:
        data = [{
            "entity_id": "AAPL",
            "event_type": "LEADERSHIP_CHANGE",
            # missing timestamp
            "properties": {"ceo": "Tim Cook"},
            "source_observation_id": "obs-1",
            "source_connector": "connector-sec"
        }]
        with self.assertRaises(DomainValidationError):
            MemoryLoader.load_from_dict(self.store, self.engine, data)

    def test_occurrence_timestamp_vs_ingestion_timestamp(self) -> None:
        occurrence_time = datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        ingested_time = datetime(2026, 1, 5, 17, 30, 0, tzinfo=timezone.utc)

        data = [{
            "entity_id": "AAPL",
            "event_type": "LEADERSHIP_CHANGE",
            "timestamp": occurrence_time.isoformat(),
            "ingested_at": ingested_time.isoformat(),
            "properties": {"ceo": "Tim Cook"},
            "source_observation_id": "obs-1",
            "source_connector": "connector-sec"
        }]
        MemoryLoader.load_from_dict(self.store, self.engine, data)
        
        event = self.store.get_latest("AAPL", MemoryEventType.LEADERSHIP_CHANGE)
        self.assertIsNotNone(event)
        self.assertEqual(event.timestamp, occurrence_time)
        self.assertEqual(event.ingested_at, ingested_time)

    def test_deterministic_secondary_sorting_on_identical_timestamps(self) -> None:
        # Same timestamp, but different properties/IDs
        now = datetime.now(timezone.utc)
        data = [
            {
                "entity_id": "AAPL",
                "event_type": "ACQUISITION",
                "timestamp": now.isoformat(),
                "properties": {"target": "Beats", "price": 3000000000},
                "source_observation_id": "obs-1",
                "source_connector": "connector-sec"
            },
            {
                "entity_id": "AAPL",
                "event_type": "ACQUISITION",
                "timestamp": now.isoformat(),
                "properties": {"target": "Siri", "price": 200000000},
                "source_observation_id": "obs-2",
                "source_connector": "connector-sec"
            }
        ]
        MemoryLoader.load_from_dict(self.store, self.engine, data)

        events = self.store.get_events("AAPL", MemoryEventType.ACQUISITION)
        self.assertEqual(len(events), 2)
        
        # Sorting must be deterministic by (timestamp, event_id)
        # Verify that sorting produces the exact same sequence regardless of insertion order
        event_ids_order = [e.event_id for e in events]
        
        # If we re-create store and load in reverse order, order should remain identical
        store2 = MemoryStore()
        MemoryLoader.load_from_dict(store2, self.engine, data[::-1])
        events2 = store2.get_events("AAPL", MemoryEventType.ACQUISITION)
        event_ids_order2 = [e.event_id for e in events2]
        
        self.assertEqual(event_ids_order, event_ids_order2)

    def test_chronological_query_range_filters(self) -> None:
        base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        data = [
            {
                "entity_id": "AAPL",
                "event_type": "DIVIDEND",
                "timestamp": (base_time - timedelta(days=10)).isoformat(),
                "properties": {"amount": 0.22},
                "source_observation_id": "obs-1",
                "source_connector": "connector-sec"
            },
            {
                "entity_id": "AAPL",
                "event_type": "DIVIDEND",
                "timestamp": base_time.isoformat(),
                "properties": {"amount": 0.23},
                "source_observation_id": "obs-2",
                "source_connector": "connector-sec"
            },
            {
                "entity_id": "AAPL",
                "event_type": "DIVIDEND",
                "timestamp": (base_time + timedelta(days=10)).isoformat(),
                "properties": {"amount": 0.24},
                "source_observation_id": "obs-3",
                "source_connector": "connector-sec"
            }
        ]
        MemoryLoader.load_from_dict(self.store, self.engine, data)

        # Query range spanning exactly base_time (only second event)
        events = self.store.get_events("AAPL", start=base_time, end=base_time)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].properties["amount"], 0.23)

        # Query range spanning large range (all events)
        events_all = self.store.get_events("AAPL")
        self.assertEqual(len(events_all), 3)

        # Query range outside of timestamps
        events_none = self.store.get_events("AAPL", start=base_time + timedelta(days=20))
        self.assertEqual(len(events_none), 0)

    def test_state_reconstruction_over_multiple_updates(self) -> None:
        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        
        # Sequence of CEO changes
        data = [
            {
                "entity_id": "AAPL",
                "event_type": "LEADERSHIP_CHANGE",
                "timestamp": base_time.isoformat(),
                "properties": {"ceo": "Steve Jobs"},
                "source_observation_id": "obs-1",
                "source_connector": "connector-sec"
            },
            {
                "entity_id": "AAPL",
                "event_type": "LEADERSHIP_CHANGE",
                "timestamp": (base_time + timedelta(days=100)).isoformat(),
                "properties": {"ceo": "Tim Cook"},
                "source_observation_id": "obs-2",
                "source_connector": "connector-sec"
            }
        ]
        MemoryLoader.load_from_dict(self.store, self.engine, data)

        # 1. Query state before any event exists (returns None)
        state_before = self.store.get_state_at("AAPL", "ceo", base_time - timedelta(days=1))
        self.assertIsNone(state_before)

        # 2. Query state on first event boundary
        state_first = self.store.get_state_at("AAPL", "ceo", base_time)
        self.assertEqual(state_first, "Steve Jobs")

        # 3. Query state in middle of timeline
        state_middle = self.store.get_state_at("AAPL", "ceo", base_time + timedelta(days=50))
        self.assertEqual(state_middle, "Steve Jobs")

        # 4. Query state after second event
        state_second = self.store.get_state_at("AAPL", "ceo", base_time + timedelta(days=101))
        self.assertEqual(state_second, "Tim Cook")

    def test_duplicate_event_id_rejection(self) -> None:
        now = datetime.now(timezone.utc)
        event_dict = {
            "event_id": "custom_duplicate_id",
            "entity_id": "AAPL",
            "event_type": "PRODUCT_LAUNCH",
            "timestamp": now.isoformat(),
            "properties": {"product": "iPhone 18"},
            "source_observation_id": "obs-1",
            "source_connector": "connector-sec"
        }
        
        MemoryLoader.load_from_dict(self.store, self.engine, [event_dict])
        
        # Second insert with duplicate ID must fail
        with self.assertRaises(DomainValidationError):
            MemoryLoader.load_from_dict(self.store, self.engine, [event_dict])

    def test_empty_store_behavior(self) -> None:
        self.assertEqual(self.store.count, 0)
        self.assertEqual(len(self.store.get_events("AAPL")), 0)
        self.assertIsNone(self.store.get_latest("AAPL", MemoryEventType.DIVIDEND))
        self.assertIsNone(self.store.get_state_at("AAPL", "ceo", datetime.now()))

    def test_interleaved_multi_entity_events(self) -> None:
        now = datetime.now(timezone.utc)
        data = [
            {
                "entity_id": "AAPL",
                "event_type": "PRODUCT_LAUNCH",
                "timestamp": now.isoformat(),
                "properties": {"product": "Apple Glass"},
                "source_observation_id": "obs-1",
                "source_connector": "connector-sec"
            },
            {
                "entity_id": "MSFT",
                "event_type": "PRODUCT_LAUNCH",
                "timestamp": (now + timedelta(seconds=1)).isoformat(),
                "properties": {"product": "Windows 12"},
                "source_observation_id": "obs-2",
                "source_connector": "connector-sec"
            }
        ]
        MemoryLoader.load_from_dict(self.store, self.engine, data)
        
        # Querying AAPL doesn't show MSFT events
        aapl_events = self.store.get_events("AAPL")
        self.assertEqual(len(aapl_events), 1)
        self.assertEqual(aapl_events[0].entity_id, "AAPL")

        msft_events = self.store.get_events("MSFT")
        self.assertEqual(len(msft_events), 1)
        self.assertEqual(msft_events[0].entity_id, "MSFT")


if __name__ == "__main__":
    unittest.main()
