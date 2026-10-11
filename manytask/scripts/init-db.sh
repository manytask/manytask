#!/bin/bash
set -e

GITLAB_DB_USER="${GITLAB_DB_USER:-gitlab}"
GITLAB_DB_PASSWORD="${GITLAB_DB_PASSWORD:-gitlab}"
GITLAB_DB_NAME="${GITLAB_DB_NAME:-gitlab}"

# When POSTGRES_USER is set, that user is created as superuser by the postgres image
# So we just need to ensure the database exists and grant permissions
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    GRANT ALL ON SCHEMA public TO $POSTGRES_USER;
EOSQL

# Role and database for GitLab; extensions require a superuser, so they are created here
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE "$GITLAB_DB_USER" WITH LOGIN PASSWORD '$GITLAB_DB_PASSWORD';
    CREATE DATABASE "$GITLAB_DB_NAME" OWNER "$GITLAB_DB_USER";
    \c "$GITLAB_DB_NAME"
    GRANT ALL ON SCHEMA public TO "$GITLAB_DB_USER";
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    CREATE EXTENSION IF NOT EXISTS btree_gist;
    CREATE EXTENSION IF NOT EXISTS amcheck;
EOSQL
