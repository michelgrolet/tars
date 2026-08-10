# Changelog

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
