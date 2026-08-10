# Changelog

## 1.4.0

Security. A memory repo is written by an agent that never asks permission to commit, and pushed to a remote. Two failures follow from that, and both are now enforced by code rather than by asking a model nicely.

- **A credential cannot leave the machine through the repo.** `tars validate` scans every file git would carry for vendor-issued key shapes and refuses, from both the pre-commit and the new pre-push hook. It reports the file and the line, never the value. Only fixed vendor prefixes, because a scanner that cries wolf on prose gets disabled inside a week. Per-line escape hatch: `tars:allow-secret`.
- **A public memory repo fails `tars doctor`.** It asks the forge for the repo's real visibility instead of trusting a decision made months ago. `unknown` when the host is not GitHub, and `unknown` never fails.
- The shipped `.gitignore` keeps `.env`, keys, certificates and `credentials.json` from ever being tracked.
- [`SECURITY.md`](SECURITY.md): the threat model, what is enforced by code, what is discipline, and an explicit list of what is not defended.
- CI: the smoke job plants a credential and asserts it survives neither the commit nor a `--no-verify` push; a new `secrets` job runs the scanner over this repo's working tree and every blob in its history.

## 1.3.0

- A host is suggested, never required. The bootstrap mentions once what a machine that stays awake would add and then drops it; `/tars-extend` raises it only when an extension actually needs one, with the laptop-only alternative in the same breath. A test fails the build the day TARS's own `requires` stops being empty.
- One extension per repo, even when several share a database: a people graph and a location history hold different data and break differently, and a shared repo makes the smaller one's releases wait on the larger one's.
- `extensions/registry.json` is the index and the source of truth: a git URL per extension, plus what it needs before it is any use. `tools/registry.py` projects it into `.claude-plugin/marketplace.json`, and a test fails the build when the two drift.
- Requirements are three independent fields, because they fail differently. `database` is a Docker container on the same laptop. `credentials` is an OAuth grant nobody can obtain for you. `always_on` is the only one that means a server.

## 1.2.0

TARS depends on git and nothing else. A harness can make it more convenient; none can be required.

- `AGENTS.md` at the root is the bootstrap. Hand any agent the git URL and one sentence, and it clones the source, runs the interview, builds the memory repo and offers to push it to a private repo of the human's own.
- `tars doctor` with no argument finds the memory repo through the wiring, so an agent that knows only the URL never has to ask where the memory lives.
- The version lives in a plain `VERSION` file that `tars --version` reads. The plugin manifest mirrors it, and a test fails the build if the two disagree.
- The skills fall back to a clone when no plugin root is present. `TestBootstrapDocs` fails the build on a skill that needs a harness to find its source, and on a README that lists a vendor command above the git URL.
- A `bootstrap` CI job clones the commit into a clean directory and installs from the clone.

## 1.1.0

- The marketplace now indexes extensions, not only TARS itself. First one: `people-memory`, a private people graph with six MCP tools and six skills, installed with `claude plugin install people-memory@tars`.
- `extensions/README.md` states where an extension lives: its own repo when it has a life of its own, in-tree when it is a skill pack with no code. `TestMarketplace` fails the build on a missing field, a duplicate name, a local source that is not on disk, or a source kind this Claude Code cannot resolve.
- `/tars-extend` knows the marketplace by name instead of asking the agent to guess where a capability comes from.

## 1.0.0

First release.

- `tars init` builds a memory repo, links `AGENTS.md`, installs the pre-commit hook, and wires the threshold into `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`. Idempotent, backs up whatever it finds, refuses to write into a directory it did not create.
- `tars sync` updates the upstream half of a personalized repo. Three-hash comparison per file, six states, never overwrites a file its human edited. `CLAUDE.md` merges by named local block instead.
- `tars validate` enforces the startup invariants: the rules that must stay hot, no `@import` in the threshold, no dead router link, `AGENTS.md` resolving to `CLAUDE.md`, placeholders fully resolved or fully unresolved. Wired to pre-commit.
- `tars doctor` reports the health of an install end to end, including the two wirings, the hook, the remote, uncommitted memory and local drift.
- Six skills: `awaken`, `remember`, `consolidate`, `tars-update`, `tars-doctor`, `tars-extend`.
- Protocols: the Ouroboros loop with its fix-the-producer step, the cold-loading architecture, confidentiality, and the security pass.
- Ships as a Claude Code plugin and marketplace.
