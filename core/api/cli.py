"""Command-Line Interface (CLI) wrapping Athena operations."""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, List, Optional

from core.api.sdk import AthenaClient, AthenaAPIException


def _print_json(data: Any) -> None:
    """Print JSON formatted structures cleanly to stdout."""
    print(json.dumps(data, indent=2))


def main(args: Optional[List[str]] = None) -> int:
    """CLI Entry Point orchestrating namespaced subcommands to the AthenaClient SDK."""
    parser = argparse.ArgumentParser(
        prog="athena",
        description="Athena Cognitive Platform Command-Line Interface"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8080",
        help="Target REST Server URL (default: http://localhost:8080)"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. Health Command
    subparsers.add_parser("health", help="Inspect platform health diagnostics.")

    # 2. Version Command
    subparsers.add_parser("version", help="Inspect platform version details.")

    # 3. Knowledge Command
    kw_parser = subparsers.add_parser("knowledge", help="Query Knowledge Graph details.")
    kw_sub = kw_parser.add_subparsers(dest="subcommand", required=True)
    
    ent_parser = kw_sub.add_parser("entity", help="Fetch details for a concept entity ID.")
    ent_parser.add_argument("entity_id", help="Concept Entity ID.")

    ns_parser = kw_sub.add_parser("neighbors", help="Fetch neighbors of an entity.")
    ns_parser.add_argument("entity_id", help="Concept Entity ID.")

    # 4. Memory Command
    mem_parser = subparsers.add_parser("memory", help="Query Temporal Memory details.")
    mem_sub = mem_parser.add_subparsers(dest="subcommand", required=True)

    ev_parser = mem_sub.add_parser("events", help="Fetch events logs for an entity.")
    ev_parser.add_argument("entity_id", help="Entity ID.")

    st_parser = mem_sub.add_parser("state", help="Resolve historic state value.")
    st_parser.add_argument("entity_id", help="Entity ID.")
    st_parser.add_argument("key", help="State property key.")
    st_parser.add_argument("timestamp", help="ISO format timestamp (e.g. 2024-01-01T00:00:00Z).")

    # 5. Simulation Command
    sim_parser = subparsers.add_parser("simulation", help="Run scenario simulations.")
    sim_sub = sim_parser.add_subparsers(dest="subcommand", required=True)
    sim_run = sim_sub.add_parser("run", help="Run simulation scenario.")
    sim_run.add_argument("filepath", help="Path to scenario JSON definition file.")

    # 6. Explanation Command
    exp_parser = subparsers.add_parser("explanation", help="Fetch narrative explanation reports.")
    exp_parser.add_argument("decision_id", help="Decision ID.")

    # 7. Configuration Command
    cfg_parser = subparsers.add_parser("configuration", help="Query Configuration snapshot lists.")
    cfg_sub = cfg_parser.add_subparsers(dest="subcommand", required=True)
    cfg_sub.add_parser("snapshots", help="List registered snapshots.")

    parsed = parser.parse_args(args)
    client = AthenaClient(base_url=parsed.url)

    try:
        if parsed.command == "health":
            _print_json(client.health())
            return 0

        elif parsed.command == "version":
            _print_json(client.version())
            return 0

        elif parsed.command == "explanation":
            _print_json(client.explanation.report(parsed.decision_id))
            return 0

        elif parsed.command == "configuration":
            if parsed.subcommand == "snapshots":
                _print_json(client.configuration.snapshots())
                return 0

        elif parsed.command == "knowledge":
            if parsed.subcommand == "entity":
                _print_json(client.knowledge.entity(parsed.entity_id))
                return 0
            elif parsed.subcommand == "neighbors":
                _print_json(client.knowledge.neighbors(parsed.entity_id))
                return 0

        elif parsed.command == "memory":
            if parsed.subcommand == "events":
                _print_json(client.memory.events(parsed.entity_id))
                return 0
            elif parsed.subcommand == "state":
                try:
                    ts = datetime.fromisoformat(parsed.timestamp)
                except ValueError:
                    print(f"Error: Timestamp '{parsed.timestamp}' is not a valid ISO format string.", file=sys.stderr)
                    return 1
                _print_json(client.memory.state(parsed.entity_id, parsed.key, ts))
                return 0

        elif parsed.command == "simulation":
            if parsed.subcommand == "run":
                if not os.path.exists(parsed.filepath):
                    print(f"Error: Scenario file path '{parsed.filepath}' not found.", file=sys.stderr)
                    return 1
                try:
                    with open(parsed.filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    print(f"Error reading JSON from '{parsed.filepath}': {str(e)}", file=sys.stderr)
                    return 1

                _print_json(client.simulation.run(data))
                return 0

    except AthenaAPIException as e:
        print(f"API Error ({e.code}): {e.message}", file=sys.stderr)
        if e.details:
            _print_json(e.details)
        return 1
    except Exception as e:
        print(f"Unexpected Client Error: {str(e)}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
