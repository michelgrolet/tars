"""Tests for the tars CLI.

The ones that matter are in TestSync: an update mechanism that silently overwrites a file
its human edited is worse than no update mechanism at all, so every branch of the state
machine is pinned here.

Run: python3 -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tars  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "template"


def init_args(path: Path, home: Path, **overrides) -> Namespace:
    args = Namespace(path=str(path), template=str(TEMPLATE), home=str(home),
                     no_wire=False, dry_run=False, json=False)
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def sync_args(path: Path, template: Path, **overrides) -> Namespace:
    args = Namespace(path=str(path), template=str(template), dry_run=False, json=True)
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


class TarsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "home"
        self.repo = self.tmp / "memory"
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def make_repo(self, **overrides) -> tars.Result:
        return tars.cmd_init(init_args(self.repo, self.home, **overrides))

    def fork_template(self) -> Path:
        """A writable copy of the shipped template, standing in for a newer upstream."""
        fork = self.tmp / "upstream"
        (fork / "template").parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(TEMPLATE, fork / "template")
        shutil.copytree(ROOT / "tools", fork / "tools")
        shutil.copy2(ROOT / "VERSION", fork / "VERSION")
        return fork / "template"


class TestInit(TarsTestCase):
    def test_creates_a_working_repo(self) -> None:
        result = self.make_repo()
        self.assertTrue(result.ok, result.errors)
        for rel in tars.TEMPLATED + tars.SEEDED + ("CLAUDE.md",):
            self.assertTrue((self.repo / rel).is_file(), f"{rel} missing")
        self.assertTrue((self.repo / "AGENTS.md").is_symlink())
        self.assertEqual((self.repo / "AGENTS.md").resolve(), (self.repo / "CLAUDE.md").resolve())
        self.assertTrue((self.repo / ".git").is_dir())

    def test_records_a_hash_for_every_templated_file(self) -> None:
        self.make_repo()
        recorded = tars.read_manifest(self.repo)["files"]
        self.assertEqual(sorted(recorded), sorted(tars.TEMPLATED))
        for rel, digest in recorded.items():
            self.assertEqual(digest, tars.sha(self.repo / rel), rel)

    def test_is_idempotent(self) -> None:
        first = self.make_repo()
        before = tars.sha(self.repo / "CLAUDE.md")
        second = self.make_repo()
        self.assertTrue(second.ok)
        self.assertEqual(before, tars.sha(self.repo / "CLAUDE.md"))
        self.assertTrue(first.actions)
        self.assertFalse(second.actions, "second run should have nothing to do")

    def test_dry_run_writes_nothing(self) -> None:
        result = self.make_repo(dry_run=True)
        self.assertTrue(result.ok)
        self.assertFalse((self.repo / "CLAUDE.md").exists())

    def test_refuses_a_foreign_non_empty_directory(self) -> None:
        self.repo.mkdir(parents=True)
        (self.repo / "my-thesis.txt").write_text("do not clobber me")
        result = self.make_repo()
        self.assertFalse(result.ok)
        self.assertEqual((self.repo / "my-thesis.txt").read_text(), "do not clobber me")

    def test_wires_both_runtimes(self) -> None:
        self.make_repo()
        imported = (self.home / ".claude" / "CLAUDE.md").read_text()
        self.assertIn(str(self.repo / "CLAUDE.md"), imported)
        codex = self.home / ".codex" / "AGENTS.md"
        self.assertEqual(codex.resolve(), (self.repo / "CLAUDE.md").resolve())

    def test_backs_up_an_existing_global_claude_md(self) -> None:
        (self.home / ".claude").mkdir(parents=True)
        (self.home / ".claude" / "CLAUDE.md").write_text("my own instructions\n")
        self.make_repo()
        backup = self.home / ".claude" / "CLAUDE.md.before-tars"
        self.assertTrue(backup.is_file())
        self.assertEqual(backup.read_text(), "my own instructions\n")
        self.assertIn("my own instructions", (self.home / ".claude" / "CLAUDE.md").read_text())

    def test_no_wire_leaves_home_alone(self) -> None:
        self.make_repo(no_wire=True)
        self.assertFalse((self.home / ".claude" / "CLAUDE.md").exists())


class TestValidate(TarsTestCase):
    def validate(self) -> tars.Result:
        return tars.cmd_validate(Namespace(path=str(self.repo), json=True))

    def test_a_fresh_repo_passes_with_a_never_woken_warning(self) -> None:
        self.make_repo()
        result = self.validate()
        self.assertTrue(result.ok, result.errors)
        self.assertTrue(any("never been woken" in w for w in result.warnings))

    def test_dropping_a_hot_rule_fails(self) -> None:
        self.make_repo()
        threshold = self.repo / "CLAUDE.md"
        threshold.write_text(threshold.read_text().replace("Mirror your human's language", "Speak English"))
        result = self.validate()
        self.assertFalse(result.ok)
        self.assertTrue(any("Mirror your human's language" in e for e in result.errors))

    def test_an_import_in_the_threshold_fails(self) -> None:
        self.make_repo()
        threshold = self.repo / "CLAUDE.md"
        threshold.write_text(threshold.read_text() + "\n@identity/personality.md\n")
        result = self.validate()
        self.assertFalse(result.ok)
        self.assertTrue(any("pasted into the prompt" in e for e in result.errors))

    def test_a_dead_router_link_fails(self) -> None:
        self.make_repo()
        threshold = self.repo / "CLAUDE.md"
        threshold.write_text(threshold.read_text() + "\n[gone](memory/nowhere.md)\n")
        result = self.validate()
        self.assertFalse(result.ok)
        self.assertTrue(any("nowhere.md" in e for e in result.errors))

    def test_half_resolved_placeholders_fail(self) -> None:
        self.make_repo()
        threshold = self.repo / "CLAUDE.md"
        threshold.write_text(threshold.read_text().replace("{{AGENT_NAME}}", "TARS"))
        result = self.validate()
        self.assertFalse(result.ok)
        self.assertTrue(any("Half-awakened" in e for e in result.errors))

    def test_a_broken_agents_link_fails(self) -> None:
        self.make_repo()
        agents = self.repo / "AGENTS.md"
        agents.unlink()
        agents.write_text("something else entirely")
        result = self.validate()
        self.assertFalse(result.ok)
        self.assertTrue(any("AGENTS.md" in e for e in result.errors))


class TestLocalBlocks(TarsTestCase):
    UPSTREAM = (
        "# Threshold v2\n"
        "new law\n"
        "<!-- tars:local:router -->\n"
        "| default | row |\n"
        "<!-- /tars:local -->\n"
        "tail\n"
    )

    def test_a_local_block_survives_an_upstream_rewrite(self) -> None:
        local = self.UPSTREAM.replace("| default | row |", "| mine | opened when X |")
        merged, orphans = tars.apply_blocks(self.UPSTREAM, tars.extract_blocks(local))
        self.assertIn("| mine | opened when X |", merged)
        self.assertIn("new law", merged)
        self.assertEqual(orphans, [])

    def test_a_block_upstream_dropped_is_reported_not_swallowed(self) -> None:
        local = self.UPSTREAM + "<!-- tars:local:triggers -->\nmine\n<!-- /tars:local -->\n"
        merged, orphans = tars.apply_blocks(self.UPSTREAM, tars.extract_blocks(local))
        self.assertEqual(orphans, ["triggers"])
        self.assertNotIn("triggers", merged)

    def test_extract_finds_every_named_block(self) -> None:
        blocks = tars.extract_blocks(self.UPSTREAM)
        self.assertEqual(list(blocks), ["router"])

    def test_the_shipped_threshold_has_local_blocks(self) -> None:
        blocks = tars.extract_blocks((TEMPLATE / "CLAUDE.md").read_text())
        self.assertTrue(blocks, "the template threshold must expose local blocks or sync cannot merge it")


class TestSync(TarsTestCase):
    """The state machine. Each test pins one branch of classify()."""

    def setUp(self) -> None:
        super().setUp()
        self.make_repo()
        self.upstream = self.fork_template()

    def bump_upstream(self, rel: str, text: str) -> None:
        target = tars.upstream_path(rel, self.upstream)
        target.write_text(target.read_text() + text)

    def run_sync(self, **overrides) -> tars.Result:
        return tars.cmd_sync(sync_args(self.repo, self.upstream, **overrides))

    def test_no_upstream_change_is_a_no_op(self) -> None:
        result = self.run_sync()
        self.assertTrue(result.ok)
        self.assertFalse(result.actions)
        self.assertNotIn("conflict", result.data)

    def test_an_untouched_file_takes_the_update(self) -> None:
        self.bump_upstream("protocols/ouroboros.md", "\nA fifth step.\n")
        result = self.run_sync()
        self.assertTrue(result.ok)
        self.assertIn("A fifth step.", (self.repo / "protocols/ouroboros.md").read_text())
        self.assertIn("protocols/ouroboros.md", result.data["update"])

    def test_the_manifest_follows_the_update(self) -> None:
        self.bump_upstream("protocols/context.md", "\nnew paragraph\n")
        self.run_sync()
        recorded = tars.read_manifest(self.repo)["files"]["protocols/context.md"]
        self.assertEqual(recorded, tars.sha(self.repo / "protocols/context.md"))
        self.assertFalse(self.run_sync().actions, "a second sync should be a no-op")

    def test_a_file_the_human_edited_is_never_overwritten(self) -> None:
        local = self.repo / "protocols/confidentiality.md"
        local.write_text(local.read_text() + "\nMy own lock: never mention the cat.\n")
        mine = local.read_text()
        self.bump_upstream("protocols/confidentiality.md", "\nUpstream added a lock.\n")

        result = self.run_sync()

        self.assertEqual(local.read_text(), mine, "sync clobbered a file its human had edited")
        self.assertIn("protocols/confidentiality.md", result.data["conflict"])
        side = self.repo / "protocols/confidentiality.md.upstream"
        self.assertTrue(side.is_file())
        self.assertIn("Upstream added a lock.", side.read_text())
        self.assertTrue(any("both sides" in w for w in result.warnings))

    def test_a_local_edit_upstream_has_not_touched_is_left_alone(self) -> None:
        local = self.repo / "protocols/context.md"
        local.write_text(local.read_text() + "\nmine only\n")
        result = self.run_sync()
        self.assertIn("mine only", local.read_text())
        self.assertIn("protocols/context.md", result.data["local-only"])
        self.assertFalse((self.repo / "protocols/context.md.upstream").exists())

    def test_a_deleted_file_is_restored(self) -> None:
        (self.repo / "protocols/security-pass.md").unlink()
        result = self.run_sync()
        self.assertTrue((self.repo / "protocols/security-pass.md").is_file())
        self.assertIn("protocols/security-pass.md", result.data["missing"])

    def test_an_unmanaged_file_is_flagged_not_overwritten(self) -> None:
        """A repo predating the manifest, or one whose manifest lost an entry."""
        manifest = tars.read_manifest(self.repo)
        del manifest["files"]["protocols/ouroboros.md"]
        tars.write_manifest(self.repo, manifest)
        local = self.repo / "protocols/ouroboros.md"
        local.write_text("hand written\n")
        self.bump_upstream("protocols/ouroboros.md", "\nchanged\n")

        result = self.run_sync()

        self.assertEqual(local.read_text(), "hand written\n")
        self.assertIn("protocols/ouroboros.md", result.data["unknown"])

    def test_dry_run_changes_nothing(self) -> None:
        self.bump_upstream("protocols/ouroboros.md", "\nA fifth step.\n")
        before = tars.sha(self.repo / "protocols/ouroboros.md")
        result = self.run_sync(dry_run=True)
        self.assertIn("protocols/ouroboros.md", result.data["update"])
        self.assertEqual(before, tars.sha(self.repo / "protocols/ouroboros.md"))

    def test_the_threshold_keeps_local_content_across_an_update(self) -> None:
        threshold = self.repo / "CLAUDE.md"
        text = threshold.read_text()
        blocks = tars.extract_blocks(text)
        self.assertTrue(blocks)
        name = next(iter(blocks))
        marker = "| my-file.md | opened when I say so |"
        threshold.write_text(text.replace(blocks[name], blocks[name] + marker + "\n"))

        upstream_threshold = self.upstream / "CLAUDE.md"
        upstream_threshold.write_text(upstream_threshold.read_text() + "\nAn upstream rule.\n")

        self.run_sync()

        merged = threshold.read_text()
        self.assertIn(marker, merged, "sync dropped the human's router rows")
        self.assertIn("An upstream rule.", merged, "sync did not take the upstream change")

    def test_the_tool_updates_itself(self) -> None:
        tool = tars.upstream_path("tools/tars.py", self.upstream)
        tool.write_text(tool.read_text() + "\n# upstream marker\n")
        self.run_sync()
        self.assertIn("# upstream marker", (self.repo / "tools/tars.py").read_text())


class TestDoctor(TarsTestCase):
    def doctor(self) -> tars.Result:
        return tars.cmd_doctor(Namespace(path=str(self.repo), home=str(self.home), json=True))

    def test_reports_a_never_woken_repo_as_broken(self) -> None:
        self.make_repo()
        result = self.doctor()
        self.assertFalse(result.ok)
        self.assertFalse(result.data["awakened"])
        self.assertTrue(result.data["claude_wired"])
        self.assertTrue(result.data["codex_wired"])

    def test_reports_an_unwired_install(self) -> None:
        self.make_repo(no_wire=True)
        result = self.doctor()
        self.assertFalse(result.data["claude_wired"])
        self.assertTrue(any("wakes up as nobody" in e for e in result.errors))

    def test_reports_local_drift(self) -> None:
        self.make_repo()
        local = self.repo / "protocols/ouroboros.md"
        local.write_text(local.read_text() + "\nmine\n")
        result = self.doctor()
        self.assertEqual(result.data["locally_modified"], ["protocols/ouroboros.md"])

    def test_no_repo_is_an_error_not_a_crash(self) -> None:
        result = tars.cmd_doctor(Namespace(path=str(self.tmp / "nothing"), home=str(self.home), json=True))
        self.assertFalse(result.ok)
        self.assertTrue(any("run tars init" in e for e in result.errors))


class TestEndToEnd(TarsTestCase):
    def test_the_hook_blocks_a_commit_that_breaks_an_invariant(self) -> None:
        self.make_repo()
        run = lambda *a: subprocess.run(["git", "-C", str(self.repo), *a],
                                        capture_output=True, text=True)
        run("config", "user.email", "t@example.com")
        run("config", "user.name", "Test")
        run("add", "-A")
        self.assertEqual(run("commit", "-m", "first").returncode, 0)

        threshold = self.repo / "CLAUDE.md"
        threshold.write_text(threshold.read_text().replace("FIX THE PRODUCER", "do stuff"))
        run("add", "-A")
        blocked = run("commit", "-m", "break it")

        self.assertNotEqual(blocked.returncode, 0, "the hook let a broken threshold through")
        self.assertIn("FIX THE PRODUCER", blocked.stdout + blocked.stderr)

    def test_the_cli_runs_as_a_subprocess(self) -> None:
        self.make_repo()
        done = subprocess.run(
            [sys.executable, str(ROOT / "tools/tars.py"), "--json", "validate", str(self.repo)],
            capture_output=True, text=True,
        )
        payload = json.loads(done.stdout)
        self.assertTrue(payload["ok"], payload["errors"])
        self.assertEqual(payload["data"]["rules_checked"], len(tars.REQUIRED_RULES))


class TestDiscovery(TarsTestCase):
    """An agent handed nothing but a git URL does not know where the memory lives.
    Everything here exists so it never has to ask."""

    def doctor(self, path=None) -> tars.Result:
        return tars.cmd_doctor(Namespace(path=path, home=str(self.home), json=True))

    def test_doctor_finds_the_repo_through_the_claude_wiring(self) -> None:
        self.make_repo()
        result = self.doctor()
        self.assertEqual(result.data["repo"], str(self.repo.resolve()))
        self.assertTrue(result.data["awakened"] is False or "awakened" in result.data)

    def test_doctor_falls_back_to_the_codex_symlink(self) -> None:
        self.make_repo()
        (self.home / ".claude/CLAUDE.md").unlink()
        self.assertEqual(tars.locate_repo(None, self.home), self.repo.resolve())

    def test_doctor_says_so_instead_of_guessing_when_nothing_is_wired(self) -> None:
        result = tars.cmd_doctor(Namespace(path=str(self.tmp / "nowhere"),
                                           home=str(self.home), json=True))
        self.assertFalse(result.ok)
        self.assertFalse(result.data["awakened"])

    def test_an_explicit_path_always_wins_over_the_wiring(self) -> None:
        self.make_repo()
        elsewhere = self.tmp / "elsewhere"
        self.assertEqual(tars.locate_repo(str(elsewhere), self.home), elsewhere.resolve())

    def test_the_version_comes_from_a_file_no_harness_owns(self) -> None:
        self.assertEqual(tars.plugin_version(TEMPLATE), (ROOT / "VERSION").read_text().strip())


class TestBootstrapDocs(unittest.TestCase):
    """A git URL is the only thing TARS asks for. These pin the places that could quietly
    stop being true: a skill that only works once a plugin is installed, or a second
    source path that leaves two clones on disk disagreeing about the version."""

    SOURCE = "$HOME/.tars/src"
    CLONE = "https://github.com/michelgrolet/tars.git"

    def skills(self) -> list[Path]:
        return sorted((ROOT / "skills").glob("*/SKILL.md"))

    def test_the_bootstrap_file_stands_on_its_own(self) -> None:
        text = (ROOT / "AGENTS.md").read_text()
        self.assertIn(self.CLONE, text)
        self.assertIn("tools/tars.py", text)
        self.assertIn("skills/awaken/SKILL.md", text)

    def test_no_skill_needs_a_harness_to_find_its_source(self) -> None:
        for skill in self.skills():
            text = skill.read_text()
            if "CLAUDE_PLUGIN_ROOT" not in text:
                continue
            self.assertIn(self.SOURCE, text,
                          f"{skill.parent.name} uses CLAUDE_PLUGIN_ROOT with no git fallback")

    def test_every_source_path_is_the_same_one(self) -> None:
        stale = [p.name for p in (ROOT / "AGENTS.md", ROOT / "README.md", *self.skills())
                 if ".cache/tars" in p.read_text()]
        self.assertEqual(stale, [], f"an older source path survives in {stale}")

    def test_the_readme_leads_with_the_url_not_with_a_vendor(self) -> None:
        head = (ROOT / "README.md").read_text().split("## The problem")[0]
        self.assertIn("github.com/michelgrolet/tars", head)
        self.assertLess(head.index("github.com/michelgrolet/tars"), head.index("claude plugin"),
                        "the Claude Code shortcut is listed above the git URL")


class TestRegistry(unittest.TestCase):
    """extensions/registry.json is the source of truth and the marketplace is a projection
    of it. Two files saying the same thing drift the week nobody is looking, so the drift
    is a build failure rather than a convention."""

    def setUp(self) -> None:
        sys.path.insert(0, str(ROOT / "tools"))
        import registry  # noqa: PLC0415

        self.registry = registry
        self.data = registry.load()

    def test_the_marketplace_is_exactly_what_the_registry_projects(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            drifted = self.registry.main(["--check"])
        self.assertEqual(drifted, 0, "run: python3 tools/registry.py --write")

    def test_every_extension_says_what_it_needs_to_run(self) -> None:
        for ext in self.data["extensions"]:
            req = ext["requires"]
            self.assertIn("database", req, ext["name"])
            self.assertIsInstance(req["always_on"], bool, ext["name"])
            self.assertIsInstance(req["credentials"], list, ext["name"])
            self.assertTrue(self.registry.needs(ext), ext["name"])

    def test_the_harness_itself_requires_nothing(self) -> None:
        """The whole promise is markdown and git on your own disk. The day TARS needs a
        database, a host or a credential, it has become someone else's product."""
        req = next(e for e in self.data["extensions"] if e["name"] == "tars")["requires"]
        self.assertIsNone(req["database"])
        self.assertFalse(req["always_on"])
        self.assertEqual(req["credentials"], [])

    def test_an_extension_that_needs_nothing_says_so_in_words(self) -> None:
        tars_entry = next(e for e in self.data["extensions"] if e["name"] == "tars")
        self.assertIn("runs where your agent runs", self.registry.needs(tars_entry))

    def test_a_hosted_extension_warns_that_a_laptop_will_not_do(self) -> None:
        hosted = dict(requires={"database": None, "always_on": True, "credentials": []})
        self.assertIn("stays awake", self.registry.needs(hosted))

    def test_the_projection_drops_fields_claude_code_would_warn_about(self) -> None:
        projected = self.registry.project(self.data)
        for entry in projected["plugins"]:
            self.assertNotIn("requires", entry)
            self.assertNotIn("provides", entry)


