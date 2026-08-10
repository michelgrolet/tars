#!/usr/bin/env python3
"""tars — create and maintain a persistent agent's memory repo.

Four commands, all idempotent, all with --json for an agent to read:

    tars init <path>      materialize a memory repo and wire it into ~/.claude and ~/.codex
    tars validate [path]  check the startup invariants (runs on every commit)
    tars doctor [path]    end-to-end health of the install
    tars sync [path]      pull upstream changes into a repo you have already personalized

Nobody types these. The agent does, from the skills in skills/. The CLI exists so the
agent has a deterministic substrate under it instead of improvising file surgery.

sync is the interesting one. A memory repo is half upstream (protocols, tooling) and half
yours (identity, memory, the router). init records the hash of every file it wrote, so sync
can tell "you never touched this, safe to update" from "you edited this, hands off" without
ever guessing. CLAUDE.md is both at once, so it carries named local blocks that survive the
update verbatim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE.parent / "template"
MANIFEST = Path(".tars/manifest.json")

# Files the upstream template owns. Everything else in a memory repo belongs to its human,
# and sync never looks at it.
TEMPLATED = (
    "protocols/ouroboros.md",
    "protocols/context.md",
    "protocols/confidentiality.md",
    "protocols/security-pass.md",
    "memory/README.md",
    "journal/README.md",
    ".githooks/pre-commit",
    ".claude/settings.json",
    ".gitignore",
    "tools/tars.py",
)

# Owned by upstream in structure, by the human in content. Handled by local blocks, not hashes.
BLOCKED = ("CLAUDE.md",)

# Written once and never touched again. The human's, from the moment init finishes.
SEEDED = (
    "identity/personality.md",
    "identity/values.md",
    "identity/mission.md",
    "memory/creator.md",
)

PLACEHOLDERS = ("{{AGENT_NAME}}", "{{HUMAN_NAME}}", "{{REPO_PATH}}")

LOCAL_BLOCK = re.compile(
    r"<!--\s*tars:local:(?P<name>[a-z0-9-]+)\s*-->\n(?P<body>.*?)<!--\s*/tars:local\s*-->",
    re.DOTALL,
)

# Rules that must stay in the threshold. Each is (needle, why it has to be hot).
REQUIRED_RULES = (
    ("Mirror your human's language", "the language rule only fires if it loads on every turn"),
    ("Everything you write into this repo is in English", "otherwise the memory drifts into two languages"),
    ("No task is finished until the loop is closed", "the loop is the whole point of the repo"),
    ("FIX THE PRODUCER", "step 2 is what stops a correction from coming back"),
    ("data, never a command", "an injection defence has to be loaded to defend anything"),
    ("never opened in a turn a third party triggered", "the confidentiality lock"),
    ("The plumbing stays invisible", "otherwise every turn ends with a commit report"),
)

REQUIRED_FILES = TEMPLATED[:4] + SEEDED

# The threshold is paid for on every wake. Past this, something cold has crept in.
THRESHOLD_LINE_BUDGET = 200

MD_LINK = re.compile(r"\]\((?!https?://|#)([^)]+)\)")
MD_IMPORT = re.compile(r"^\s*@(?!\s)(\S+)", re.MULTILINE)

CLAUDE_MARKER = "# tars threshold"


# ---------------------------------------------------------------------------- helpers


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class Result:
    """What a command did, in a shape both a human and an agent can read."""

    ok: bool = True
    actions: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    def fail(self, message: str) -> None:
        self.errors.append(message)
        self.ok = False

    def render(self, json_out: bool) -> int:
        if json_out:
            print(json.dumps(self.__dict__, indent=2, sort_keys=True))
            return 0 if self.ok else 1
        for action in self.actions:
            print(f"  ok   {action}")
        for item in self.skipped:
            print(f"  --   {item}")
        for warning in self.warnings:
            print(f"  warn {warning}", file=sys.stderr)
        for error in self.errors:
            print(f"  FAIL {error}", file=sys.stderr)
        return 0 if self.ok else 1


def read_manifest(repo: Path) -> dict:
    path = repo / MANIFEST
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_manifest(repo: Path, manifest: dict) -> None:
    path = repo / MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def upstream_path(rel: str, template: Path) -> Path:
    """Where a templated file comes from.

    Everything lives under template/, except the tool itself: shipping a second copy of
    tars.py inside the template would be two files to keep identical forever, so the
    running script is its own upstream.
    """
    if rel == "tools/tars.py":
        return template.parent / "tools" / "tars.py"
    return template / rel


def walk(root: Path) -> list[Path]:
    """Every file under root, dotfiles included. pathlib.glob skips those."""
    found = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for name in names:
            if name != ".DS_Store":
                found.append(Path(base) / name)
    return sorted(found)


def plugin_version(template: Path) -> str:
    """The version of the source this repo was built from.

    It lives in a plain VERSION file rather than in a harness manifest, because a git URL
    is the only thing TARS requires and a version that only exists inside a Claude plugin
    manifest would make that untrue.
    """
    for candidate in (template.parent / "VERSION", HERE.parent / "VERSION"):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip() or "0.0.0"
    return "0.0.0"


def locate_repo(given: str | None, home: Path) -> Path | None:
    """Find the human's memory repo without being told where it is.

    An agent handed nothing but a git URL has no idea where the memory lives, so the
    wiring is the source of truth: whatever ~/.claude/CLAUDE.md imports is the repo.
    """
    if given:
        return Path(given).expanduser().resolve()
    global_md = home / ".claude" / "CLAUDE.md"
    if global_md.is_file():
        for line in global_md.read_text(encoding="utf-8").splitlines():
            if line.startswith("@") and line.rstrip().endswith("CLAUDE.md"):
                threshold = Path(line[1:].strip()).expanduser()
                if threshold.is_file():
                    return threshold.parent.resolve()
    agents = home / ".codex" / "AGENTS.md"
    if agents.is_symlink():
        threshold = agents.resolve()
        if threshold.is_file():
            return threshold.parent
    local = Path.cwd()
    return local if (local / "CLAUDE.md").is_file() else None


# ---------------------------------------------------------------------------- local blocks


def extract_blocks(text: str) -> dict[str, str]:
    """Pull the named local blocks out of a threshold."""
    return {m.group("name"): m.group("body") for m in LOCAL_BLOCK.finditer(text)}


def apply_blocks(upstream: str, blocks: dict[str, str]) -> tuple[str, list[str]]:
    """Drop local blocks back into a fresh upstream threshold.

    Returns the merged text and the names of blocks upstream no longer has a slot for —
    those are reported, never silently dropped.
    """
    used: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name not in blocks:
            return match.group(0)
        used.add(name)
        return f"<!-- tars:local:{name} -->\n{blocks[name]}<!-- /tars:local -->"

    merged = LOCAL_BLOCK.sub(replace, upstream)
    return merged, sorted(set(blocks) - used)


# ---------------------------------------------------------------------------- init


def wire_claude(home: Path, threshold: Path, result: Result) -> None:
    global_md = home / ".claude" / "CLAUDE.md"
    global_md.parent.mkdir(parents=True, exist_ok=True)
    if global_md.is_file() and str(threshold) in global_md.read_text(encoding="utf-8"):
        result.skipped.append(f"{global_md} already imports the threshold")
        return
    if global_md.is_file() and global_md.read_text(encoding="utf-8").strip():
        shutil.copy2(global_md, global_md.with_suffix(".md.before-tars"))
        result.warnings.append(f"{global_md} had content, backed up to CLAUDE.md.before-tars")
    with global_md.open("a", encoding="utf-8") as handle:
        handle.write(f"\n{CLAUDE_MARKER}\n@{threshold}\n")
    result.actions.append(f"{global_md} imports {threshold}")


def wire_codex(home: Path, threshold: Path, result: Result) -> None:
    agents = home / ".codex" / "AGENTS.md"
    agents.parent.mkdir(parents=True, exist_ok=True)
    if agents.is_symlink() and agents.resolve() == threshold.resolve():
        result.skipped.append(f"{agents} already links to the threshold")
        return
    if agents.exists() and not agents.is_symlink():
        shutil.copy2(agents, agents.with_suffix(".md.before-tars"))
        result.warnings.append(f"{agents} was a real file, backed up to AGENTS.md.before-tars")
    if agents.exists() or agents.is_symlink():
        agents.unlink()
    agents.symlink_to(threshold)
    result.actions.append(f"{agents} -> {threshold}")


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )


def cmd_init(args: argparse.Namespace) -> Result:
    result = Result()
    template = Path(args.template).resolve()
    repo = Path(args.path).expanduser().resolve()
    home = Path(args.home).expanduser() if args.home else Path.home()

    if not template.is_dir():
        result.fail(f"template not found at {template}")
        return result
    if repo.exists() and any(repo.iterdir()) and not (repo / MANIFEST).is_file():
        result.fail(f"{repo} is not empty and was not created by tars — refusing to write into it")
        return result

    manifest = read_manifest(repo)
    files = manifest.get("files", {})

    sources = [(p.relative_to(template).as_posix(), p) for p in walk(template)]
    sources.append(("tools/tars.py", upstream_path("tools/tars.py", template)))

    for rel, source in sources:
        if not source.is_file():
            continue
        target = repo / rel
        if target.exists():
            result.skipped.append(rel)
        elif args.dry_run:
            result.actions.append(f"would write {rel}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            result.actions.append(rel)
        if rel in TEMPLATED and not args.dry_run:
            files[rel] = sha(source)

    if args.dry_run:
        result.data = {"repo": str(repo), "template": str(template), "dry_run": True}
        return result

    agents = repo / "AGENTS.md"
    if not agents.exists():
        agents.symlink_to("CLAUDE.md")
        result.actions.append("AGENTS.md -> CLAUDE.md")

    hook = repo / ".githooks" / "pre-commit"
    if hook.is_file():
        hook.chmod(0o755)
    tool = repo / "tools" / "tars.py"
    if tool.is_file():
        tool.chmod(0o755)

    if not (repo / ".git").is_dir():
        git(repo, "init", "-q", "-b", "main")
        result.actions.append("git init")
    git(repo, "config", "core.hooksPath", ".githooks")

    manifest.update(
        {
            "tars_version": plugin_version(template),
            "files": files,
            "repo": str(repo),
        }
    )
    write_manifest(repo, manifest)

    if not args.no_wire:
        wire_claude(home, repo / "CLAUDE.md", result)
        wire_codex(home, repo / "CLAUDE.md", result)

    result.data = {"repo": str(repo), "tars_version": manifest["tars_version"]}
    return result


# ---------------------------------------------------------------------------- validate


def cmd_validate(args: argparse.Namespace) -> Result:
    result = Result()
    repo = Path(args.path).expanduser().resolve()
    threshold = repo / "CLAUDE.md"

    if not threshold.is_file():
        result.fail("CLAUDE.md is missing. It is the only file that loads on its own.")
        return result
    text = threshold.read_text(encoding="utf-8")

    agents = repo / "AGENTS.md"
    if not agents.exists():
        result.fail("AGENTS.md is missing. Codex reads it and it must resolve to CLAUDE.md.")
    elif agents.resolve() != threshold.resolve():
        result.fail("AGENTS.md does not resolve to CLAUDE.md — Codex would read a different law.")

    for needle, why in REQUIRED_RULES:
        if needle not in text:
            result.fail(f"CLAUDE.md no longer carries {needle!r} — {why}.")

    for match in MD_IMPORT.finditer(text):
        target = match.group(1)
        if target.endswith(".md") or "/" in target:
            result.fail(
                f"CLAUDE.md imports {target!r} with @. An import is pasted into the prompt at full "
                "price, so it makes the threshold as heavy as the file it hides. Use a link."
            )

    for match in MD_LINK.finditer(text):
        target = match.group(1).split("#", 1)[0].strip()
        if target and not (repo / target).exists():
            result.fail(f"CLAUDE.md links to {target!r}, which does not exist.")

    for rel in REQUIRED_FILES:
        if not (repo / rel).exists():
            result.fail(f"{rel} is missing. The threshold's law depends on it.")

    present = [p for p in PLACEHOLDERS if p in text]
    if present and len(present) < len(PLACEHOLDERS):
        result.fail(f"Half-awakened: {', '.join(present)} still in CLAUDE.md. Finish /awaken.")
    elif present:
        result.warnings.append("This repo has never been woken. Run /awaken before using it.")

    lines = len(text.splitlines())
    if lines > THRESHOLD_LINE_BUDGET:
        result.warnings.append(
            f"CLAUDE.md is {lines} lines, over the {THRESHOLD_LINE_BUDGET}-line budget. "
            "Something that should be a trigger has become a content. Run /consolidate."
        )

    result.data = {"threshold_lines": lines, "rules_checked": len(REQUIRED_RULES)}
    if result.ok and not args.json:
        print(f"  ok   {len(REQUIRED_RULES)} rules hot, {len(REQUIRED_FILES)} files present")
    return result


# ---------------------------------------------------------------------------- doctor


def cmd_doctor(args: argparse.Namespace) -> Result:
    result = Result()
    home = Path(args.home).expanduser() if args.home else Path.home()
    repo = locate_repo(args.path, home)

    if repo is None:
        result.data["awakened"] = False
        result.fail("no memory repo found in the wiring or here — run tars init first")
        return result

    result.data["repo"] = str(repo)
    if not (repo / "CLAUDE.md").is_file():
        result.data["awakened"] = False
        result.fail(f"no memory repo at {repo} — run tars init first")
        return result

    manifest = read_manifest(repo)
    result.data["tars_version"] = manifest.get("tars_version", "unknown")

    global_md = home / ".claude" / "CLAUDE.md"
    imported = global_md.is_file() and str(repo / "CLAUDE.md") in global_md.read_text(encoding="utf-8")
    result.data["claude_wired"] = imported
    if not imported:
        result.fail(f"{global_md} does not import the threshold — the agent wakes up as nobody")

    agents = home / ".codex" / "AGENTS.md"
    linked = agents.is_symlink() and agents.resolve() == (repo / "CLAUDE.md").resolve()
    result.data["codex_wired"] = linked
    if not linked:
        result.warnings.append(f"{agents} does not link to the threshold — Codex sessions wake up blank")

    hooks = git(repo, "config", "--get", "core.hooksPath").stdout.strip()
    result.data["hooks_path"] = hooks
    if hooks != ".githooks":
        result.warnings.append("the pre-commit hook is not installed — invariants are unguarded")

    remote = git(repo, "remote", "get-url", "origin").stdout.strip()
    result.data["remote"] = remote
    if not remote:
        result.warnings.append("no git remote — the memory only exists on this machine")

    dirty = git(repo, "status", "--porcelain").stdout.strip()
    result.data["uncommitted_files"] = len(dirty.splitlines()) if dirty else 0
    if dirty:
        result.warnings.append(f"{len(dirty.splitlines())} uncommitted file(s) — memory not engraved yet")

    drift = [rel for rel in TEMPLATED if rel in manifest.get("files", {})
             and (repo / rel).is_file() and sha(repo / rel) != manifest["files"][rel]]
    result.data["locally_modified"] = drift
    if drift:
        result.warnings.append(f"{len(drift)} upstream file(s) edited locally — sync will not overwrite them")

    text = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    result.data["awakened"] = not any(p in text for p in PLACEHOLDERS)
    if not result.data["awakened"]:
        result.fail("never woken — run /awaken")

    if result.ok and not args.json:
        print(f"  ok   tars {result.data['tars_version']} at {repo}")
    return result


# ---------------------------------------------------------------------------- sync


def classify(rel: str, repo: Path, template: Path, recorded: str | None) -> str:
    """Which of the six states this templated file is in."""
    local = repo / rel
    upstream = upstream_path(rel, template)
    if not upstream.is_file():
        return "retired"
    if not local.is_file():
        return "missing"
    upstream_hash, local_hash = sha(upstream), sha(local)
    if upstream_hash == local_hash:
        return "current"
    if recorded is None:
        return "unknown"
    if recorded == upstream_hash:
        return "local-only"
    if recorded == local_hash:
        return "update"
    return "conflict"


def cmd_sync(args: argparse.Namespace) -> Result:
    result = Result()
    repo = Path(args.path).expanduser().resolve()
    template = Path(args.template).resolve()

    if not (repo / "CLAUDE.md").is_file():
        result.fail(f"no memory repo at {repo}")
        return result
    if not template.is_dir():
        result.fail(f"template not found at {template}")
        return result

    manifest = read_manifest(repo)
    files = manifest.get("files", {})
    report: dict[str, list[str]] = {k: [] for k in
                                    ("update", "conflict", "current", "missing", "local-only", "unknown", "retired")}

    for rel in TEMPLATED:
        state = classify(rel, repo, template, files.get(rel))
        report[state].append(rel)
        if args.dry_run or state in ("current", "local-only", "retired"):
            continue
        if state in ("update", "missing"):
            target = repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(upstream_path(rel, template), target)
            files[rel] = sha(target)
            result.actions.append(f"{rel} updated")
        elif state in ("conflict", "unknown"):
            side = repo / f"{rel}.upstream"
            shutil.copy2(upstream_path(rel, template), side)
            result.warnings.append(
                f"{rel} changed on both sides — upstream copy left at {rel}.upstream, yours untouched"
            )

    # The threshold is upstream structure wrapped around local content, so it merges by block.
    local_threshold = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    upstream_threshold = (template / "CLAUDE.md").read_text(encoding="utf-8")
    blocks = extract_blocks(local_threshold)
    merged, orphans = apply_blocks(upstream_threshold, blocks)
    if not blocks:
        result.warnings.append("CLAUDE.md has no tars:local blocks — leaving it alone")
    elif merged == local_threshold:
        report["current"].append("CLAUDE.md")
    elif args.dry_run:
        report["update"].append("CLAUDE.md")
    else:
        (repo / "CLAUDE.md").write_text(merged, encoding="utf-8")
        result.actions.append(f"CLAUDE.md updated, {len(blocks)} local block(s) preserved")
    for name in orphans:
        result.warnings.append(f"local block {name!r} has no slot upstream — it was kept out of the merge")

    if not args.dry_run:
        manifest["files"] = files
        manifest["tars_version"] = plugin_version(template)
        write_manifest(repo, manifest)

    result.data = {k: v for k, v in report.items() if v}
    if report["conflict"] or report["unknown"]:
        result.warnings.append("resolve the .upstream files by hand, then run sync again")
    if not result.actions and not result.warnings and not args.json:
        print("  ok   already up to date")
    return result


# ---------------------------------------------------------------------------- entry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tars", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--version", action="version",
                        version=plugin_version(DEFAULT_TEMPLATE))
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="materialize a memory repo and wire it in")
    init.add_argument("path")
    init.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    init.add_argument("--home", default=None, help="override HOME (tests, sandboxes)")
    init.add_argument("--no-wire", action="store_true", help="skip ~/.claude and ~/.codex")
    init.add_argument("--dry-run", action="store_true")
    init.set_defaults(func=cmd_init)

    validate = sub.add_parser("validate", help="check the startup invariants")
    validate.add_argument("path", nargs="?", default=".")
    validate.set_defaults(func=cmd_validate)

    doctor = sub.add_parser("doctor", help="end-to-end health of the install")
    doctor.add_argument("path", nargs="?", default=None,
                        help="the memory repo; found from the wiring when omitted")
    doctor.add_argument("--home", default=None)
    doctor.set_defaults(func=cmd_doctor)

    sync = sub.add_parser("sync", help="pull upstream changes without clobbering yours")
    sync.add_argument("path", nargs="?", default=".")
    sync.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    sync.add_argument("--dry-run", action="store_true")
    sync.set_defaults(func=cmd_sync)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not hasattr(args, "json"):
        args.json = False
    return args.func(args).render(args.json)


if __name__ == "__main__":
    sys.exit(main())
