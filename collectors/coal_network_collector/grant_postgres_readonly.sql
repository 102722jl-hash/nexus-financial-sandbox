-- Run as PostgreSQL owner/admin after the target schema exists.
-- Replace the role name with the read-only user entered in the model UI.
CREATE ROLE coal_network_readonly LOGIN PASSWORD 'SET_THIS_ONLY_IN_PSQL_NOT_IN_REPO';
GRANT USAGE ON SCHEMA coal_network TO coal_network_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA coal_network TO coal_network_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA coal_network GRANT SELECT ON TABLES TO coal_network_readonly;
ALTER ROLE coal_network_readonly SET default_transaction_read_only = on;
