# extensions/

An extension is a capability the agent gains: an MCP server, a skill pack, a dashboard, a guard.

## Standalone first, TARS optional

**An extension with its own repo must work with no TARS anywhere on the machine.** Someone finds it, clones it, wires it into Codex or Cursor or a script of their own, and never learns this harness exists. That is the normal case, not the degraded one.

TARS is then one client among several, and what it adds is the part a bare MCP server cannot do for itself: the skills that decide *when* to reach for the tool, and the threshold trigger that makes them fire without being asked. `people-memory` is the proof. Its repo has its own setup wizard, its own Codex and Claude Code instructions, its own tests and its own releases, and the string `tars` appears nowhere in it.

The dependency runs one way. This registry points at extensions; no extension points back at a harness it needs.

The one exception is an extension that lives in this directory. It has no repo to clone and no life without TARS, and that is the only thing that earns it a place in-tree.

```bash
python3 tools/registry.py
```

prints the install path for each one, and for anything with its own repo that path is a `git clone` and nothing else. A test fails the build if an externally-hosted extension is ever listed with only a TARS-shaped way in.

## What each one costs to run

Half of these speak to something that has to exist before they are useful. That belongs in the index, not in a paragraph someone finds after installing:

```bash
python3 tools/registry.py
```

```
tars           https://github.com/michelgrolet/tars
               needs: nothing, it runs where your agent runs
people-memory  https://github.com/michelgrolet/people-memory-mcp
               needs: a postgres to point it at, local or hosted
location-memory  https://github.com/michelgrolet/tars-location-mcp
               needs: a postgres to point it at, local or hosted
```

Three independent requirements, because they fail differently:

| `requires` | What it means | What it costs you |
|---|---|---|
| `database` | It stores something durable | A local Postgres in Docker, or a free hosted project. Both work. |
| `always_on` | It holds a session, a listener, or a schedule | A machine that does not sleep. A laptop will not do, and this is the only one that means a server. |
| `credentials` | It speaks to an account that is yours | An OAuth grant or a token you obtain yourself. Nobody else can do it for you. |

**A database is not a server.** Most extensions that need Postgres run perfectly against `docker run postgres` on the same laptop as the agent. The one requirement that genuinely means a machine somewhere else is `always_on`, and it is the rarest.

## When a host is worth it

**TARS never needs one.** The harness is markdown and git on your own disk, and it stays that way. Nothing below is a prerequisite for anything above.

A host earns its place the day one of these is true:

- an extension holds a **session** that dies with your laptop: a linked messaging account, a webhook listener, an inbox watcher;
- you want something to run **while you are asleep**: a morning digest, a nightly consolidation, a scheduled `/tars-update`;
- you want the same memory reachable from **more than one machine**, without one of them having to be awake.

A host means whatever does not sleep: a five-dollar VPS, a Raspberry Pi on a shelf, an old laptop with the lid open. The agent is the same agent, the repo is the same repo, cloned twice and pushed to the same remote.

**Suggest it when the reason appears, never at install.** An agent that opens with "first, rent a server" has lost most of the people it was talking to. An agent that says "this one needs a machine that stays awake, here is what that means, and here is the version that runs on your laptop instead" has kept them.

Extensions that share the same `database` value can point at the same instance: one Postgres, several schemas, one connection string in your environment. That is why the field names the engine rather than a service.

## Installing one, in any agent

`extensions/registry.json` is the index and the source of truth. Every entry carries a name, a description, a git URL and what it needs, so an agent that has never heard of Claude Code can read it and decide:

```bash
curl -s https://raw.githubusercontent.com/michelgrolet/tars/main/extensions/registry.json
```

Clone the one you want and follow its own `AGENTS.md` or `README.md`. An extension is responsible for saying how it is wired, because only it knows what it talks to.

On Claude Code the same list is also a marketplace, so one command does the clone and the wiring:

```bash
claude plugin marketplace add michelgrolet/tars
claude plugin install people-memory@tars
```

