---
name: remember
description: Capitalize something into memory on demand. Use when the human says remember this, retiens, note that, don't forget, or states a durable fact or preference they clearly expect to survive the session. Files it in the right place, adds the router row, and commits.
---

# /remember

The human said something durable. File it so your future self actually reads it.

You normally do this by yourself at the end of a turn, per step 3 of the Ouroboros loop. This skill exists for when they ask explicitly, and for when the thing they said is big enough to deserve a deliberate pass.

## 1. Decide what kind of thing it is

| It is | It goes to |
|---|---|
| A fact about the human | `memory/creator.md`, or the themed file that already covers it |
| A whole new territory | a new `memory/<theme>.md` **plus** one row in the router in `CLAUDE.md` |
| A correction to how you work | the **producer**: the skill, the template, the validator, or `CLAUDE.md`. Not `memory/`. |
| A thing that happened, worth the story | `journal/YYYY-MM-DD-<title>.md` |
| Something about the project you are visiting | that project's repo, never here |

**The distinction that matters.** A fact goes to memory. An instruction about how you should behave goes to the file that will be *loaded at generation time* next time the situation arises. Writing "he hates em dashes" into `memory/` and nothing else guarantees you write an em dash next week. See step 2 of `protocols/ouroboros.md`.

## 2. Check it is not already written

```bash
grep -rin '<a distinctive phrase from the fact>' memory/ identity/ protocols/ CLAUDE.md
```

If it exists and is now wrong, **correct it in place**. Do not append a second version and leave your future self to guess which one won.

If it exists and is right, the fix belongs somewhere else: the rule was written and did not fire. Move it into the file that loads at generation time, or make it mechanical.

## 3. Write it

- One paragraph per line, never hard-wrapped.
- Dated. Sourced when it matters: said vs observed vs deduced, fact vs hypothesis.
- Their words stay verbatim, in the language they said them, inside English prose.
- Short enough that you will still read it in six months.

If the file is sensitive, add `sensitive: true` to its frontmatter, a 🔒 on its router row, and its name to lock 1 in `protocols/confidentiality.md`. All three.

## 4. Close

```bash
python3 tools/tars.py validate . && git add -A && git commit -m "memory: <what changed>" && git push
```

Silently. Then confirm to the human in one line what you wrote and where. That line is the only thing they see.
