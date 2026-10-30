(()=>{
  const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');let checks=0;
  const source=(name)=>fs.readFileSync(path.join(__dirname,name),'utf8'),check=(value,message)=>{assert.ok(value,message);checks++};
  const html=source('index.html'),server=source('server.py'),pipeline=source('v218_pipeline.py'),app=source('app.js'),ui=source('v218-pipeline-ui.js'),mock=source('mock-adapter.js');
  check(html.includes('NEXUS V2.19')&&html.includes('id="v219NetworkMode"'),'V2.19 页面缺少独立网络入口');
  check(html.includes('CREATE_NEW_NETWORK')&&html.includes('创建全新网络'),'生成方式必须明确');
  check(pipeline.includes('build_generated_network_plan')&&pipeline.includes('FINANCIAL_DISCLOSURE_NETWORK'),'后端缺少独立图编译器');
  check(pipeline.includes('CONFIRMED_LINEAGE')&&pipeline.includes('CONFIRMED_STRUCTURE'),'披露关系必须和因果边区分');
  check(server.includes('plan.get("mode") == "CREATE_NEW_NETWORK"')&&server.includes('"outputLevel": "EXPOSURE_ONLY"'),'独立网络必须执行情景门禁');
  check(app.includes('function applyStandaloneNetwork')&&app.includes("data.nodes.splice(0,data.nodes.length)"),'画布必须真正替换节点');
  check(app.includes("state.networkMode==='standalone'?runtimeVisualEdges"),'独立画布不得绘制静态领域边');
  check(ui.includes("bridge.applyStandaloneNetwork")&&ui.includes("el('v218Run').disabled=standalone"),'激活后必须打开新图并禁用无依据推演');
  check(mock.includes('PLAN-MOCK-GENERATED')&&mock.includes('entity-600019-sh'),'Mock 必须覆盖独立网络');
  check(server.includes('/api/networks')&&server.includes('persist_network')&&server.includes('do_DELETE'),'生成网络必须可注册、重载和删除');
  check(ui.includes('nexus:network-registered')&&source('v212-domain-ui.js').includes('deleteCurrentNetwork'),'右上角必须注册生成网络并支持删除');
check(!html.includes('data-view="compare"')&&!html.includes('data-view="model"')&&!app.includes('renderStandaloneCompare')&&app.includes("state.playbackActive||Math.abs(contribution)>.01"),'情景实验室和模型参数必须完全移除，同时保留动态谱系播放');
  new Function(app);new Function(ui);new Function(mock);checks+=3;
  console.log('Financial sandbox V2.19 contract tests: '+checks+'/'+checks+' passed');
})();
