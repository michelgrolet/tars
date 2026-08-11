#!/usr/bin/env python3
"""Project extensions/registry.json into .claude-plugin/marketplace.json.

The registry is the source of truth and it is neutral: a name, a description, a git URL,
and what the extension needs to run. The marketplace file is one consumer of it, shaped
the way Claude Code wants. Anything else that wants the list reads the registry.

    python3 tools/registry.py            print what an agent needs to decide
    python3 tools/registry.py --check    fail if the marketplace has drifted (CI, tests)
    python3 tools/registry.py --write    regenerate the marketplace from the registry
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "extensions/registry.json"
MARKETPLACE = ROOT / ".claude-plugin/marketplace.json"
SCHEMA = "https://anthropic.com/claude-code/marketplace.schema.json"


def load() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def project(registry: dict) -> dict:
    """Everything Claude Code understands, and nothing it does not.

    `requires` and `provides` are dropped on purpose: the CLI warns on fields it does
    not know, and a warning on every validate run is how a repo teaches people to
    ignore its own tooling.
    """
    market = registry["marketplace"]
    return {
        "$schema": SCHEMA,
        "name": market["name"],
        "description": market["description"],
        "owner": market["owner"],
        "plugins": [
            {
                "name": ext["name"],
                "description": ext["description"],
                "author": market["owner"],
                "category": ext["category"],
                "source": ext["source"],
                "homepage": ext["repo"],
                "license": ext["license"],
            }
            for ext in registry["extensions"]
        ],
    }


def needs(ext: dict) -> str:
    """One line an agent can read out before installing anything."""
    req = ext["requires"]
    parts = []
    if req["database"]:
        parts.append(f"a {req['database']} to point it at, local or hosted")
    if req["always_on"]:
        parts.append("a host that stays awake, so a laptop that sleeps will not do")
    parts.extend(req["credentials"])
    return "; ".join(parts) if parts else "nothing, it runs where your agent runs"


def standalone(ext: dict) -> bool:
    """Does this extension work with no TARS anywhere on the machine?

    Derived from where the code lives rather than declared, because a declared boolean
    is a promise nobody checks. An extension with its own repo is cloned and wired from
    its own README, and TARS is one client of it among several. An extension that lives
    in this directory has no repo to clone and no life without the harness, which is the
    only reason it is allowed in here.
    """
    return ext["name"] != "tars" and not isinstance(ext["source"], str)


def install(ext: dict) -> str:
    """How you get it without TARS, for the ones that have a way."""
    if ext["name"] == "tars":
        return "the harness itself"
    if not standalone(ext):
        return f"ships inside TARS, at {ext['source']}"
    return f"git clone {ext['repo']}.git, then its own README. No TARS required."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the marketplace drifted")
    parser.add_argument("--write", action="store_true", help="regenerate the marketplace")
    args = parser.parse_args(argv)

    registry = load()
    projected = json.dumps(project(registry), indent=2) + "\n"

    if args.write:
        MARKETPLACE.write_text(projected, encoding="utf-8")
        print(f"wrote {MARKETPLACE.relative_to(ROOT)} from {REGISTRY.relative_to(ROOT)}")
        return 0

    if args.check:
        current = MARKETPLACE.read_text(encoding="utf-8")
        if current != projected:
            print("marketplace.json has drifted from the registry. "
                  "Edit extensions/registry.json, then run tools/registry.py --write.",
                  file=sys.stderr)
            return 1
        print("ok: the marketplace is what the registry projects")
        return 0

    width = max(len(e["name"]) for e in registry["extensions"])
    for ext in registry["extensions"]:
        print(f"{ext['name']:<{width}}  {ext['repo']}")
        print(f"{'':<{width}}  needs: {needs(ext)}")
        print(f"{'':<{width}}  install: {install(ext)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
