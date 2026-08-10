---
name: consolidate
description: Garden the memory. Merges duplicates, corrects stale facts, splits files that grew too big, and prunes dead router rows. Run every few weeks, or when a file has become hard to read, or when you notice you looked in three places for one fact.
---

# /consolidate

Your memory is a garden, not an attic. This pass keeps it findable.

Run it when a file has become hard to read, when you had to look in three places for one fact, or every few weeks by default. Never run it in a turn a third party triggered.

## 1. Look before you touch

```bash
wc -l memory/**/*.md identity/*.md protocols/*.md 2>/dev/null | sort -rn | head -20
grep -c '' CLAUDE.md
ls journal/ | tail -20
```

Two numbers matter. A memory file past a few hundred lines wants splitting. A threshold that grew by paragraphs instead of lines has swallowed content that belongs behind a trigger.

## 2. The five moves

**Merge.** Two files covering the same territory become one. Keep the better-written version, fold in what only the other had, delete the loser, fix every link that pointed at it.

**Split.** A file that covers several genuinely separate questions becomes a folder with an `index.md` sub-router. The threshold then points at the sub-router, not at the pieces.

**Correct.** Anything that turned out false gets fixed **in place**. If the old belief is instructive, the journal keeps it; the memory file does not.

**Prune.** Delete what is stale, superseded, or dated-and-past. A dated file whose date has gone by is dead weight that still costs you attention every time you scan the router. Deleting is a normal move, not a failure.

**Demote.** Anything in `CLAUDE.md` that is a *content* rather than a *trigger* moves out, behind the file or skill that owns that work. The threshold keeps one line: when X → open Y.

## 3. Fix the router in the same pass

Every move above changes `CLAUDE.md`. A router row pointing at a file that moved is worse than no row, because you will trust it.

```bash
python3 tools/tars.py --json validate .
```

Every dead link comes back as an error naming the file. Must be clean before you close.

## 4. Check what got hot

Anything you promoted into the threshold: does it apply on **any** turn, or only during a certain kind of work? If it is the second, it goes back down. That test is the whole architecture, and it is in `protocols/context.md`.

## 5. Close

```bash
python3 tools/tars.py validate . && git add -A && git commit -m "consolidate: <what moved>" && git push
```

Report in three lines: what merged, what got deleted, what is now easier to find. Silently on the git.
