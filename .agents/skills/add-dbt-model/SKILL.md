---
name: add-dbt-model
description: Add or change a dbt model in dbt/models/, validating it with sqlfluff and dbt parse, then dbt build --empty when warehouse credentials are available. Use whenever a model, schema.yml, or dbt config in this repo is edited.
---

# Adding a dbt model in this repo

Read [AGENTS.md](../../../AGENTS.md) first — its SQL / dbt section is the
authority on what belongs in which layer. This skill covers the workflow and
the verification, not the rules.

## 1. Write it

- **staging** — renames and recasts, nothing else. Always a `view`, the only
  layer allowed to call `{{ source() }}`, named `stg_<source>_<entity>`.
- **marts** — `{{ ref() }}` only, never `{{ source() }}`. A `table`, named for
  the business concept.
- A `schema.yml` beside the model, with descriptions and at least `not_null`
  and `unique` on the keys.
- Lowercase keywords, trailing commas, one column per line, snake_case.

## 2. Run every command from `dbt/`

```bash
cd dbt
```

There is no `--profiles-dir` flag anywhere: `profiles.yml` sits in `dbt/`, and
the `keyfile` path inside it is relative to the working directory too. Both
reasons point the same way. A `--profiles-dir` snippet found anywhere is stale.

Commands below are written as `poetry run …`, which is how the project is set
up. Any dbt and sqlfluff on PATH work the same; without them,
`uvx --from dbt-bigquery dbt parse` and `uvx sqlfluff lint models/` run without
installing anything. (uvx prints a cosmetic warning suggesting `--from
dbt-core`; ignore it — that spelling would leave out the BigQuery adapter.)

## 3. Lint — no warehouse needed

```bash
poetry run sqlfluff lint models/
poetry run sqlfluff fix  models/   # applies what it can
```

`All Finished!` is printed **either way** — it is not a pass signal, and
reading it as one is the easy mistake here. Measured on this repo:

- Clean: exit 0, and `All Finished!` is the only line.
- Violations: exit 1, a `== [<path>] FAIL` line, then one line per violation as
  `L: <line> | P: <pos> | <rule> | <message>` — and `All Finished!` at the end
  all the same.

So judge it by the exit code and the `FAIL` line, never by the last line. An
uppercase `SELECT` gives `CP01 Keywords must be lower case`, an uppercase
column alias gives `CP02 Unquoted identifiers must be lower case`.

`dbt/.sqlfluff` uses the jinja templater with stubbed `ref`/`source`/`config`
macros, so this never touches BigQuery. A dbt builtin with no stub there has to
be added, and it goes in one of two sections: a macro (something you *call*)
under `jinja:macros`, a context variable (something you read attributes off,
like `target` — already stubbed — or `this`) under `jinja:context`. Put a
context variable in the macros section and lint still fails with
`Undefined jinja template variable`.

## 4. Parse — no warehouse needed

```bash
poetry run dbt parse
```

This is the real gate for a model's structure: bad Jinja, an unknown `ref()` or
`source()`, a malformed `schema.yml`. Exit 0 means the project parsed. Exit 2
prints `Compilation Error` — measured here, `{{ ref('no_such_model') }}` gives
`depends on a node named 'no_such_model' which was not found`.

While `models/staging/` and `models/marts/` are still empty, every run warns
about `2 unused configuration paths: models.currency_dbt.staging` and
`…marts`. That is expected and not a failure — the materialization defaults in
`dbt_project.yml` simply have no models to apply to yet.

`dbt parse` writes into `dbt/target/`, which is gitignored.

## 5. Compile — needs credentials, and checks less than it sounds like

```bash
poetry run dbt compile
```

`compile` renders Jinja into raw SQL under `dbt/target/compiled/`. That is all
it does. From dbt's own docs: *"If you just want dbt to read and validate your
project code, without connecting to the data warehouse, use `dbt parse`
instead."* It does **not** check that the columns you selected exist, and does
not ask the warehouse whether the SQL is valid.

So why the connection? For introspective queries — populating the relation
cache so incremental models know whether they already exist, and resolving
macros that run SQL themselves such as `run_query` or
`dbt_utils.get_column_values`. Nothing in this project does either of those
yet, so over `parse` it buys exactly one thing: the rendered SQL, which is
worth reading to confirm `{{ ref() }}` and `{{ source() }}` resolved to the
tables you expected.

**Columns are only ever checked by executing the SQL.** That means `dbt build`,
or the cheap version of it:

```bash
poetry run dbt build --empty    # limits refs and sources to zero rows
```

`--empty` sends the real query to BigQuery with zero-row inputs, so a
misspelled column or a bad join fails there without scanning data. Use it when
credentials exist and a full `dbt build` would be wasteful.

Both need a real key at `secrets/credentials.json` and the `project` in
`profiles.yml` changed from `your-gcp-project-id`. Without them the command
fails at the connection, exit 2:

```text
Encountered an error:
Database Error
  [Errno 2] No such file or directory: '../secrets/credentials.json'
```

**That is an environment problem, not a verdict on the model.** When it
happens: say `parse` and `sqlfluff` passed and that the warehouse checks could
not run for lack of credentials. Never create, guess at, or go looking for a
key — see the `secrets/` rule in AGENTS.md.

## 6. Report

Paste the real output of each check and say which ones actually ran. Be exact
about what that leaves unproven:

| Passed | Proves |
| --- | --- |
| `sqlfluff lint` | style only |
| `dbt parse` | Jinja, `ref`/`source` resolve, `schema.yml` is well formed |
| `dbt compile` | the same, plus the SQL renders and the connection works |
| `dbt build --empty` | the warehouse accepts the query — columns really exist |
| `dbt build` | the above, and the tests pass against real data |

A model that lints and parses cleanly has not been near the warehouse. Do not
call that "verified" without saying where the checking stopped.