`.claude-plugin/marketplace.json` is generated from the registry, never edited by hand, and a test fails the build if the two drift. It carries the subset Claude Code understands: the CLI warns on fields it does not know, and a repo that warns on every validate run teaches people to ignore its own tooling.

```bash
python3 tools/registry.py --write     # after editing the registry
python3 tools/registry.py --check     # what CI runs
```

That marketplace is a shortcut, not the contract. The contract is the git URL.

## Where an extension lives

**The registry lives here. Most of the code does not.**

| The extension | Where it lives | `source` |
|---|---|---|
| Has its own tests, releases, licence, or users who do not use TARS | Its own repo | `{"source": "url", "url": "https://github.com/owner/repo.git"}` |
| Is a skill pack with no code of its own, useful only next to TARS | This directory | `"./extensions/<name>"` |

The rule that decides it: **would this repo be worth reading on its own?** `people-memory` is a Postgres product with a dashboard and a test suite. Vendoring it here would bury it and force its releases to travel through TARS. A three-file skill pack for a niche workflow has no such life, and a separate repo for it is a repo nobody stars and nobody updates.

**A shared database is not a reason to share a repo.** Several extensions can point at the same Postgres and still ship separately: a people graph and a location history hold different data, break differently, and interest different people. One repo each, one schema each, one connection string in the environment. The moment two extensions live in one repo, the smaller one's releases wait on the larger one's, and nobody can adopt one without the other.

The exception is an extension that is **useless alone**: a dashboard over another extension's schema, or a migration tool that only means something next to it. That belongs in the repo it reads, as a directory, indexed with `git-subdir` if it deserves its own entry at all.

## Adding one

1. The extension needs a git URL that clones without credentials, and a `README.md` or `AGENTS.md` at its root saying how to wire it. That is the whole requirement.
2. If you also want it installable in one command on Claude Code, give it `.claude-plugin/plugin.json`: `name`, `version`, `description`, and whichever of `skills`, `mcpServers`, `hooks`, `agents` it provides. `claude plugin validate <path>` checks it.
3. Add an entry to `extensions/registry.json` with `name`, `description`, `repo`, `source`, `category`, `license`, `provides` and `requires`. Fill `requires` honestly: a `database` someone discovers after installing is a bad afternoon, and an `always_on` they discover after installing is a bad week.
4. `python3 tools/registry.py --write`, then `python3 -m unittest discover -s tools/tests`. The suite fails on a missing field, a duplicate name, a local source that is not on disk, a source kind Claude Code cannot resolve, a marketplace that drifted from the registry, or an extension indexed and left out of the list below.
5. Install it and read what actually loaded before claiming it works. `claude plugin details <name>@tars` reports the skills, the MCP servers and the tokens it costs on every session.

## Pinning

Entries track their default branch, so an update picks up improvements. Pin a `commit` in the source when an extension is not yours and you want to read a diff before your agent runs it.

## Current extensions

- **[people-memory](https://github.com/michelgrolet/people-memory-mcp)**, a private people graph. Six MCP tools (`search_people`, `get_person`, `remember_person`, `add_fact`, `connect_people`, `find_intro_path`) and six skills that record people during ordinary conversation. Needs a Postgres, runs on your laptop against one in Docker. MIT.
- **[location-memory](https://github.com/michelgrolet/tars-location-mcp)**, a private location archive. Fourteen MCP tools over stays, cities, countries, trips, journeys and records, plus `location_coverage`, which reports the holes in the archive so the agent stops answering "you were never there" when the truth is "nothing was recorded then". Two skills. Needs a Postgres, runs on your laptop against one in Docker. MIT.
- **[srs](https://github.com/michelgrolet/srs)**, one simple stack of spaced-repetition cards shared by a minimal web app and an MCP server. Ten tools create, edit, search, delete and review cards from chat; FSRS schedules them and the tag flow pushes agents to reuse existing categories. One skill. Needs GitHub authentication with access to the card repository. MIT.

The two share nothing but a database engine, and each is installable without the other. `location-memory` can link a trip to a person, and does it through an optional migration that refuses to install unless a `people` table already exists.
