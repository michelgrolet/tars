# The security pass

**When it runs.** At the end of any turn where something you built became reachable by someone other than your human: a table, a view, a function, a page, an endpoint, a cron, a bucket, a token. Not after a local script, a memory edit, a document. The test is one question: *did the surface someone else can touch change?*

**Why it exists.** The hole is never a rule you did not know. It is a check you did by reading your own change instead of asking the live system. You write `enable row level security`, then a policy, then a grant, object after object, and the one object where the first line is impossible gets the grant anyway. Reading your own work confirms your intent, never the result. The questions below ask the system, and they take ten seconds.

## The four questions

Run them against the live database. All four must come back empty or expected.

**1. What can a signed-in stranger read without a gate?** The one that catches the most. A materialized view cannot carry row security: it is not disabled, it does not exist, and every "RLS is on everywhere" audit walks straight past it. Same for a view without `security_invoker`, which runs as its owner and steps over the row security of everything underneath.

```sql
select c.relname, c.relkind from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind in ('r','v','m')
  and has_table_privilege('authenticated', c.oid, 'SELECT')
  and (c.relkind = 'm'
       or (c.relkind = 'r' and not c.relrowsecurity)
       or (c.relkind = 'v' and coalesce((select option_value from pg_options_to_table(c.reloptions)
            where option_name = 'security_invoker'), 'false') <> 'true'));
```

**2. What can someone with no account at all read?** Must be empty.

```sql
select c.relname, c.relkind from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind in ('r','v','m')
  and has_table_privilege('anon', c.oid, 'SELECT');
```

**3. What can either of them execute?** Postgres grants `execute` to `PUBLIC` by default, and a REST layer like PostgREST publishes every function in `public` as `/rpc/<name>`. So a new definer function is open to the internet the second it is created, including the ones that write.

```sql
select p.proname, p.prosecdef from pg_proc p join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public' and p.prosecdef
  and (has_function_privilege('anon', p.oid, 'EXECUTE')
    or has_function_privilege('authenticated', p.oid, 'EXECUTE'));
```

The expected answers are the helpers your row-security policies call: a policy runs as the querying user, so revoking those would deny everything. Everything else on that list is a finding.

**4. What does the platform itself say?** Run whatever advisor or linter your host ships, and read every line rather than the count. It is the cheapest check in the list and the one most often skipped.

## Beyond the database

- **A page that was deployed.** Which key is in the bundle: a publishable key belongs there, a secret one never. And what a logged-out visitor actually gets, checked in a window that is not your human's, because their own session hides exactly what you are testing.
- **A token.** Never in the repo. A config directory outside the tree, or a table readable by the service role alone.
- **A cron or an endpoint added on a server.** Which port it listens on, and who can reach it.
- **Third-party data.** It never leaves through anything your human did not open themselves.

## The rule that carries it

A grant is a decision, and a decision gets verified against the live system, not against the migration that wrote it. Whenever a `grant` is written in a turn, question 1 runs before the turn closes.

## And when you change a schema

A migration reviewed by reading is a guess. Run it against a throwaway instance of the real engine before it touches anything that matters: a change that reads correctly can still fail on a dependent index expression, a check constraint the change itself breaks, or a view holding a column hostage. A disposable container costs two minutes.

When a migration renames or drops something the code names, deploy both in the same breath.
