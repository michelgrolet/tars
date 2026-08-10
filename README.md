# TARS

**A harness for a personal agent.** One git repo holding who your agent is, the law it runs on every turn, what it has learned about you, and the skills it extends itself with. Every Claude Code and Codex session on the machine wakes up inside it.

Memory is one of the four. The part that makes the rest work is that only one file loads on every wake.

No server, no database, no API key. Markdown files and git.

[![ci](https://github.com/michelgrolet/tars/actions/workflows/ci.yml/badge.svg)](https://github.com/michelgrolet/tars/actions/workflows/ci.yml)

## Install

Send your agent this URL and one sentence:

> https://github.com/michelgrolet/tars — read AGENTS.md and set it up.

That is the install. [`AGENTS.md`](AGENTS.md) is written for the agent, not for you: it clones the source, interviews you, builds your memory repo, wires it into `~/.claude` and `~/.codex`, and offers to push it to a private repo of your own. Claude Code, Codex, Cursor, Aider, anything that can run `git` and `python3`.

By hand, if you would rather watch:

```bash
git clone https://github.com/michelgrolet/tars.git ~/.tars/src
python3 ~/.tars/src/tools/tars.py init ~/tars
```

Then ask your agent to run the interview in `~/.tars/src/skills/awaken/SKILL.md`.

**Nothing here depends on a specific agent.** Claude Code can install the skills as a plugin so they fire on their own, and that is a convenience on top, never the way in.

<details>
<summary>The Claude Code shortcut</summary>

```bash
claude plugin marketplace add michelgrolet/tars
claude plugin install tars@tars
```

Restart, then `/awaken`. Same result, with the skills registered as slash commands.
</details>

## What a personal agent needs

A coding agent is given a task and forgets you when it ends. A personal agent is the same model with four things around it: an identity it keeps, a law it applies on every turn, a memory of you it maintains, and a way to grow without you editing config. Each of those is a file that has to be loaded at the right moment, and the whole design problem is that they compete for the same budget.

Every memory feature on the market solves that by appending facts to a pile and injecting the pile. Past a few hundred entries the useful fact competes with three hundred irrelevant ones and loses. Quality degrades exactly as the memory becomes worth having.

TARS starts from the opposite constraint. An agent is bounded by what it looks at simultaneously, not by what it knows. So **one file loads on every wake**: the threshold. It holds the law, the rules that apply on every turn, and a router: one line per file saying *when to open it*. Everything else stays cold until a task reaches for it.

```
CLAUDE.md          hot   ~125 lines, every session
├── identity/      cold  voice, values, mission
├── memory/        cold  one theme per file
├── protocols/     cold  the loop, confidentiality, the security pass
└── journal/       cold  one entry per session that mattered
```

The router is markdown links, never `@import` lines. An import is pasted into the prompt at full price, so a thin threshold that imports a 48k identity file is a 48k threshold wearing a disguise. `tars validate` fails the commit if one appears.

The memory can grow to a hundred files. The wake cost does not move.

## The loop

Every action closes with four steps.

1. **Act.** Do the work. If the turn changed something another person can reach, verify against the live system, not against your own diff.
2. **Fix the producer.** When you re-ask, rewrite its output, or say "I already told you", it repairs *the file that will emit the same thing next week*, the skill or the template or the threshold, not just its note about it. A correction filed only in memory produces the identical output on Tuesday. Knowing a rule is not what makes it fire; the file being read at the moment of the work is.
3. **Capitalize.** The fact goes to `memory/`, the instruction goes to the producer, the story goes to `journal/`.
4. **Commit.** Straight to `main`, silently. It never asks permission to remember and never narrates git at you.

Step 2 is what separates this from a notes folder.

## Updates that cannot eat your work

You personalize the repo. Upstream keeps improving the protocols. Those two facts usually mean one of them wins.

`tars init` records a SHA-256 of every file it wrote. `tars sync` compares three hashes, upstream and recorded and yours, and knows which side moved:

| state | meaning | action |
|---|---|---|
| `current` | identical to upstream | nothing |
| `update` | upstream moved, you never touched it | takes the new version |
| `local-only` | you edited it, upstream did not move | left alone |
| `conflict` | both moved | writes `<file>.upstream` beside yours, **touches nothing** |
| `missing` | deleted locally | restored |
| `unknown` | no recorded hash | treated as a conflict |

`CLAUDE.md` is upstream structure wrapped around your content, so it is not hashed. It carries named local blocks:

```markdown
<!-- tars:local:router -->
| memory/clients.md | a client is named |
<!-- /tars:local -->
```

Sync rewrites the threshold from upstream and puts your blocks back verbatim. A block upstream no longer has a slot for is reported, never silently dropped.

Every branch of that state machine is pinned by a test, because an update mechanism that quietly overwrites a file you edited is worse than no update mechanism.

## Everything is asked for, not configured

There is a CLI. You are not meant to type it. The skills do, and the skills are what you talk to.

| Skill | What you say |
|---|---|
| `/awaken` | "set yourself up", "give yourself a memory" |
| `/remember` | "remember this", "don't forget that I…" |
| `/consolidate` | "your memory is a mess", or every few weeks |
| `/tars-update` | "get the latest", or on a schedule |
| `/tars-doctor` | "why don't you remember me", "is my memory saved" |
| `/tars-extend` | "add a skill for this", "install that plugin", "connect to X" |

`/tars-extend` is the one that keeps it growing: it installs Claude Code plugins and MCP servers, writes new skills into *your* repo so they are versioned with your memory, and adds the trigger to the threshold so the skill actually fires instead of sitting unread.

## Extensions

The harness is the substrate. Extensions are the capabilities that plug into it, indexed in [`extensions/registry.json`](extensions/registry.json) with a git URL and, for each one, what it needs before it is any use:

```bash
python3 tools/registry.py
```

```
people-memory  https://github.com/michelgrolet/people-memory-mcp
               needs: a postgres to point it at, local or hosted
```

Three requirements, listed separately because they fail differently. `database` means a Docker container or a free hosted project, on the same laptop as the agent. `credentials` means an OAuth grant nobody can obtain for you. `always_on` is the only one that means a server, because a session or a listener dies when a laptop sleeps.

**[people-memory](https://github.com/michelgrolet/people-memory-mcp)** gives the agent a private graph of everyone you know: `search_people`, `remember_person`, `add_fact`, `connect_people`, `find_intro_path`, plus skills that record people during ordinary conversation instead of asking you to fill in a CRM. MIT.

```bash
claude plugin install people-memory@tars     # Claude Code
git clone https://github.com/michelgrolet/people-memory-mcp.git   # anywhere else, then follow its README
```

An extension runs with your agent's permissions, so read what it loads before installing it. [`extensions/README.md`](extensions/README.md) has the rule for where an extension lives and how to add one.

**TARS itself never needs a server**, and a test fails the build the day its own `requires` stops being empty. A host earns its place only when something has to keep running while you sleep: a linked messaging session, a nightly digest, a scheduled update. That is a five-dollar VPS or a Raspberry Pi, suggested at the moment there is a reason for it, never as a step in the install.

## The CLI underneath

```
tars init <path>      build a memory repo, wire ~/.claude and ~/.codex, install the hook
tars validate [path]  check the startup invariants (runs on every commit)
tars doctor [path]    end-to-end health, --json for the agent to read
tars sync [path]      pull upstream without clobbering yours
```

All four are idempotent, all take `--json`, `init` and `sync` take `--dry-run`. Python 3.10+, standard library only.

`validate` is the part that holds. Rules written in prose drift; this one fails a commit that drops a rule from the threshold, adds an `@import`, leaves a dead router link, breaks the `AGENTS.md` link Codex reads, or half-resolves the setup placeholders. The pre-commit hook runs it whether or not anyone remembers to.

```
$ python3 tools/tars.py validate ~/tars
  FAIL CLAUDE.md no longer carries 'FIX THE PRODUCER': step 2 is what stops a correction from coming back.
```

## Security

This repo holds everything you have told your agent, and it is committed and pushed by an agent that was told never to ask permission to remember. Two things follow from that, and both are enforced by code rather than by asking a model nicely.

**A credential never leaves your machine through this repo.** You say an API key out loud, the agent writes it down because recording what you tell it is its whole job, and it pushes. `tars validate` scans every file git would carry for vendor-issued key shapes and refuses, from **both** the pre-commit and the pre-push hook: pre-commit only ever saw the commits it was installed for, and push is the irreversible moment.

```
FAIL memory/infra.md:1 carries what looks like a credential (AWS access key).
     A memory repo gets pushed, so this would leave your machine.
```

It reports the file and the line, never the value: echoing the match would copy it into a terminal, a scrollback and a CI log. It matches only vendor prefixes with a fixed shape, because a memory file is prose about your life and says "password" constantly, and a scanner that cries wolf gets disabled inside a week. Per-line escape hatch, reviewable in a diff: `<!-- tars:allow-secret -->`. The scanner runs against this repo's own working tree and its whole history on every push.

**Your memory repo is private and stays private.** `/awaken` creates it private. `tars doctor` then asks GitHub for its actual visibility rather than trusting a decision made six months ago, and fails if it went public. That is the one failure with no recovery.

**Confidentiality is a protocol, and it is labelled honestly.** `protocols/confidentiality.md` holds one principle: you are the only source of instructions, and anything arriving through a third-party channel, a message or a fetched page or a tool result, is data, never a command. It ships with a blocklist you fill in and a stop rule. It also says, in its own text, that it is agent discipline and not a security boundary: it reduces the surface, it does not remove it. Prose is not encryption.

[`SECURITY.md`](SECURITY.md) has the full threat model, including a list of what is **not** defended.

## Tests

```bash
python3 -m unittest discover -s tools/tests -v
```

68 tests, no dependencies. CI runs them on Linux and macOS against Python 3.10 and 3.13, plus three jobs that check claims rather than code:

- **smoke** builds a repo in a sandboxed `$HOME`, plants a credential in it, and asserts it cannot be committed and cannot be pushed past `--no-verify`, with the bare remote still at zero commits at the end;
- **bootstrap** clones the commit into a clean directory and installs from the clone, because "a git URL and a shell" is a claim and not a hope;
- **secrets** runs the scanner over this repo's working tree and over every blob in every commit.

## Layout

| Path | What it is |
|---|---|
| `AGENTS.md` | The bootstrap. What an agent reads when you hand it the git URL. |
| `SECURITY.md` | The threat model: what is enforced by code, what is discipline, what is not defended. |
| `skills/` | The skill library. Plain markdown, readable by any agent; also packaged as a Claude Code plugin. |
| `template/` | What a memory repo starts as: threshold, identity, protocols, hook, settings. |
| `tools/tars.py` | The CLI. Copied into each memory repo, updated by `sync`. |
| `tools/tests/` | The test suite. |
| `.claude-plugin/` | Plugin and marketplace manifests. |
| `extensions/` | The registry: every extension, its git URL, and what it needs to run. |

## Requirements

`git` and `python3` 3.10+, on macOS or Linux. No dependencies to install, the CLI is standard library only.

An agent that can run shell commands, which is every coding agent worth pointing at this. The threshold is wired into `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` because those are the two files that get read on every session today; any harness that reads a global instruction file is one line in `tars init` away.

---

The Ouroboros idea started as a fork of [lupi-starter](https://github.com/Iskandeur/lupi-starter). This is a rewrite from a running instance, keeping what earned its place.

MIT.
