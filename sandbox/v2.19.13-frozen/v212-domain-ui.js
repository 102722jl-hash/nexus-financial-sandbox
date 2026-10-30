(function(){
  const runtime=window.NEXUS_ACTIVE_RUNTIME,pkg=window.NEXUS_ACTIVE_PACKAGE,bridge=window.NEXUS_V24_BRIDGE,baseEngine=window.SANDBOX_ENGINE,api=window.NEXUS_API_CLIENT;
  const el=(id)=>document.getElementById(id);
  const builtins=new Set(['ai-infrastructure','coal-steel']);
  const axisSub={macro:'MACRO & EXTERNAL',demand:'DEMAND & PRICE',route:'SUPPLY & ROUTES',constraint:'INVENTORY & CAPACITY',chain:'VALUE POOLS',company:'COMPANY MODELS'};
  function applyDomainCopy(){
    document.body.dataset.domain=runtime.id;
    document.title='NEXUS V2.19 · '+runtime.name;
    el('domainSelect').value=runtime.id;
    el('domainCaseLabel').textContent='FINANCIAL WORLD SANDBOX · '+(runtime.id==='coal-steel'?'CASE 02':'CASE 01');
    el('domainCaseTitle').textContent='金融沙盒推演 · '+runtime.caseTitle;
    el('domainCaseDescription').textContent=runtime.caseDescription;
    el('domainStateTitle').textContent=runtime.id==='coal-steel'?'煤炭—钢铁领域包':'AI 基础设施领域包';
    el('domainStateDetail').textContent=pkg.version+' · '+pkg.nodes.length+' 节点 / '+pkg.edges.length+' 边';
    document.getElementById('networkCanvas').setAttribute('aria-label',runtime.name+'金融世界网络');
    pkg.layers.forEach((layer)=>{
      const heading=document.querySelector('[data-axis-layer="'+layer.id+'"]');
      if(heading){heading.querySelector('b').textContent=layer.title;heading.querySelector('small').textContent=runtime.id==='coal-steel'?axisSub[layer.id]:heading.querySelector('small').textContent;}
      const rail=document.querySelector('.layer[data-layer="'+layer.id+'"] span');if(rail)rail.textContent=layer.title;
    });
    document.querySelectorAll('[data-v27-stage]').forEach((button,index)=>{button.textContent=runtime.stageLabels[index]});
    if(runtime.id==='coal-steel')document.querySelectorAll('[data-focus="upstream"],[data-focus="capacity"],[data-focus="infrastructure"]').forEach((item)=>item.hidden=true);
  }
  function renderPresets(){
    const container=el('quickPresets'),separator=container.querySelector('.preset-separator');
    container.querySelectorAll('[data-preset]').forEach((item)=>item.remove());
    runtime.presets.forEach(([text,label])=>{
      const button=document.createElement('button');button.type='button';button.dataset.preset=text;button.textContent=label;
      button.addEventListener('click',()=>{const parsed=baseEngine.parseScenario(text);if(parsed.error)return;bridge.state.scenarios[bridge.state.active].text=text;bridge.state.scenarios[bridge.state.active].shocks=parsed.shocks;bridge.render();});
      container.insertBefore(button,separator);
    });
  }
  function updateDelete(){
    el('deleteNetwork').disabled=!el('domainSelect').value.startsWith('generated:');
  }
  function rememberNetwork(networkId){const url=new URL(window.location.href);if(networkId)url.searchParams.set('network',networkId);else url.searchParams.delete('network');window.history.replaceState(null,'',url.toString());}
  async function loadGenerated(value,remember=true){
    const networkId=value.slice('generated:'.length),response=await api.networks.get(networkId);
    if(response.state!=='ready'){el('domainSelect').value=runtime.id;rememberNetwork(null);updateDelete();return false}
    const applied=bridge.applyStandaloneNetwork(response.data);
    if(applied.applied){document.body.dataset.domain='generated-network';el('domainSelect').value=value;if(remember)rememberNetwork(networkId);updateDelete();return true}
    return false;
  }
  async function refreshNetworks(preferred){
    if(!api?.networks)return;
    const response=await api.networks.list();if(response.state!=='ready')return;
    el('domainSelect').querySelectorAll('[data-generated-network]').forEach((option)=>option.remove());
    for(const network of response.data.networks||[]){
      const option=document.createElement('option');option.value='generated:'+network.networkId;option.dataset.generatedNetwork='true';option.textContent=(network.networkName||'导入网络')+' · 自定义';el('domainSelect').appendChild(option);
    }
    const requested=preferred||((new URLSearchParams(window.location.search)).get('network')?'generated:'+(new URLSearchParams(window.location.search)).get('network'):null);
    if(requested&&el('domainSelect').querySelector('option[value="'+CSS.escape(requested)+'"]')){
      el('domainSelect').value=requested;
      if(preferred)rememberNetwork(requested.slice('generated:'.length));else await loadGenerated(requested,false);
    }else if(!preferred&&(new URLSearchParams(window.location.search)).get('network'))rememberNetwork(null);
    updateDelete();
  }
  async function switchDomain(event){
    const next=event.target.value;
    if(next.startsWith('generated:')){await loadGenerated(next,true);return;}
    if(!builtins.has(next))return;
    if(next===runtime.id){bridge.restoreStaticNetwork();rememberNetwork(null);applyDomainCopy();renderPresets();updateDelete();return}
    const url=new URL(window.location.href);url.searchParams.set('domain',next);url.searchParams.delete('network');url.searchParams.set('v','2.19.12');window.location.assign(url.toString());
  }
  async function deleteCurrentNetwork(){
    const value=el('domainSelect').value;if(!value.startsWith('generated:'))return;
    const option=el('domainSelect').selectedOptions[0];
    if(!window.confirm('删除“'+option.textContent.replace(/ · 自定义$/,'')+'”？数据库源和原始表不会删除。'))return;
    const response=await api.networks.delete(value.slice('generated:'.length));if(response.state!=='ready')return;
    bridge.restoreStaticNetwork({clearWorkspace:true});rememberNetwork(null);applyDomainCopy();renderPresets();await refreshNetworks();el('domainSelect').value=runtime.id;updateDelete();
  }
  el('domainSelect').addEventListener('change',switchDomain);
  el('deleteNetwork').addEventListener('click',deleteCurrentNetwork);
  document.addEventListener('nexus:network-registered',(event)=>refreshNetworks('generated:'+event.detail.networkId));
  applyDomainCopy();renderPresets();refreshNetworks();
  window.NEXUS_V212_DOMAIN_UI={runtime,applyDomainCopy,switchDomain,refreshNetworks,deleteCurrentNetwork};
}());
