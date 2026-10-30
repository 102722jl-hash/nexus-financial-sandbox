(function(){
  const runtime=window.NEXUS_ACTIVE_RUNTIME,pkg=window.NEXUS_ACTIVE_PACKAGE,bridge=window.NEXUS_V24_BRIDGE,baseEngine=window.SANDBOX_ENGINE,api=window.NEXUS_API_CLIENT;
  const el=(id)=>document.getElementById(id);
  const builtins=new Set(['ai-infrastructure','coal-steel']);
  const networkDisplayTimeZone='Asia/Shanghai';
  let switchSequence=0,committedValue=runtime.id,networkCatalog=new Map();
  const axisSub={macro:'MACRO & EXTERNAL',demand:'DEMAND & PRICE',route:'SUPPLY & ROUTES',constraint:'INVENTORY & CAPACITY',chain:'VALUE POOLS',company:'COMPANY MODELS'};
  function applyDomainCopy(){
    document.body.dataset.domain=runtime.id;
    document.title='NEXUS V2.20 · '+runtime.name;
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
    const value=el('domainSelect').value,item=value.startsWith('generated:')?networkCatalog.get(value.slice('generated:'.length)):null;
    el('deleteNetwork').disabled=!item||item.deletable===false;
  }
  function rememberNetwork(networkId){const url=new URL(window.location.href);if(networkId)url.searchParams.set('network',networkId);else url.searchParams.delete('network');window.history.replaceState(null,'',url.toString());}
  function setSwitchBusy(active){el('domainSelect').disabled=active;el('domainSelect').dataset.loading=active?'true':'false';if(active)el('deleteNetwork').disabled=true;else updateDelete()}
  function restoreCommittedSelection(){el('domainSelect').value=committedValue;rememberNetwork(committedValue.startsWith('generated:')?committedValue.slice('generated:'.length):null);updateDelete()}
  function networkUploadParts(network){
    const stamp=network.createdAt||network.dataCutoff;
    if(!stamp)return{date:'日期未知',time:'',second:''};
    const parsed=new Date(stamp),fallback=String(stamp).slice(0,10);
    if(Number.isNaN(parsed.getTime()))return{date:/^\d{4}-\d{2}-\d{2}$/.test(fallback)?fallback:'日期未知',time:'',second:''};
    const parts=Object.fromEntries(new Intl.DateTimeFormat('zh-CN',{timeZone:networkDisplayTimeZone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(parsed).filter((item)=>item.type!=='literal').map((item)=>[item.type,item.value]));
    return{date:parts.year+'-'+parts.month+'-'+parts.day,time:parts.hour+':'+parts.minute,second:parts.second};
  }
  function decorateNetworkDates(networks){
    const decorated=networks.map((network)=>({network,parts:networkUploadParts(network)})),dateCounts=new Map(),minuteCounts=new Map();
    decorated.forEach(({parts})=>{dateCounts.set(parts.date,(dateCounts.get(parts.date)||0)+1);const minute=parts.date+' '+parts.time;minuteCounts.set(minute,(minuteCounts.get(minute)||0)+1)});
    return decorated.map(({network,parts})=>{
      let label=parts.date;
      if(parts.time&&dateCounts.get(parts.date)>1)label+=' '+parts.time;
      if(parts.second&&minuteCounts.get(parts.date+' '+parts.time)>1)label+=':'+parts.second;
      return{network,label};
    });
  }
  async function loadGenerated(value,remember=true,sequence=++switchSequence){
    const previous=committedValue;let applicationStarted=false;setSwitchBusy(true);
    try{
      const networkId=value.slice('generated:'.length),response=await api.networks.get(networkId);
      if(sequence!==switchSequence)return false;
      if(response.state!=='ready'){committedValue=previous;restoreCommittedSelection();return false}
      applicationStarted=true;
      const applied=bridge.applyStandaloneNetwork(response.data);
      if(!applied.applied)throw new Error(applied.reason||'GENERATED_NETWORK_APPLY_FAILED');
      document.body.dataset.domain='generated-network';committedValue=value;el('domainSelect').value=value;if(remember)rememberNetwork(networkId);return true;
    }catch(error){
      if(sequence!==switchSequence)return false;
      let restored=previous;
      if(applicationStarted){
        bridge.restoreStaticNetwork();
        if(previous.startsWith('generated:')){
          const prior=await api.networks.get(previous.slice('generated:'.length));
          if(sequence!==switchSequence)return false;
          try{if(prior.state!=='ready'||!bridge.applyStandaloneNetwork(prior.data).applied)throw new Error('PREVIOUS_NETWORK_RESTORE_FAILED')}
          catch(restoreError){restored=runtime.id;applyDomainCopy();renderPresets()}
        }else{applyDomainCopy();renderPresets()}
      }
      committedValue=restored;restoreCommittedSelection();
      return false;
    }finally{if(sequence===switchSequence)setSwitchBusy(false)}
  }
  async function refreshNetworks(preferred){
    if(!api?.networks)return;
    const response=await api.networks.list();if(response.state!=='ready')return;
    el('domainSelect').querySelectorAll('[data-generated-network]').forEach((option)=>option.remove());networkCatalog=new Map();
    for(const {network,label} of decorateNetworkDates(response.data.networks||[])){
      networkCatalog.set(network.networkId,network);const option=document.createElement('option');option.value='generated:'+network.networkId;option.dataset.generatedNetwork='true';option.dataset.deletable=String(network.deletable!==false);option.textContent=(network.networkName||'导入网络')+' · 自定义 · '+Number(network.nodeCount||0)+'节点/'+Number(network.edgeCount||0)+'关系 · '+label;el('domainSelect').appendChild(option);
    }
    const requested=preferred||((new URLSearchParams(window.location.search)).get('network')?'generated:'+(new URLSearchParams(window.location.search)).get('network'):null);
    if(requested&&el('domainSelect').querySelector('option[value="'+CSS.escape(requested)+'"]')){
      el('domainSelect').value=requested;
      if(preferred){committedValue=requested;rememberNetwork(requested.slice('generated:'.length));}else await loadGenerated(requested,false,++switchSequence);
    }else if(!preferred&&(new URLSearchParams(window.location.search)).get('network'))rememberNetwork(null);
    updateDelete();
  }
  async function switchDomain(event){
    const next=event.target.value,sequence=++switchSequence;
    if(next.startsWith('generated:')){await loadGenerated(next,true,sequence);return;}
    if(!builtins.has(next))return;
    if(next===runtime.id){bridge.restoreStaticNetwork();committedValue=runtime.id;rememberNetwork(null);applyDomainCopy();renderPresets();setSwitchBusy(false);return}
    const url=new URL(window.location.href);url.searchParams.set('domain',next);url.searchParams.delete('network');url.searchParams.set('v','2.20.0');window.location.assign(url.toString());
  }
  async function deleteCurrentNetwork(){
    const value=el('domainSelect').value;if(!value.startsWith('generated:'))return;
    const option=el('domainSelect').selectedOptions[0];
    if(!window.confirm('删除“'+option.textContent.replace(/ · 自定义$/,'')+'”？数据库源和原始表不会删除。'))return;
    const response=await api.networks.delete(value.slice('generated:'.length));if(response.state!=='ready'){window.alert(response.error?.message||response.error?.detail||'网络删除失败');return;}
    ++switchSequence;bridge.restoreStaticNetwork({clearWorkspace:true});committedValue=runtime.id;rememberNetwork(null);applyDomainCopy();renderPresets();await refreshNetworks();el('domainSelect').value=runtime.id;updateDelete();
  }
  el('domainSelect').addEventListener('change',switchDomain);
  el('deleteNetwork').addEventListener('click',deleteCurrentNetwork);
  document.addEventListener('nexus:network-registered',(event)=>refreshNetworks('generated:'+event.detail.networkId));
  applyDomainCopy();renderPresets();refreshNetworks();
  window.NEXUS_V212_DOMAIN_UI={runtime,applyDomainCopy,switchDomain,refreshNetworks,deleteCurrentNetwork};
}());
