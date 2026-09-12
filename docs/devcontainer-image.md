# GitHub Codespaces and the shared image

## GitHub Codespaces

Open the repository or a fork in Codespaces to pull the shared image,
`ghcr.io/lifnaja/deb-gen-ai-playground-devcontainer:1`.
It includes Python 3.12, Google Cloud CLI, Poetry, ruff, Docker-in-Docker, and
the dbt dependencies from `dbt/poetry.lock`. The `poetry install` a codespace
runs on creation therefore finds nothing to do and takes well under a second
instead of around 24. A fork that changes its own dbt dependencies still works —
`poetry install` installs whatever differs. Run Airflow with `docker compose`;
Docker Desktop is not needed on your own machine.

After creating a codespace or rebuilding its container, verify Docker with:

```bash
docker info
docker compose version
```

Then follow the Google Cloud service account and Airflow setup steps in the
[README](../README.md). Open the Airflow UI through port 8080 in the Codespaces
Ports tab.

Students do not need to configure Codespaces prebuilds or enable GitHub Actions
in their forks. The configuration continues to reference the upstream
repository's public image. Creating a new codespace still requires downloading
the image, and that image is about 660 MB larger now that it carries the dbt
dependencies. The install it replaces took around 24 seconds, so the saving is
real but not the whole 24. Reopening an existing codespace runs neither.

The image targets Codespaces (`linux/amd64`). It does not include Airflow images
or data, so the first Airflow startup still needs to pull its images.

## Building and publishing the shared image

Build files live in `.github/devcontainer-image/`. The Dockerfile installs Poetry
and ruff, then installs the dbt dependencies. Dev Container Features install
Google Cloud CLI and Docker-in-Docker, including the metadata needed to start
the Docker daemon. Build with the Dev Container CLI to preserve this metadata.

The build context is limited to that directory, so the workflow copies
`dbt/pyproject.toml` and `dbt/poetry.lock` into it before building; both copies
are gitignored and must not be committed there. The Dockerfile sets
`POETRY_VIRTUALENVS_CREATE=false` so those packages land in the system
site-packages rather than in a virtualenv. That is deliberate: poetry names a
virtualenv after a hash of the project's absolute path, so a baked virtualenv
would stop matching as soon as the workspace sat anywhere but the path it was
built at, and a renamed fork is enough to cause that. `poetry run dbt` and
`poetry run sqlfluff` work either way.

The trade is that the image is now coupled to `dbt/poetry.lock`. Changing a dbt
dependency means republishing the image, which is why the workflow also triggers
on that file. Forgetting is not a breakage: `poetry install` on creation just
installs the difference, and the codespace is slower to be ready.

The `.github/workflows/devcontainer-image.yml` workflow runs only in the upstream
repository when changes to the build files or workflow are pushed to `main`.
You can also trigger it from `main` through Actions → Publish devcontainer image
→ Run workflow. It checks Python, Poetry, ruff, dbt, sqlfluff, gcloud, and
Compose, asserts that `poetry install` in `dbt/` reports nothing left to do —
the whole point of baking the dependencies in — and runs a test container before
publishing the `1` and `sha-<commit>` tags to GHCR using `GITHUB_TOKEN`.

Before sharing the repository with students for the first time:

1. Push the build files and workflow to `main`, then wait for the workflow to
   succeed.
2. Go to your GitHub profile → Packages → `deb-gen-ai-playground-devcontainer`
   → Package settings → Change visibility → Public. New GHCR packages are private
   by default, even when the repository is public.
3. Verify that the image can be pulled without logging in before students open
   Codespaces. Creating a codespace from a fork will fail if the image has not
   been published or is still private.

After changing the tools or the dbt dependencies, build the image again and use
Rebuild Container to pick up the new image. Forks can use the shared image
without changing its owner.
To publish your own image, update the image references, source label, and
workflow's repository condition to match your repository.

See [sharing prebuilt images with forks](https://containers.dev/guide/prebuild)
and [publishing to GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
