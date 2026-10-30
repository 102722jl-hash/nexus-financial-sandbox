(function(){
  const workbench=window.NEXUS_V216_WORKBENCH;
  const api=window.NEXUS_API_CLIENT;
  const el=(id)=>document.getElementById(id);
  if(!workbench)return;
  let discovered=[];
  let session={connectionId:null,sourceId:null,connectionReady:false};
  const esc=(value)=>String(value??'').replace(/[&<>"']/g,(char)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

  function config(includeTables){
    const type=el('v217DbType').value;
    const selected=includeTables?[...document.querySelectorAll('[data-v217-table]:checked')].map((item)=>item.value):[];
    return{
      type,
      host:el('v217DbHost').value.trim(),
      port:Number(el('v217DbPort').value),
      database:el('v217DbName').value.trim(),
      user:el('v217DbUser').value.trim(),
      password:el('v217DbPassword').value,
      credentialRef:el('v217DbCredentialRef').value.trim(),
      schema:el('v217DbSchema').value.trim(),
      sslmode:el('v217DbSsl').value,
      tables:selected
    };
  }
  function safeSource(connection,data){
    return{
      sourceType:connection.type.toUpperCase(),
      fileName:connection.database+'.'+connection.schema,
      snapshot:'METADATA_ONLY',
      sourceHash:data.sourceHash,
      server:connection.host+':'+connection.port,
      selectedTables:data.selectedTables||[],
      credentialPersisted:false
    };
  }
  function renderTables(){
    el('v217DbTables').innerHTML=discovered.length?'<div class="v217-table-head"><span>允许画像的表</span><b>已发现 '+discovered.length+' 张</b></div><div class="v217-table-list">'+discovered.map((table)=>'<label><input type="checkbox" data-v217-table value="'+esc(table.name)+'"><span>'+esc(table.schema+'.'+table.name)+'</span></label>').join('')+'</div>':'<p>当前 Schema 没有可见表。</p>';
    el('v217ProfileTables').disabled=!discovered.length;
    updateSelection();
  }
  function updateSelection(){
    const count=document.querySelectorAll('[data-v217-table]:checked').length;
    el('v217SelectedCount').textContent='已选 '+count+' 张表';
    el('v217ProfileTables').disabled=!count;
  }
  function renderAdapters(adapters){
    el('v217AdapterSummary').innerHTML=adapters?.length?adapters.map((item)=>{const period=item.reportPeriodSource==='SOURCE_COLUMN'?'报告期由来源字段提供':item.reportPeriodHint?'报告期候选 '+esc(item.reportPeriodHint):'缺少报告期字段或表名年份';const date=item.availableDateMode==='SOURCE_COLUMN'?'可见日期由来源字段提供':'无公告日时使用同步截止日，仅限当前快照';return'<div class="v219-adapter-row"><b>'+esc(item.qualifiedDisplay)+'</b><span>'+esc(item.profileStatus)+' · '+Number(item.columnCount||0)+' 列</span><small>'+esc(item.identifierMode)+' / '+esc(item.sourceFieldMode)+' / '+esc(item.syncMode)+'</small><em>'+period+' · '+date+'</em></div>';}).join(''):'<p>尚未建立表适配器。</p>';
  }
  function reason(response,fallback){return response?.error?.message||response?.data?.detail||fallback}
  async function discover(){
    const connection=config(false);
    el('v217DbFailure').textContent='';el('v217DbState').textContent='正在发现数据表';el('v217DiscoverTables').disabled=true;
    try{
      let response;
      if(!session.connectionId){
        const tested=await api.connections.test(connection);
        if(tested.state==='permission_denied')throw new Error('权限不足');
        if(tested.state==='error')throw new Error(reason(tested,'数据库连接测试失败'));
        const created=await api.connections.create(connection);
        if(created.state==='permission_denied')throw new Error('权限不足');
        if(created.state==='error')throw new Error(reason(created,'数据库会话创建失败'));
        session={connectionId:created.data.connectionId,sourceId:created.data.sourceId,connectionReady:true};
        response=tested;
      }else{
        response=await api.connections.tables(session.connectionId);
        if(response.state==='permission_denied')throw new Error('权限不足');
        if(response.state==='error')throw new Error(reason(response,'读取表清单失败'));
      }
      const data=response.data;
      discovered=(data.tables||[]).map((item)=>typeof item==='string'?{name:item,schema:connection.schema}:item);
      renderTables();
      el('v217DbState').textContent='连接正常 · 已发现数据表';el('v217ProfileProgress').textContent='等待选择';
      workbench.state.connector='LOCAL CONNECTOR';workbench.state.profile=data.summary;workbench.state.tasks=data.tasks||workbench.state.tasks;workbench.render();
    }catch(error){
      session={connectionId:null,sourceId:null,connectionReady:false};el('v217DbState').textContent='数据库连接失败';el('v217DbFailure').textContent=error.message;
      workbench.state.quarantine=[{code:'DATABASE_CONNECTION_FAILED',reason:error.message}];
      workbench.render();
    }finally{
      el('v217DbPassword').value='';el('v217DiscoverTables').disabled=false;
    }
  }
  async function profileSelected(){
    const connection=config(true),tables=connection.tables;if(!tables.length){el('v217DbFailure').textContent='请至少选择一张表';return}
    el('v217DbFailure').textContent='';el('v217DbState').textContent='连接正常 · 正在画像';el('v217ProfileTables').disabled=true;
    let analyzed=null,currentTable='';
    try{
      for(let index=0;index<tables.length;index+=1){
        currentTable=tables[index];el('v217ProfileProgress').textContent='正在画像 '+(index+1)+' / '+tables.length+' · '+currentTable;
        const response=await api.sources.analyze(session.sourceId,{tables:[currentTable],append:true,reset:index===0,totalTables:tables.length,networkIntent:el('v219NetworkMode').value});
        if(response.state==='permission_denied')throw new Error('权限不足');
        if(response.state==='error')throw new Error(reason(response,'表画像失败'));
        analyzed=response.data;el('v217ProfileProgress').textContent='已完成 '+(index+1)+' / '+tables.length;
      }
      renderAdapters(analyzed.tableAdapters||[]);
      workbench.acceptDatabaseProfile(analyzed,safeSource(connection,analyzed));
      window.dispatchEvent(new CustomEvent('nexus:source-analyzed',{detail:{sourceId:session.sourceId,mappings:analyzed.mappings||[],metricCatalog:analyzed.metricCatalog||[],sourceType:'DATABASE',tables,networkIntent:analyzed.networkIntent||el('v219NetworkMode').value,precompiledAdapter:analyzed.precompiledAdapter}}));
      const compiled=analyzed.precompiledAdapter;el('v217DbState').textContent=compiled?.detected?'连接正常 · 已识别预编译网络表':'连接正常 · 画像完成';el('v217ProfileProgress').textContent=compiled?.detected?'结构签名通过 · 自动确认 '+Number(compiled.autoConfirmed||0)+' 列 · 待审核 '+Number(compiled.needsReview||0)+' 列':'画像完成 '+tables.length+' / '+tables.length;
    }catch(error){
      el('v217DbState').textContent='连接正常 · 画像失败';el('v217DbFailure').textContent='表 '+currentTable+'：'+error.message;
      workbench.state.quarantine=[{code:'DATABASE_TABLE_PROFILE_FAILED',table:currentTable,reason:error.message}];workbench.render();
    }finally{updateSelection()}
  }
  async function request(includeTables){return includeTables?profileSelected():discover()}
  function setDefaults(){
    const mysql=el('v217DbType').value==='mysql';
    el('v217DbPort').value=mysql?'3306':'5432';
    el('v217DbSchema').value=mysql?el('v217DbName').value.trim():'public';
    el('v217DbSsl').innerHTML=mysql?'<option value="preferred">preferred</option><option value="required">required</option><option value="disabled">disabled</option>':'<option value="prefer">prefer</option><option value="require">require</option><option value="verify-full">verify-full</option><option value="disable">disable</option>';
    discovered=[];session={connectionId:null,sourceId:null,connectionReady:false};renderTables();renderAdapters([]);
  }
  el('v217DbType').addEventListener('change',setDefaults);
  el('v217DbName').addEventListener('change',()=>{if(el('v217DbType').value==='mysql'&&!el('v217DbSchema').value.trim())el('v217DbSchema').value=el('v217DbName').value.trim();});
  el('v217DbTables').addEventListener('change',(event)=>{if(event.target.matches('[data-v217-table]'))updateSelection()});
  ['v217DbHost','v217DbPort','v217DbName','v217DbUser','v217DbSchema'].forEach((id)=>el(id).addEventListener('change',()=>{session={connectionId:null,sourceId:null,connectionReady:false};discovered=[];renderTables();renderAdapters([]);el('v217DbState').textContent='连接配置已修改'}));
  el('v217DiscoverTables').addEventListener('click',discover);
  el('v217ProfileTables').addEventListener('click',profileSelected);
  window.addEventListener('nexus:intent-changed',()=>{if(session.sourceId){el('v217DbState').textContent='连接正常 · 导入目标已改变';el('v217ProfileProgress').textContent='请重新画像选定表';}});
  window.addEventListener('nexus:workspace-restored',(event)=>{
    const data=event.detail||{},source=data.source,connection=data.connection;if(!source)return;
    session={connectionId:source.connectionId,sourceId:source.sourceId,connectionReady:Boolean(source.connectionId)};
    if(connection){el('v217DbType').value=connection.type||'postgresql';el('v217DbHost').value=connection.host||'';el('v217DbPort').value=connection.port||'';el('v217DbName').value=connection.database||'';el('v217DbUser').value=connection.user||'';el('v217DbSchema').value=connection.schema||'';}
    discovered=(source.selectedTables||[]).map((name)=>({name,schema:connection?.schema||'public'}));renderTables();document.querySelectorAll('[data-v217-table]').forEach((input)=>input.checked=true);updateSelection();renderAdapters(source.tableAdapters||[]);
    el('v217DbState').textContent='已恢复只读工作区';el('v217ProfileProgress').textContent='已恢复 '+discovered.length+' 张表 · 密码未保存';
  });
  window.NEXUS_V217_DB_UI={config,request,discover,profileSelected,getSession:()=>({...session})};
}());
