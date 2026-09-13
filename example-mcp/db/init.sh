#!/usr/bin/env bash

set -euo pipefail

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${MCP_DB_USER:?MCP_DB_USER is required}"
: "${MCP_DB_PASSWORD:?MCP_DB_PASSWORD is required}"

psql \
  --set ON_ERROR_STOP=1 \
  --set database_name="$POSTGRES_DB" \
  --set reader_user="$MCP_DB_USER" \
  --set reader_password="$MCP_DB_PASSWORD" \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --file /schema/schema.sql
