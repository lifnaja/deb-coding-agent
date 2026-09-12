FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

LABEL org.opencontainers.image.source="https://github.com/lifnaja/deb-gen-ai-playground"

USER root
RUN PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install poetry \
    && PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install ruff

# Yarn is unused; its inherited apt source can block updates with a stale key.
RUN rm -f /etc/apt/sources.list.d/yarn.list

# Bake in the dbt dependencies so that the `poetry install` a codespace runs on
# creation has nothing left to do. Measured on this lock file: 24s cold, 0.4s
# once these are already present.
#
# Turning virtualenv creation off is what makes that cache hit. Poetry names a
# virtualenv after a hash of the project's absolute path, so a baked venv stops
# matching the moment the workspace sits anywhere but the exact path it was
# built at -- a renamed fork is enough (verified: .../deb-gen-ai-playground/dbt
# gave currency-dbt-Oc8HMUZI, .../some-fork-name/dbt gave currency-dbt-9NoCA67X,
# and poetry built the whole environment a second time). Installed into the
# system site-packages instead, the path stops mattering. `poetry run dbt` and
# `poetry run sqlfluff` still work; poetry only notes the skipped virtualenv on
# stderr, and `poetry -q run` silences that.
#
# This couples the image to dbt/poetry.lock: change a dbt dependency and the
# image has to be rebuilt, which is why the publish workflow watches both files.
# Forgetting degrades rather than breaks -- `poetry install` then installs only
# what changed.
ENV POETRY_VIRTUALENVS_CREATE=false
COPY pyproject.toml poetry.lock /tmp/dbt/
RUN cd /tmp/dbt \
    && poetry install --no-interaction \
    && rm -rf /tmp/dbt /root/.cache
