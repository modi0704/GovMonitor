#!/usr/bin/env bash
# Creates the two application roles of MASTERPLAN 6.1 and the application database.
# Runs once from the postgres image's /docker-entrypoint-initdb.d, or by hand:
#   PGUSER=postgres APP_DB=govmonitor APP_OWNER_PASSWORD=... APP_USER_PASSWORD=... deploy/db/init-roles.sh
# Idempotent: safe to run twice.
set -euo pipefail
APP_DB="${APP_DB:-govmonitor}"
APP_OWNER="${APP_OWNER:-app_owner}"
APP_USER="${APP_USER:-app_user}"
: "${APP_OWNER_PASSWORD:?APP_OWNER_PASSWORD is required}"
: "${APP_USER_PASSWORD:?APP_USER_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 --dbname "${POSTGRES_DB:-postgres}" \
  -v owner="$APP_OWNER" -v appuser="$APP_USER" \
  -v owner_pw="$APP_OWNER_PASSWORD" -v user_pw="$APP_USER_PASSWORD" -v appdb="$APP_DB" <<'SQL'
-- app_owner: owns every table, runs migrations and platform-owner operations.
-- BYPASSRLS because RLS is FORCED on tenant tables (which would otherwise bind the owner too).
-- CREATEDB only so the test suite can create its throwaway database.
SELECT format('CREATE ROLE %I LOGIN BYPASSRLS CREATEDB PASSWORD %L', :'owner', :'owner_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'owner') \gexec
SELECT format('ALTER ROLE %I LOGIN BYPASSRLS CREATEDB PASSWORD %L', :'owner', :'owner_pw') \gexec

-- app_user: what the web and worker processes use. Owns nothing, no BYPASSRLS.
SELECT format('CREATE ROLE %I LOGIN NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L', :'appuser', :'user_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'appuser') \gexec
SELECT format('ALTER ROLE %I LOGIN NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L', :'appuser', :'user_pw') \gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'appdb', :'owner')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'appdb') \gexec
SQL

# app_user must not create objects in the public schema (PostgreSQL 15+ default, made explicit).
psql -v ON_ERROR_STOP=1 --dbname "$APP_DB" -v appuser="$APP_USER" <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'appuser') \gexec
SQL
echo "init-roles: roles and database ready"
