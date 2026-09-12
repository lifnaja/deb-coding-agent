---
name: write-airflow-dag
description: Write or edit an Airflow DAG in airflow/dags/, then verify it with ruff and an import check in the airflow-cli container. Use whenever a DAG file in this repo is created or changed, including small edits, and before reporting DAG work as done.
---

# Writing an Airflow DAG in this repo

Read [AGENTS.md](../../../AGENTS.md) first — its Conventions section is the
authority on what a DAG here may contain. This skill covers the workflow and
the verification, not the rules.

## 1. Write it

### Naming

- Name the `dag_id` with `<domain>_<entity>[_<grain>]` in lowercase
  `snake_case`, for example `sales_orders_daily`.
- Keep one DAG per file and make the filename match the `dag_id` exactly:
  `sales_orders_daily.py` contains `dag_id="sales_orders_daily"`.
- Do not add a `_dag` suffix; Airflow already presents the identifier as a DAG.
- Do not put deployment environments such as `dev`, `staging`, or `prod` in
  the name. Deploy the same DAG identity through each environment.
- Include a grain such as `_daily` only when it describes the data grain or
  distinguishes pipelines that intentionally run at different grains. Do not
  rename a DAG merely because its current schedule changes.
- Do not add a generic action such as `_ingest` when every DAG in the repo
  performs that action. Use an action suffix such as `_backfill` or
  `_reconcile` only for a genuinely separate workflow type.
- Name each `task_id` with `<verb>_<object>`, such as `fetch_orders` or
  `load_orders`.

### Structure

- Classic `PythonOperator` only — no TaskFlow `@task`, no provider operators.
- Give each task one responsibility: one observable pipeline step with its own
  success, failure, and retry boundary. For example, model fetch, transform,
  and load as separate tasks instead of hiding all three behind one
  `PythonOperator`.
- Do not interpret one responsibility as one function call. Keep tightly
  coupled operations in the same task when separating them would not create a
  useful retry or monitoring boundary.
- Give every `PythonOperator` its own plain callable in an importable module,
  not inline in the DAG file, so each task can be run and tested without
  Airflow.
- Pass only small serializable values through XCom. For substantial payloads,
  write the data to durable storage and pass its location to the next task.
- BigQuery through the `google.cloud.bigquery` client inside that callable.
  `GOOGLE_APPLICATION_CREDENTIALS` is already set in the containers, and
  `google-cloud-bigquery` ships in the image (3.43.0 on `apache/airflow:3.3.1`)
  — so `import` works with `_PIP_ADDITIONAL_REQUIREMENTS` left empty. If that
  import ever fails, say so; do not paper over it by adding the package there.

## 2. Lint

From the repository root:

```bash
ruff check .
ruff format --check .
```

Config is [ruff.toml](../../../ruff.toml) at the root. `--fix` and
`ruff format` (without `--check`) apply the changes.

If `ruff` is not on PATH: the devcontainer and Codespaces install it through
`pipx install ruff`, a machine with uv can use `uv tool install ruff` or run
`uvx ruff check .` without installing anything. The config is what matters,
not how the binary got there.

## 3. Check that Airflow can import it

Look at what is running first — `docker compose ps` — and pick the matching
command. Both take the same arguments and print the same thing.

**Stack already up** — use the scheduler that is already running. No new
container, roughly a second:

```bash
cd airflow
docker compose exec airflow-scheduler airflow dags list-import-errors --local
```

**Nothing running** — `airflow-cli` sits behind the `debug` profile, but
`docker compose run` starts it anyway and pulls up `postgres`, which it
depends on. Around three seconds:

```bash
cd airflow
docker compose run --rm airflow-cli dags list-import-errors --local
```

`--local` parses the files on disk. Without it the command reports whatever the
dag-processor last serialized into the metadata database, which is stale for a
file written seconds ago.

`docker compose up airflow-init` is **not** part of this loop. It migrates the
metadata database, which is a one-time thing already done by any stack that has
been started, and needed again only after `docker compose down -v`. Do not run
it pre-emptively — run it when the output says the database needs it (step 4).

## 4. Read the result

Exit 0 means every file Airflow selected for parsing imported successfully.
Exit 1 means something is wrong, and the output says which of two things it is.
Measured on this repo, both commands behave identically:

| Situation | Exit | Output |
| --- | --- | --- |
| Every selected file imported | 0 | `No data found` |
| A file failed to import | 1 | table of `filepath \| error` with the traceback |
| Metadata database not migrated | 1 | `Database migration required. Please run 'airflow db migrate'.` |

The third one is not a verdict on the code — nothing was parsed. Run
`docker compose up airflow-init`, then run the check again.

Do not read the exit code through a pipe. `docker compose ... | tail` reports
the exit status of `tail`, which is 0 no matter what happened upstream, and a
broken DAG then looks like a pass.

### The one silent pass

Airflow only opens a file in `dags/` if its contents contain **both** the
strings `airflow` and `dag`, case-insensitive. A file missing either one is
skipped without a word — exit 0, `No data found`, and the file was never read.

A real DAG file always has both. A helper module sitting in `dags/` may not,
and this command then tells you nothing about it. Verified here: one broken
file was invisible until the word `airflow` was added to it, after which it was
reported.

## 5. Report

Paste the real output. A DAG that imports is not a DAG that works — this check
finds import errors only, so say that is what was checked. Delete any scratch
file added while debugging; `airflow/dags/` is a tracked directory and
everything in it gets parsed.
