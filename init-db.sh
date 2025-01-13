#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER adminmanytask WITH PASSWORD 'adminpass';
    CREATE DATABASE manytask;
    GRANT ALL PRIVILEGES ON DATABASE manytask TO adminmanytask;
    \c manytask
    GRANT ALL ON SCHEMA public TO adminmanytask;
EOSQL