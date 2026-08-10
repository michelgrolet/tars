# You were handed this repo

Someone gave you this git URL and asked you to set it up. This file is your instruction sheet. It works in any agent that can run `git` and `python3`: Claude Code, Codex, Cursor, Aider, a plain shell.

**Read this whole file before running anything.** Then do the four steps below in order, in one turn, without asking the human to run commands themselves.

## 1. Get the source

```bash
TARS_SRC="$HOME/.tars/src"
if [ -d "$TARS_SRC/.git" ]; then git -C "$TARS_SRC" pull -q --ff-only
else git clone -q https://github.com/michelgrolet/tars.git "$TARS_SRC"; fi
python3 "$TARS_SRC/tools/tars.py" --version
```

This directory is upstream's copy. It is read-only as far as the human is concerned, and it is not where their memory lives.

## 2. Check nobody lives here yet

```bash
python3 "$TARS_SRC/tools/tars.py" --json doctor 2>/dev/null || echo "no memory yet"
```

If that reports `"awakened": true`, this human already has a memory repo. Say so in one line and stop. Never run the interview over a live memory: it would overwrite who they are with a fresh guess.

## 3. Build their memory repo

Ask one question, in one line, and wait for the answer:

> Where should your memory live? `~/tars` is the default. It just has to be a directory you are happy to commit to.

Then:

```bash
python3 "$TARS_SRC/tools/tars.py" init ~/tars
```

That writes the scaffold, `git init`s it, installs the pre-commit hook, links `AGENTS.md` to `CLAUDE.md` so Codex and Claude read the same law, and points `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` at the new threshold. It backs up whatever it finds first and it is safe to run twice.

## 4. Run the awakening interview

Read `$TARS_SRC/skills/awaken/SKILL.md` and follow it. It is written for you, not for the human. It tells you what to ask, in what order, which files each answer lands in, and what never to invent.

**Do not skip it and write the files from what you already know.** A memory repo full of your assumptions is worse than an empty one: a gap gets filled next week, an invention gets treated as fact forever.

## 5. Put it on their own git

A memory that exists on one disk has a deadline. At the end of the interview:

```bash
cd ~/tars && gh repo create tars --private --source=. --remote=origin --push
```

**Private.** This repo will hold everything they tell you. If `gh` is missing or not logged in, do not hand the human a task list: install it or authenticate it if you can, and if you truly cannot, open `https://github.com/new` in their browser, tell them in one line what to click, and finish the wiring yourself once the remote exists.

## 6. Mention the host once, then drop it

TARS runs on their machine and needs nothing else. Say so, and say what a second machine would add, in one line, without turning it into a step:

> This lives on your laptop. If you ever want it doing things while you sleep, a morning digest, a nightly cleanup, an always-connected messaging account, that wants a machine that stays awake: a small VPS, a Raspberry Pi, an old laptop. Same repo, cloned twice, same remote. Say the word whenever.

**Do not set one up now, do not ask which one they would pick, do not list providers.** They asked for a memory, not for infrastructure. The moment it becomes worth it is when they install an extension that needs it, and `/tars-extend` handles that conversation with a concrete reason in hand.

## After that

The skills in `$TARS_SRC/skills/` are the interface. Read the one whose `description` matches what the human asks for:

| Skill | Fires when they say |
|---|---|
| `awaken` | set yourself up, give yourself a memory |
| `remember` | remember this, don't forget that I… |
| `consolidate` | your memory is a mess, or every few weeks |
| `tars-update` | get the latest, or on a schedule |
| `tars-doctor` | why don't you remember me, is my memory saved |
| `tars-extend` | add a skill for this, connect yourself to X |

If your harness has a native skill mechanism, install them into it so they fire on their own. On Claude Code that is `claude plugin marketplace add michelgrolet/tars && claude plugin install tars@tars`, and it is a convenience, not a requirement: nothing in TARS needs it. Everywhere else, copy `skills/` where your harness looks for skills, or just read the file when the moment comes.

## What you are looking at

`template/` is what a memory repo starts as. `tools/tars.py` is the whole implementation, standard library only. `protocols/` inside the template holds the law the agent runs on, and `protocols/ouroboros.md` is the one that matters: every action ends by repairing the file that will emit the same mistake next week.
