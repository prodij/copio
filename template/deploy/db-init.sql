-- Run once as the RDS admin (database `postgres`). Zitadel creates its own role and database.
-- The passwords come from the environment, not the arguments. Unset: ON_ERROR_STOP ends the run at its first use. Empty would mean a role with no password, so first-run.sh refuses that first.
\getenv app_password APP_DB_PASSWORD
\getenv lago_password LAGO_DB_PASSWORD
SELECT format('CREATE ROLE app LOGIN PASSWORD %L', :'app_password')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app') \gexec
SELECT format('CREATE ROLE lago LOGIN PASSWORD %L', :'lago_password')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lago') \gexec
GRANT app TO CURRENT_USER;
GRANT lago TO CURRENT_USER;
SELECT 'CREATE DATABASE app OWNER app' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'app') \gexec
SELECT 'CREATE DATABASE lago OWNER lago' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'lago') \gexec

-- Lago's first migration would fail trying to create pg_partman: creating it needs rds_superuser, and `lago` isn't one.
\connect lago
CREATE SCHEMA IF NOT EXISTS partman;
CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;
GRANT ALL ON SCHEMA partman TO lago;
GRANT ALL ON ALL TABLES IN SCHEMA partman TO lago;
GRANT ALL ON ALL SEQUENCES IN SCHEMA partman TO lago;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA partman TO lago;
GRANT EXECUTE ON ALL PROCEDURES IN SCHEMA partman TO lago;
