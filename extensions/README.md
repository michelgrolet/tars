# extensions/

An extension is a capability the agent gains: an MCP server, a skill pack, a dashboard, a guard.

## Installing one, in any agent

`.claude-plugin/marketplace.json` is the index. Every entry carries a name, a description and a git URL, so an agent that has never heard of Claude Code can read it and act on it:

```bash
python3 -c "import json,urllib.request as u; \
  [print(p['name'], '\t', p['source'].get('url', p['source']) if isinstance(p['source'],dict) else p['source']) \
   for p in json.load(u.urlopen('https://raw.githubusercontent.com/michelgrolet/tars/main/.claude-plugin/marketplace.json'))['plugins']]"
```

Then clone the one you want and follow its own `AGENTS.md` or `README.md`. An extension is responsible for saying how it is wired, because only it knows whether it needs a database, a token, or nothing.

On Claude Code the same index is a marketplace, so one command does the clone and the wiring:

```bash
claude plugin marketplace add michelgrolet/tars
claude plugin install people-memory@tars
```

That is a shortcut, not the contract. The contract is the git URL.

## Where an extension lives

**The registry lives here. Most of the code does not.**

| The extension | Where it lives | `source` |
|---|---|---|
| Has its own tests, releases, licence, or users who do not use TARS | Its own repo | `{"source": "url", "url": "https://github.com/owner/repo.git"}` |
| Is a skill pack with no code of its own, useful only next to TARS | This directory | `"./extensions/<name>"` |

The rule that decides it: **would this repo be worth reading on its own?** `people-memory` is a Postgres product with a dashboard and a test suite. Vendoring it here would bury it and force its releases to travel through TARS. A three-file skill pack for a niche workflow has no such life, and a separate repo for it is a repo nobody stars and nobody updates.

## Adding one

1. The extension needs a git URL that clones without credentials, and a `README.md` or `AGENTS.md` at its root saying how to wire it. That is the whole requirement.
2. If you also want it installable in one command on Claude Code, give it `.claude-plugin/plugin.json`: `name`, `version`, `description`, and whichever of `skills`, `mcpServers`, `hooks`, `agents` it provides. `claude plugin validate <path>` checks it.
3. Add an entry to `.claude-plugin/marketplace.json` with `name`, `description`, `author`, `category`, `license`, `homepage` and `source`.
4. `python3 -m unittest discover -s tools/tests`. `TestMarketplace` fails on a missing field, a duplicate name, a local source that is not on disk, a source kind Claude Code cannot resolve, or an extension indexed here and left out of the list below.
5. Install it and read what actually loaded before claiming it works. `claude plugin details <name>@tars` reports the skills, the MCP servers and the tokens it costs on every session.

## Pinning

Entries track their default branch, so an update picks up improvements. Pin a `commit` in the source when an extension is not yours and you want to read a diff before your agent runs it.

## Current extensions

- **[people-memory](https://github.com/michelgrolet/people-memory-mcp)**, a private people graph. Six MCP tools (`search_people`, `get_person`, `remember_person`, `add_fact`, `connect_people`, `find_intro_path`) and six skills that record people during ordinary conversation. Postgres, self-hostable. MIT.
