---
name: tars-update
description: Pull the latest TARS protocols and tooling into an existing memory repo without touching what the human wrote. Use when they say update TARS, get the latest, pull upstream, am I on the old version, or when tars-doctor reports a version behind. Also the skill to run on a schedule.
---

# /tars-update

Their memory repo is half upstream and half theirs. This brings the upstream half forward and does not touch the rest.

**What is upstream's:** `protocols/`, `tools/tars.py`, the hook, the settings, and the structure of `CLAUDE.md`.
**What is theirs, permanently:** `identity/`, `memory/`, `journal/`, and every `<!-- tars:local:... -->` block in the threshold.

## 1. Fetch upstream

```bash
TARS_SRC="${CLAUDE_PLUGIN_ROOT:-$HOME/.cache/tars/src}"
if [ -d "$TARS_SRC/.git" ]; then git -C "$TARS_SRC" pull -q --ff-only
elif [ ! -d "$TARS_SRC" ]; then git clone -q --depth 1 https://github.com/michelgrolet/tars.git "$TARS_SRC"; fi
```

If the plugin is installed rather than cloned, `claude plugin update tars` refreshes the skills and `${CLAUDE_PLUGIN_ROOT}` already points at the new version. Tell them a restart applies it, once, and move on.

## 2. Look before you write

```bash
cd <their repo> && git status --porcelain
python3 tools/tars.py --json sync . --template "$TARS_SRC/template" --dry-run
```

**Uncommitted work first.** If `git status` is not clean, commit it before syncing. A conflict is much easier to read against a clean tree.

The dry run returns each templated file in one of six states:

| state | what it means | what sync does |
|---|---|---|
| `current` | identical to upstream | nothing |
| `update` | upstream changed, they never touched it | takes the new version |
| `local-only` | they edited it, upstream did not move | leaves it alone |
| `conflict` | both sides changed | writes `<file>.upstream` beside theirs, touches nothing |
| `missing` | deleted locally | restores it |
| `unknown` | no recorded hash, so it cannot be judged | treated as a conflict |

## 3. Apply

```bash
python3 tools/tars.py --json sync . --template "$TARS_SRC/template"
```

## 4. Resolve conflicts by hand, one file at a time

For each `<file>.upstream` it left behind:

```bash
diff -u <file> <file>.upstream
```

Read both. Their edit exists for a reason, so the merge keeps their intent and takes upstream's improvement around it. Then delete the `.upstream` file and re-run sync so the manifest records the resolution.

**Never resolve a conflict by copying `.upstream` over their file.** That is exactly the silent overwrite the whole mechanism exists to prevent.

## 5. Verify and engrave

```bash
python3 tools/tars.py --json doctor . && git add -A && git commit -m "tars: sync to <version>"
```

## 6. Report

Three lines: what came in, what was left alone, and what still needs their eyes. If nothing changed, one line: already current at `<version>`.

## Running it on a schedule

Once a week is enough; upstream protocols do not move fast. If their harness can schedule work, schedule this skill rather than a raw command, so a conflict gets read by someone instead of piling up. **A scheduled run stops at step 4 and reports.** Never auto-resolve a conflict in a run they are not watching.
