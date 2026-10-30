(function(){
  const run=window.NEXUS_V25_RUN||{};
  run.runId='v217-'+window.NEXUS_ACTIVE_RUNTIME.id+'-2026-09-02';
  run.version='2.17.0';
  run.parentVersion='2.16.0-frozen';
  run.databaseConnector='portable-db-connector-1.0.0';
  run.apiContract='sandbox-resource-api-1.0.0';
  run.aiPolicy='CANDIDATE_ONLY';
  run.credentialPolicy='EPHEMERAL_OR_ENV_REF_ONLY';
  run.connectionMode='BACKEND_LOCAL_CONNECTOR';
  window.NEXUS_V25_RUN=run;
}());
