# AGENTS.md

Guidance for AI coding agents working in this repository. Human-facing setup
docs live in [README.md](README.md); this file covers the operational details an
agent needs to make correct changes.

## Project overview

A data platform for currency exchange-rate data:

- **Ingest** — Apache Airflow 3.3.1 (Docker Compose, `LocalExecutor`) pulls
  currency data from the public
  [`@fawazahmed0/currency-api`](https://github.com/fawazahmed0/exchange-api)
  CDN endpoints.
- **Transform** — dbt (`dbt-bigquery`) models the raw data into staging views
  and marts tables on BigQuery.
- **MCP example** — Docker Compose seeds PostgreSQL from the Greeenery CSV files
  and exposes one read-only `query` tool over Streamable HTTP.

Layout:

```text
.
├── airflow/          # Airflow Docker Compose env; DAGs go in airflow/dags/
├── dbt/              # Poetry-managed dbt project (profile lives at dbt/profiles.yml)
├── example-mcp/      # Seeded PostgreSQL and its query-only MCP server
├── greeenery/        # CSV seed data used by example-mcp/
├── scripts/          # Standalone stdlib-only Python utilities
├── secrets/          # GCP key file; whole directory gitignored
├── docs/             # Environment and workshop-maintenance notes
├── .agents/skills/   # Agent skills for the repeated tasks; see below
├── .devcontainer/    # Codespaces: Python 3.12 + gcloud CLI + Poetry
└── .github/          # Prebuilt devcontainer image and its build workflow
```

All human-facing documentation is consolidated in the root
[README.md](README.md) — subdirectories deliberately have no README of their
own. When you change setup steps, commands, or environment variables, update
the root README and do not add a new README next to the code.

## Setup commands

### Airflow

```bash
cd airflow
cp .env.example .env          # then set AIRFLOW_UID=$(id -u) on Linux
docker compose up airflow-init
docker compose up -d
```

UI: <http://localhost:8080>. Requires Docker Compose v2 and at least 4 GB of
memory allocated to Docker.

```bash
docker compose ps
docker compose logs -f airflow-scheduler
docker compose run --rm airflow-cli dags list
docker compose down                 # add -v to also drop the Postgres volume
```

### dbt

```bash
cd dbt
poetry install
poetry run dbt debug    # set `project` in profiles.yml first
```

`dbt-bigquery` requires Python `>=3.10,<3.14`, so `poetry install` fails
outright on a 3.14 interpreter — and 3.14 is already the default `python3` on
some machines here. Point Poetry at a supported one first:
`poetry env use python3.13`.

### Example MCP

```bash
cd example-mcp
cp .env.example .env        # optional; Compose has matching defaults
docker compose up --build -d
```

PostgreSQL is published on `127.0.0.1:5433` and the MCP endpoint is
`http://127.0.0.1:8000/mcp`. The seed scripts read the CSV files from
`greeenery/` only when the PostgreSQL volume is first created.

## Build and test commands

Always run dbt from the `dbt/` directory.

```bash
poetry run dbt parse    # structure only - no warehouse connection
poetry run sqlfluff lint  models/
poetry run sqlfluff fix   models/
poetry run dbt debug    # verify BigQuery connection
poetry run dbt compile  # renders Jinja to SQL - does not check columns
poetry run dbt build --empty   # runs the SQL with zero-row inputs
poetry run dbt build    # seed + run + test
poetry run dbt run
poetry run dbt test
```

The first three need no credentials and are the checks that always apply: on
this repo `dbt parse` exits 2 on an unknown `ref()`, and `sqlfluff lint` exits
1 on an uppercase keyword. Everything from `dbt debug` down connects, so
without a key at `secrets/credentials.json` and a real `project` in
`profiles.yml` they fail at the connection — an environment problem, not a
verdict on the model. Report it as that, and never invent a credential to get
past it.

`dbt compile` is not the column check it looks like: it renders Jinja into SQL
and connects only for introspective queries. Whether the columns exist is
answered by executing the SQL — `dbt build`, or `dbt build --empty`, which
sends the real query with its inputs limited to zero rows.

[.agents/skills/add-dbt-model/](.agents/skills/add-dbt-model/SKILL.md) walks
through the whole loop, including how to read each failure.

No `--profiles-dir` flag: dbt looks for `profiles.yml` in the working
directory, and it sits at `dbt/profiles.yml`. The `keyfile` path in it is
relative to the working directory too, so both reasons point the same way —
run dbt from `dbt/`. If you find a `--profiles-dir` snippet anywhere, it is
stale.

`dbt/pyproject.toml` is `package-mode = false`: Poetry manages dependencies
only and does not build `dbt/` as a Python package.

Python in `scripts/` and `airflow/dags/` is linted with ruff. The config is
[ruff.toml](ruff.toml) at the root; the rules it selects mirror the type-hint
and docstring requirements in Code style below.

```bash
ruff check .
ruff format --check .
```

Validate and test the MCP example from `example-mcp/`:

```bash
docker compose config --quiet
docker compose up --build -d
docker compose exec -T mcp python -m unittest tests.test_server
docker compose exec -T \
  -e MCP_URL=http://127.0.0.1:8000/mcp \
  mcp python -m unittest tests.test_server.HttpSmokeTest
```

The HTTP smoke test verifies that the server advertises only `query`, reads a
known seeded value, and rejects a write. `docker compose down` stops the
services without removing the seeded database; `docker compose down -v`
deletes it and causes the CSV files to be reloaded on the next start.

ruff is not in any dependency file — it is a standalone tool. The devcontainer
installs it with `pipx install ruff` (the image ships pipx but not uv). On a
machine that has uv instead, `uv tool install ruff`, or run it without
installing anything: `uvx ruff check .`.

After writing or editing anything in `airflow/dags/`, check that Airflow can
import it before saying it is done. Use whichever matches what is running —
`docker compose ps` says which:

```bash
cd airflow
docker compose exec airflow-scheduler airflow dags list-import-errors --local
docker compose run --rm airflow-cli dags list-import-errors --local
```

`--local` parses the files on disk instead of reporting what the dag-processor
last serialized, which is stale for a file written seconds ago.

Exit 0 means every file Airflow selected for parsing imported successfully
(`No data found`). Exit 1 means either a selected file failed to import (a
`filepath | error` table) or the metadata database was never migrated
(`Database migration required` — run
`docker compose up airflow-init`, then check again). Do not read that exit
code through a pipe: `… | tail` reports the status of `tail`, always 0.

It catches import errors only, and only in files whose contents contain both
`airflow` and `dag` — Airflow skips the rest without a word.

[.agents/skills/write-airflow-dag/](.agents/skills/write-airflow-dag/SKILL.md)
walks through that whole loop. Skills live in `.agents/skills/`, one of the
project skill directories GitHub Copilot reads — which is the tool students
use here.

There is no test suite for `scripts/`. Verify changes by running the script
from the repository root:

```bash
python scripts/load_currency.py
```

`OUTPUT_DIR` is the relative path `scripts/data`, resolved against the current
working directory — the same trap as dbt's `keyfile`. Run it from inside
`scripts/` and it writes to `scripts/scripts/data/`.

## Environment and credentials

- BigQuery auth is `method: service-account` with a key file. `profiles.yml`
  holds every setting as a literal value — no `env_var()` and no dotenv file
  for dbt. This is a teaching repo: students edit `project` in the file
  directly. Do not reintroduce `env_var()` unless asked.
- **Never commit, print, or paste the contents of a service-account key.** It
  is a long-lived credential that works immediately if it leaks. Common
  filenames (`credentials.json`, `*service-account*.json`, `*keyfile*.json`)
  are gitignored anywhere in the repo as a second line of defence, but the
  real guard is that all of `secrets/` is ignored.
- **Never open a file inside `secrets/`.** Listing the directory is fine and
  often necessary — knowing that `credentials.json` is present is enough to
  answer most questions. Reading it is not: no `Read`, no `cat`/`head`/`tail`,
  no `grep`, no script that prints it, and no quoting it back in a summary or
  an error message. Ask the person to check the file themselves instead. Once a
  key reaches a transcript it must be treated as leaked and rotated, so there
  is no version of this that is only a little bit wrong.
- `keyfile` in `profiles.yml` is the relative path
  `../secrets/credentials.json`. dbt resolves it against the current working
  directory, not against `profiles.yml`, so run every dbt command from `dbt/`.
- `profiles.yml` is a tracked file, so nothing secret may go in it. A project
  id and a keyfile path are fine; the key itself never goes near it.
- Airflow's dotenv file is gitignored and holds real values. Only edit the
  matching example file when adding a variable; never read, print, or copy the
  contents of the real one into code, logs, or a commit.
- In dbt models, reach for dbt's `target` context rather than repeating the GCP
  project id. `dbt/.sqlfluff` stubs `target` so this still lints without a
  warehouse; see the sqlfluff note under Code style. Airflow DAGs have no dbt
  context; let `bigquery.Client()` discover the project from the configured
  credentials as described below.
- Airflow's local admin credentials are development-only defaults and must not
  be reused anywhere real.

## Code style

**Python** (`scripts/`, future `airflow/dags/`)

- Python `>=3.10,<3.14` (the `dbt-bigquery` cap). `from __future__ import
  annotations`, full type hints on public functions, and docstrings on the
  module and on every function, `main()` included.
- ruff enforces the two rules above; see [ruff.toml](ruff.toml) and the lint
  commands under Build and test commands. It is a dev tool, not a dependency —
  nothing in the repo imports it.
- `scripts/` is deliberately **stdlib-only** — no `requests`, no third-party
  dependencies. Keep it that way so the scripts run without a virtualenv.
- Catch specific exceptions and fail loudly: report the error on `stderr` and
  exit non-zero (`sys.exit`), so a scheduler never records a failed run as a
  success. `main()` returns `None` and `__main__` just calls it. See
  [scripts/load_currency.py](scripts/load_currency.py) as the reference
  implementation, including its atomic-write pattern.
- DAG files belong in `airflow/dags/`. Keep business logic in importable
  modules so it can be tested outside Airflow.

**SQL / dbt** (`dbt/models/`)

- Lowercase keywords, trailing commas, one column per line, snake_case names.
- `models/staging/` → materialized as `view`, named `stg_<source>_<entity>`.
  A staging model **renames columns and recasts types, and does nothing
  else**: no filtering, no joins, no aggregation, no derived columns, no
  business rules. Its row count matches the raw table it reads. Anything
  beyond a rename or a cast belongs downstream, in a mart.
- Staging is the **only** layer allowed to call `{{ source() }}`, and it is
  always a `view` — never give a staging model a different materialization.
  One staging model per raw table.
- `models/marts/` → materialized as `table`, named for the business concept.
- A mart or report model (`fct_*`, `dim_*`, anything downstream) reads from
  `{{ ref() }}` **only** — it must never call `{{ source() }}`. Reaching past
  staging into a raw table skips the rename and the cast, so two models end up
  reading the same column under different names and types, and the lineage
  graph stops showing where a number actually came from.
- Materialization is set in `dbt_project.yml`; only add a `{{ config() }}`
  block when a model genuinely deviates.
- Never write a hardcoded `project.dataset.table` anywhere — `{{ ref() }}` and
  `{{ source() }}` are what make the dependency graph real.
- Add a `schema.yml` beside new models with descriptions and at least
  `not_null` / `unique` tests on keys.
- `dbt/.sqlfluff` enforces the two capitalisation rules above and an
  88-character line limit. It uses the **jinja** templater with stubbed
  `ref`/`source`/`config`/`var` macros, not the dbt templater, so
  `sqlfluff lint` runs without a BigQuery connection — which is why
  `sqlfluff-templater-dbt` is deliberately not a dependency.
  Without a dialect set there, sqlfluff refuses to run at all. dbt builtins are
  stubbed in **two** sections and the difference matters: macros (`ref`,
  `source`, `config`, `var`, `is_incremental`) go under `jinja:macros`, while
  context *variables* go under `jinja:context`. `target` is already stubbed
  there, so `{{ target.project }}` lints clean; a macro stub for it would not
  work. Anything else a model reaches for — `this`, for one — needs the same
  treatment or `sqlfluff lint` reports `Undefined jinja template variable`.

**Markdown and language**

- Wrap prose at roughly 80 characters, matching the existing READMEs.
- Everything students read is written in **Thai**: [README.md](README.md), the
  workshop material, and the explanatory comments inside `dbt/profiles.yml` —
  students edit that file by hand. Keep writing those in Thai; do not quietly
  translate them to English while editing something else.
- Everything aimed at the code is written in **English**: Python docstrings and
  comments, SQL comments, commit messages, `dbt/.sqlfluff` (tool config nobody
  is asked to edit during the workshop), and this file.

## Conventions and constraints

- `airflow/docker-compose.yaml` is kept intentionally close to the upstream
  official file so it can be refreshed from the Airflow docs. Prefer overriding
  behaviour through environment variables in that file rather than editing its
  service definitions; if you must edit them, keep the diff minimal and say why.
- `airflow/config/` is **not** where an override that other people need goes.
  `airflow/.gitignore` ignores `config/*` except `.gitkeep`, and Airflow writes
  its own generated `airflow.cfg` in there on first start — so a file dropped
  into it is local to one machine. An override that must reach everyone goes in
  the compose file as an `AIRFLOW__<SECTION>__<KEY>` environment variable.
- `LocalExecutor` is a deliberate choice — no Redis, Celery, or worker
  container. Do not reintroduce them.
- The Airflow containers mount `dags/`, `logs/`, `config/`, `plugins/`, and
  `secrets/` (read-only) from `airflow/`. Files created inside containers are
  owned by `AIRFLOW_UID`.
- One key file serves both tools: `secrets/credentials.json` at the repo root.
  dbt points at it from `profiles.yml`; compose mounts `../secrets`
  read-only into the Airflow containers and sets
  `GOOGLE_APPLICATION_CREDENTIALS`. Do not add a second copy anywhere.
- The whole `secrets/` directory is gitignored, so any filename dropped in is
  safe. Never put a key in `airflow/dags/` — that directory is tracked, and
  only a few exact filenames are caught by the root gitignore.
- `scripts/load_currency.py` takes **no arguments** by design. The URL
  template, the currency (`btc`), the date (`DATE`), and the output directory
  are all module-level constants. `DATE` is pinned to a single day, so the
  script fetches exactly one date per run; change the constant to fetch a
  different one. Do not reintroduce argparse, and do not make the date
  dynamic, unless asked.
- Output goes to `scripts/data/<DATE>/btc.json` so separate days do not
  overwrite each other. `scripts/data/` has its contents gitignored, with
  `.gitkeep` negated so the directory itself stays tracked.
- `dbt/models/example/example.sql` is a connection smoke test. It can be removed
  once real staging and mart models exist.
- DAGs in `airflow/dags/` use the classic `PythonOperator` only — no TaskFlow
  `@task` decorators and no provider operators such as
  `BigQueryInsertJobOperator`. The point is that the operator graph stays
  visible in the DAG file and the work itself stays in a plain callable.
- Reach BigQuery with the `google.cloud.bigquery` client inside that callable,
  not through `BigQueryHook` or an Airflow connection. The containers already
  export `GOOGLE_APPLICATION_CREDENTIALS`, so `bigquery.Client()` finds the
  service account on its own — and the same function then runs outside Airflow
  unchanged, which is what makes it testable.
- `google-cloud-bigquery` is already in the stock `apache/airflow:3.3.1` image
  (3.43.0, checked with
  `docker compose run --rm airflow-cli python -c "import google.cloud.bigquery"`).
  Nothing needs installing: leave `_PIP_ADDITIONAL_REQUIREMENTS` empty.
## Git and PR conventions

- Conventional Commit prefixes, matching the existing history:
  `chore:`, `docs:`, `feat:`, `fix:`. Subject in imperative mood, lowercase.
- Do not commit or push unless explicitly asked.
- Keep secrets, `dbt/target/`, `dbt/dbt_packages/`, `dbt/logs/`,
  `airflow/logs/`, and `scripts/data/` out of commits.
- Before reporting a change as done, run the relevant command above
  (`dbt build`, `sqlfluff lint`, `ruff check`, the DAG import check, or the
  script) and report the real output.

## Things to check before large changes

1. Does the change need a new environment variable? Add it to the matching
   `.env.example` and to the README in the same commit.
2. Would it require a paid or non-default GCP API? Ask first — this runs
   against a personal GCP project.

## Reference

- [Apache Airflow Docker Compose](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose.html)
- [dbt BigQuery adapter](https://docs.getdbt.com/docs/core/connect-data-platform/bigquery-setup)
- [GCP service-account keys](https://cloud.google.com/iam/docs/keys-create-delete)