class TestMarketplace(unittest.TestCase):
    """The registry is the only thing standing between someone and code that runs with
    their agent's permissions, so a malformed entry has to fail here rather than at install."""

    REQUIRED = ("name", "description", "author", "category", "source", "homepage")
    REMOTE_KINDS = ("url", "git-subdir", "github")

    def setUp(self) -> None:
        self.plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        self.market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.entries = self.market["plugins"]

    def test_every_entry_carries_the_fields_a_reader_needs(self) -> None:
        for entry in self.entries:
            for field in self.REQUIRED:
                self.assertIn(field, entry, f"{entry.get('name', '?')} is missing {field}")

    def test_names_are_unique(self) -> None:
        names = [entry["name"] for entry in self.entries]
        self.assertEqual(len(names), len(set(names)), f"duplicate plugin name in {names}")

    def test_local_sources_are_on_disk_and_declare_themselves(self) -> None:
        for entry in self.entries:
            source = entry["source"]
            if not isinstance(source, str):
                continue
            manifest = ROOT / source / ".claude-plugin/plugin.json"
            self.assertTrue(manifest.is_file(), f"{entry['name']} points at {source}, no manifest there")
            self.assertEqual(json.loads(manifest.read_text())["name"], entry["name"])

    def test_remote_sources_use_a_shape_this_claude_code_resolves(self) -> None:
        # 'git' is not implemented by the CLI and 'github' fails to clone: both were tested
        # against a live install, and both fail with an error that reads like a permissions problem.
        for entry in self.entries:
            source = entry["source"]
            if isinstance(source, str):
                continue
            self.assertIn(source["source"], ("url", "git-subdir"),
                          f"{entry['name']} uses source kind {source['source']!r}")
            self.assertTrue(source["url"].startswith("https://"), source["url"])

    def test_the_plugin_manifest_mirrors_VERSION_rather_than_owning_it(self) -> None:
        self.assertEqual(self.plugin["version"], (ROOT / "VERSION").read_text().strip())

    def test_the_marketplace_agrees_with_the_plugin_it_ships(self) -> None:
        own = [entry for entry in self.entries if entry["name"] == self.plugin["name"]]
        self.assertEqual(len(own), 1, "tars indexes itself exactly once")
        self.assertEqual(own[0]["description"], self.plugin["description"])

    def test_declared_skill_directories_hold_real_skills(self) -> None:
        for declared in self.plugin["skills"]:
            root = ROOT / declared
            self.assertTrue(root.is_dir(), f"{declared} is declared and absent")
            found = sorted(p for p in root.iterdir() if p.is_dir())
            self.assertTrue(found, f"{declared} is empty")
            for skill in found:
                self.assertTrue((skill / "SKILL.md").is_file(), f"{skill.name} has no SKILL.md")

    def test_the_extensions_directory_documents_the_rule(self) -> None:
        readme = (ROOT / "extensions/README.md").read_text()
        for entry in self.entries:
            if entry["name"] == self.plugin["name"]:
                continue
            self.assertIn(entry["name"], readme, f"{entry['name']} is indexed and undocumented")


if __name__ == "__main__":
    unittest.main()
