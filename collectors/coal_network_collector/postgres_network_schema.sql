-- Target schema for the model connector. Run as an owner/admin account.
CREATE SCHEMA IF NOT EXISTS coal_network;

CREATE TABLE IF NOT EXISTS coal_network.network_registry (LIKE public.network_registry INCLUDING ALL);
CREATE TABLE IF NOT EXISTS coal_network.network_layers (LIKE public.network_layers INCLUDING ALL);
CREATE TABLE IF NOT EXISTS coal_network.entities (LIKE public.entities INCLUDING ALL);
CREATE TABLE IF NOT EXISTS coal_network.evidence (LIKE public.evidence INCLUDING ALL);
CREATE TABLE IF NOT EXISTS coal_network.metric_values (LIKE public.metric_values INCLUDING ALL);
CREATE TABLE IF NOT EXISTS coal_network.formulas (LIKE public.formulas INCLUDING ALL);
CREATE TABLE IF NOT EXISTS coal_network.network_nodes (LIKE public.network_nodes INCLUDING ALL);
CREATE TABLE IF NOT EXISTS coal_network.network_edges (LIKE public.network_edges INCLUDING ALL);
CREATE TABLE IF NOT EXISTS coal_network.valuation (LIKE public.valuation INCLUDING ALL);
CREATE TABLE IF NOT EXISTS coal_network.review_queue (LIKE public.review_queue INCLUDING ALL);
CREATE TABLE IF NOT EXISTS coal_network.raw_documents (LIKE public.raw_documents INCLUDING ALL);

COMMENT ON SCHEMA coal_network IS 'Generated coal-power transmission network; synchronized from the local audited collector';
COMMENT ON TABLE coal_network.network_registry IS 'Network registry';
COMMENT ON TABLE coal_network.network_nodes IS 'Candidate and formal network nodes';
COMMENT ON TABLE coal_network.network_edges IS 'Candidate and formal network edges';
COMMENT ON TABLE coal_network.metric_values IS 'Normalized source metrics';
COMMENT ON TABLE coal_network.evidence IS 'Auditable source evidence';
