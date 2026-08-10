---
name: tars-extend
description: Add a capability to the agent. Installs a Claude Code plugin or MCP server, or authors a new skill in the human's own memory repo, and wires the trigger into the threshold so it actually fires. Use when they say add a skill, install a plugin, teach you to do X, connect you to Y, make a command for this, or when the same manual routine has come up three times.
---

# /tars-extend

They want the agent to be able to do something it cannot do yet. Three shapes, and picking the right one is most of the job.

| What they want | Shape |
|---|---|
| A capability someone else already built | An existing plugin or MCP server. Install it. |
| A routine of theirs, repeated, with their own steps in it | A skill in their memory repo. Write it. |
| Something the agent should do without being asked | A trigger in the threshold. One line. |

**Do not write a skill for something a plugin already does.** Look first.

## Installing something that exists

The extensions built for a memory are indexed in `extensions/README.md` upstream, each with a git URL. `people-memory` is the one to reach for the moment they want the agent to remember people: a private graph with `search_people`, `remember_person`, `add_fact`, `connect_people` and `find_intro_path`, plus skills that record someone during ordinary conversation.

```bash
claude plugin install people-memory@tars     # Claude Code, one command
```

Anywhere else, clone the extension's repo and follow its own `AGENTS.md` or `README.md`, then add its MCP server the way this harness does it (`claude mcp add`, an entry in a config file, whatever applies here). **Record in `memory/` what it is for and which tools it exposes.** A connector nobody wrote down is a connector nobody uses.

`claude plugin details <name>` shows what a plugin brings and what it costs in context before anything is installed, so read that to them rather than installing blind.

**Two things before installing anything.** Say who wrote it and what it will be able to reach. A plugin runs with the agent's permissions, so "it is on a marketplace" is not a safety statement. A restart is what applies it: say that once, at the end, not as a running commentary.

## Writing a new skill

It lives in **their repo**, at `.claude/skills/<name>/SKILL.md`, so it is versioned with their memory and travels with it.

```markdown
---
name: <verb-or-noun, kebab-case>
description: What it does, and WHEN to use it. Include the phrases they would actually say. This string is the only thing matched against a request, so a vague description means the skill never fires.
---

# /<name>

<One line: what this turn is for.>

## 1. <first real step>
...
```

What makes the difference between a skill that fires and one that rots:

- **The description is the trigger.** Write it in their words, not yours. "when they say the deploy is stuck" beats "for deployment troubleshooting".
- **Steps, with the actual commands.** A skill that says "check the config" is a note to self. One that says `cat ~/.foo/config.toml` is a skill.
- **Say what not to do.** The failure modes you already know are the most valuable lines in the file.
- **Verify before it closes.** A skill with no check at the end has no idea whether it worked.
- **Test it before you claim it works.** Run each command. An untested skill is a guess that will fail in front of them.

## Adding a trigger

For anything that should happen without being asked, one line goes inside the `<!-- tars:local:triggers -->` block in `CLAUDE.md`:

```markdown
- <situation, in their words> → **`/<skill>`**
```

**A trigger is allowed to be hot, a content never is.** The line that says *when* to load something must be in the threshold, or it never fires. The thing being loaded stays cold, behind it. If what you are about to add is a paragraph, it belongs in the skill, and the threshold keeps only the pointer.

## Close

```bash
cd <their repo> && python3 tools/tars.py validate . && git add -A && git commit -m "extend: <what it can now do>"
```

Then one line on what it can now do, and one on how to set it off. Nothing about where the file went.
