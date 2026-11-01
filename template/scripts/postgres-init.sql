-- Local-only databases and passwords; real environments get generated secrets in milestone 2.
-- Zitadel creates its own `zitadel` user and database on first start (it gets the admin login).
CREATE USER app WITH PASSWORD 'app';
CREATE DATABASE app OWNER app;
CREATE DATABASE app_test OWNER app;
-- Lago installs extensions (pg_partman) during its migrations, which needs a superuser.
CREATE USER lago WITH PASSWORD 'lago' SUPERUSER;
CREATE DATABASE lago OWNER lago;
