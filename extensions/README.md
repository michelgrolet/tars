# extensions/

An extension is a capability the agent gains: an MCP server, a skill pack, a dashboard, a guard. They are installed with one command and they update on their own schedule.

```bash
claude plugin marketplace add michelgrolet/tars
claude plugin install people-memory@tars
```

## Where an extension lives

**The registry lives here. Most of the code does not.**

`.claude-plugin/marketplace.json` is an index. Each entry names a plugin and says where to fetch it from. Two shapes:

| The extension | Where it lives | `source` |
|---|---|---|
| Has its own tests, releases, licence, or users who do not use TARS | Its own repo | `{"source": "url", "url": "https://github.com/owner/repo.git"}` |
| Is a skill pack with no code of its own, useful only next to TARS | This directory | `"./extensions/<name>"` |

Anthropic's own marketplace mixes both the same way: local paths for what it maintains, remote URLs for the 200-odd plugins it merely indexes.

The rule that decides it: **would this repo be worth reading on its own?** `people-memory` is a Postgres product with a dashboard and a test suite. Vendoring it here would bury it and force its releases to travel through TARS. A three-file skill pack for a niche workflow has no such life, and a separate repo for it is a repo nobody stars and nobody updates.

## Adding one

1. The extension needs `.claude-plugin/plugin.json` at its root: `name`, `version`, `description`, and whichever of `skills`, `mcpServers`, `hooks`, `agents` it provides. `claude plugin validate <path>` checks it.
2. Add an entry to `.claude-plugin/marketplace.json` with `name`, `description`, `author`, `category`, `license`, `homepage` and `source`.
3. `python3 -m unittest discover -s tools/tests`. `TestMarketplace` fails on a missing field, a duplicate name, a local source that is not on disk, a source kind this Claude Code cannot resolve, or an extension indexed here and left out of the list below.
4. Install it from the marketplace and read `claude plugin details <name>@tars` before claiming it works. The inventory tells you what actually loaded and what it costs in tokens on every session.

## Pinning

Entries here track their default branch, so `claude plugin update` picks up improvements. Pin a `commit` in the source when an extension is not yours and you want to read a diff before your agent runs it.

## Current extensions

- **[people-memory](https://github.com/michelgrolet/people-memory-mcp)**, a private people graph. Six MCP tools (`search_people`, `get_person`, `remember_person`, `add_fact`, `connect_people`, `find_intro_path`) and six skills that record people during ordinary conversation. Postgres, self-hostable. MIT.
