(function(){
  const requested=new URLSearchParams(window.location.search).get('domain');
  const domain=requested==='coal-steel'?'coal-steel':'ai-infrastructure';
  window.NEXUS_REQUESTED_DOMAIN=domain;
  const scripts=domain==='coal-steel'?
    ['coal-data.js','coal-db-snapshot.js','coal-semantics.js','legacy-engine.js','coal-model-config.js','coal-engine.js','data-contract.js','domain-coal-steel.js','coal-company-adapter.js','domain-coal-package.js']:
    ['legacy-data.js','v26-semantics.js','legacy-engine.js','v2-model-config.js','v2-engine.js','data-contract.js','domain-ai-infra.js','db-coverage-snapshot.js','company-adapter.js','domain-ai-package.js'];
  document.write(scripts.map((src)=>'<script src="'+src+'?v=2.17.0"></scr'+'ipt>').join(''));
}());
