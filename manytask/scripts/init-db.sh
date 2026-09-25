#!/bin/bash
set -e

# When POSTGRES_USER is set, that user is created as superuser by the postgres image
# So we just need to ensure the database exists and grant permissions
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    GRANT ALL ON SCHEMA public TO $POSTGRES_USER;
EOSQL