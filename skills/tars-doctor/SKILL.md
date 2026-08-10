---
name: tars-doctor
description: Diagnose and repair a TARS install. Use when the agent seems to have forgotten everything, when a session wakes up blank, when the human asks is TARS working, why don't you remember me, is my memory saved, or before trusting anything else in this repo.
---

# /tars-doctor

Something is off, or they want to know it isn't. Find out, fix what you can, and say plainly what you couldn't.

## 1. Run it

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-$HOME/.cache/tars/src}/tools/tars.py" --json doctor ~/tars
```

Substitute their repo path if it is not `~/tars`. Inside the repo, `python3 tools/tars.py --json doctor .` works too.

## 2. Read the answer

| field | what it means when it is wrong |
|---|---|
| `claude_wired: false` | `~/.claude/CLAUDE.md` does not import the threshold. **This is the one that makes an agent wake up as nobody.** Check it first, every time. |
| `codex_wired: false` | Codex sessions wake up blank. Claude is fine. |
| `awakened: false` | The repo exists but the interview never ran. `/awaken`. |
| `hooks_path` not `.githooks` | Invariants are unguarded: a bad edit to the threshold will commit cleanly and break the next wake. |
| `remote: ""` | The memory exists on one disk only. |
| `uncommitted_files > 0` | Work that is not engraved yet. Between two sessions, only what is committed survives. |
| `locally_modified` non-empty | They edited upstream files. Not a fault, just something sync will hand back to them instead of overwriting. |
| `tars_version` behind | `/tars-update`. |

## 3. Repair

Most of it is one command, and it is safe to run on a live repo:

```bash
python3 "$TARS_SRC/tools/tars.py" init ~/tars
```

`init` is idempotent. It writes only what is missing, re-links `AGENTS.md`, reinstalls the hook, and re-wires both runtimes. It will not touch a file that already exists.

For the rest:

- **No remote** → offer to create one. `gh repo create tars --private --source=. --remote=origin --push`. Private, always.
- **Uncommitted files** → read them first, then commit. Never `git checkout .` on a memory repo; that is somebody's memory you are discarding.
- **`validate` failing** → the error names the rule and why it has to be hot. Restore that line to `CLAUDE.md` rather than deleting the check.

## 4. The failure the tool cannot see

If everything reports green and the agent still behaves like it has no memory, the threshold is loading but nothing under it is. That is almost always one of two things:

- **The router points at files that do not exist**, so every lookup silently returns nothing. `validate` catches this, so re-read its output rather than trusting a green `doctor`.
- **The rule that should have fired is cold.** It is written in a `memory/` or `protocols/` file that nothing tells the agent to open. A rule that is not loaded at the moment of the work does not exist. Move the *trigger* into the threshold and leave the *content* where it is.

That second one is the most common real defect in a mature memory, and no check can find it. The signal is human: the same correction keeps coming back.

## 5. Report

Three lines. What is broken, what you fixed, what needs them. If everything is green, one line and stop.
