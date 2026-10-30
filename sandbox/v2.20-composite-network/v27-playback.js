(function(){
  const bridge=window.NEXUS_V24_BRIDGE;
  const state=bridge.state;
  const el=(id)=>document.getElementById(id);
  const stageIds=['shock','demand','route','constraint','chain','company','finance','attribution'];
  const stages=stageIds.map((id,index)=>({id,label:window.NEXUS_ACTIVE_RUNTIME.stageLabels[index]}));
  let timer=null;
  let speed=1100;

  function currentResult(){return bridge.current();}
  function updateKpis(){
    if(state.networkMode==='standalone'){
      const graph=bridge.getRuntimeNetwork(),entities=bridge.data.nodes.filter((node)=>node.layer==='company').length,metrics=bridge.data.nodes.filter((node)=>node.importSnapshot?.metricCodes?.length&&node.layer!=='company').length;
      el('v27IndustryValue').textContent=metrics+' 指标';
      el('v27Winner').textContent=entities+' 实体';
      el('v27Loser').textContent='ABSTAIN';
      el('v27Bottleneck').textContent=graph.relations.length+' 结构关系';
      return;
    }
    const result=currentResult();
    if(!result)return;
    const companies=[...result.base.companies].sort((a,b)=>b.valuation-a.valuation);
    const winner=companies[0],loser=companies.at(-1);
    el('v27IndustryValue').textContent=result.industryRange.base.toFixed(1);
    el('v27Winner').textContent=winner.name+' '+bridge.fmt(winner.valuation);
    el('v27Loser').textContent=loser.name+' '+bridge.fmt(loser.valuation);
    el('v27Bottleneck').textContent=result.base.constraints[0]?.label||'无显著瓶颈';
  }

  function applyStage(){
    const stage=Math.max(0,Math.min(stages.length-1,state.playbackStage));
    state.playbackStage=stage;
    document.body.classList.toggle('v27-playing',state.playbackActive);
    document.body.dataset.playbackStage=String(stage);
    el('v27StageState').textContent=String(stage+1).padStart(2,'0')+' / 08 · '+stages[stage].label;
    el('v27ProgressFill').style.width=((stage+1)/stages.length*100)+'%';
    el('v27Play').classList.toggle('active',Boolean(timer));
    el('v27PlayIcon').textContent=timer?'Ⅱ':'▶';
    el('v27PlayLabel').textContent=timer?'暂停':'播放传播';
    document.querySelectorAll('[data-v27-stage]').forEach((button)=>{
      const index=Number(button.dataset.v27Stage);
      button.classList.toggle('reached',index<=stage);
      button.classList.toggle('current',index===stage);
    });
    document.querySelectorAll('[data-v27-reveal]').forEach((item)=>item.classList.toggle('v27-revealed',stage>=Number(item.dataset.v27Reveal)));
    document.querySelectorAll('.bridge-node').forEach((node,index)=>{
      const revealed=stage>=7||(stage===6&&index<5);
      node.classList.toggle('v27-revealed',revealed);
      node.classList.toggle('v27-current',(stage===6&&index===4)||(stage===7&&index===5));
    });
    document.querySelectorAll('.rank-company').forEach((node)=>node.classList.toggle('v27-revealed',stage>=7));
    document.dispatchEvent(new CustomEvent('nexus:playback-stage',{detail:{stage}}));
  }

  function stop(){if(timer){clearInterval(timer);timer=null;}applyStage();}
  function advance(){
    if(state.playbackStage>=stages.length-1){stop();return;}
    state.playbackStage+=1;
    applyStage();
  }
  function play(){
    if(timer){stop();return;}
    if(state.playbackStage>=stages.length-1)state.playbackStage=0;
    state.playbackActive=true;
    applyStage();
    timer=setInterval(advance,speed);
    applyStage();
  }
  function replay(){stop();state.playbackActive=true;state.playbackStage=0;applyStage();play();}
  function step(){stop();state.playbackActive=true;state.playbackStage=Math.min(stages.length-1,state.playbackStage+1);applyStage();}

  el('v27Play').addEventListener('click',play);
  el('v27Replay').addEventListener('click',replay);
  el('v27Step').addEventListener('click',step);
  el('v27ShowAll').addEventListener('click',()=>{stop();state.playbackActive=false;state.playbackStage=stages.length-1;applyStage();});
  el('v27Speed').addEventListener('change',(event)=>{
    speed=Number(event.target.value);
    if(timer){stop();play();}
  });
  document.querySelectorAll('[data-v27-stage]').forEach((button)=>button.addEventListener('click',()=>{
    stop();state.playbackActive=true;state.playbackStage=Number(button.dataset.v27Stage);applyStage();
  }));
  document.addEventListener('nexus:render',()=>{updateKpis();requestAnimationFrame(applyStage);});
  document.addEventListener('nexus:standalone-network-applied',()=>{
    const labels=['数据范围','市场与成长','运营与效率','资本与风险','结果与质量','公司实体','实体对比','证据归档'];
    document.querySelectorAll('[data-v27-stage]').forEach((button,index)=>button.textContent=labels[index]);
    state.playbackActive=false;state.playbackStage=stages.length-1;updateKpis();applyStage();
  });
  const params=new URLSearchParams(window.location.search);
  const requestedStage=Number(params.get('stage'));
  if(params.has('stage')&&Number.isInteger(requestedStage)&&requestedStage>=0&&requestedStage<stages.length){state.playbackActive=true;state.playbackStage=requestedStage;}
  updateKpis();
  applyStage();
  if(params.get('autoplay')==='1')setTimeout(replay,250);
  window.NEXUS_V27_PLAYBACK={stages,play,replay,step,stop,applyStage};
}());
