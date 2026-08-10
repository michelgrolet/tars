# memory/

What you know. This folder grows for as long as you exist, and it is the reason you are not a fresh assistant every morning.

## The rule

**One theme, one file, one row in the router.** When you learn something durable that no existing file covers, create `memory/<theme>.md` and add a single line to the router in `CLAUDE.md`: a markdown link plus when to open it. The threshold grows by one line, never by a paragraph.

Nothing in here loads on its own. That is deliberate: see [`../protocols/context.md`](../protocols/context.md).

## When a theme becomes a domain

A file that passes a few hundred lines, or that covers several genuinely separate questions, becomes a folder with its own `index.md` sub-router. The threshold then points at the sub-router, not at its twenty files. Descend one stage at a time.

## Writing rules

- **Date and source** every addition: fact vs hypothesis, said vs observed vs deduced.
- **Correct in place.** If something turns out false, fix the line. Never stack a contradiction on top of the old version and leave your future self to guess which one won.
- **Quotes stay verbatim**, in the language they were said in, inside English prose.
- **Never hard-wrap.** One paragraph per line.
- **A command you write down, you ran first.** Untested recipes rot in silence.

## Marking a file sensitive

Add `sensitive: true` in the frontmatter and a 🔒 on its router row, then name it in the blocklist in [`../protocols/confidentiality.md`](../protocols/confidentiality.md). All three, or the lock applies nowhere.
