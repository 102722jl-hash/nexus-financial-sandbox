(function(root){
  const layers=['macro','demand','route','constraint','chain','company'];
  const catalogs={
    'ai-infrastructure':{
      id:'ai-infrastructure',name:'AI 基础设施',status:'SUPPORTED',
      keywords:['ai','gpu','hbm','cowos','inference','token','datacenter','data_center','accelerator','semiconductor','wafer','cloud_capex','算力','推理','数据中心','晶圆','先进封装','高带宽存储'],
      nodeIds:['rates','exportControl','powerSupply','itCycle','aiAdoption','aiCapex','trainingDemand','inferenceCost','tokenDemand','sovereignDemand','dcBuildout','generalGpu','customAsic','domesticCompute','opticalScale','efficiency','hbmSupply','cowosCapacity','waferCapacity','networkCapacity','transformerCapacity','coolingCapacity','constructionLabor','accelerators','memoryStack','foundryPackage','networkFabric','powerCooling','cloudServices','aiSoftware','nvda','amd','avgo','tsmc','skhynix','micron','arista','vertiv','eaton','msft'],
      companies:[
        {id:'nvda',name:'NVIDIA',aliases:['nvda','nvidia','英伟达']},{id:'amd',name:'AMD',aliases:['amd']},{id:'avgo',name:'Broadcom',aliases:['avgo','broadcom','博通']},{id:'tsmc',name:'TSMC',aliases:['tsmc','tsm','台积电']},{id:'skhynix',name:'SK hynix',aliases:['skhynix','sk_hynix','000660.ks','海力士']},{id:'micron',name:'Micron',aliases:['micron','mu','美光']},{id:'arista',name:'Arista',aliases:['arista','anet']},{id:'vertiv',name:'Vertiv',aliases:['vertiv','vrt']},{id:'eaton',name:'Eaton',aliases:['eaton','etn']},{id:'msft',name:'Microsoft',aliases:['microsoft','msft','微软']}
      ],
      metrics:[
        ['rates','实际利率',['real_rate','interest_rate','actual_rate','实际利率']],['exportControl','出口管制强度',['export_control','trade_restriction','出口管制']],['powerSupply','可用电力供给',['power_supply','grid_capacity','available_power','电力供给']],['itCycle','企业 IT 景气',['it_cycle','enterprise_it','it景气']],['aiAdoption','AI 应用渗透',['ai_adoption','adoption_rate','ai渗透率']],['aiCapex','云厂商 AI 资本开支',['ai_capex','cloud_capex','hyperscaler_capex','ai资本开支']],['trainingDemand','训练算力需求',['training_demand','training_compute','训练算力']],['inferenceCost','单位推理成本',['inference_cost','cost_per_token','推理成本']],['tokenDemand','推理 Token 需求',['token_demand','token_volume','推理token']],['sovereignDemand','主权算力需求',['sovereign_demand','sovereign_ai','主权算力']],['dcBuildout','数据中心新建',['dc_buildout','datacenter_buildout','data_center_buildout','数据中心新建']],['generalGpu','通用 GPU 路线',['gpu_supply','general_gpu','gpu出货']],['customAsic','定制 ASIC 路线',['custom_asic','asic_supply','定制asic']],['domesticCompute','本地替代算力',['domestic_compute','local_accelerator','国产算力']],['opticalScale','光互连扩展',['optical_scale','optical_interconnect','光互连']],['efficiency','软件效率提升',['software_efficiency','compute_efficiency','软件效率']],['hbmSupply','HBM 有效供给',['hbm_supply','hbm_capacity','hbm_bit_shipment','hbm供给']],['cowosCapacity','CoWoS 先进封装',['cowos_capacity','advanced_packaging','cowos产能']],['waferCapacity','先进制程晶圆',['wafer_capacity','advanced_wafer','晶圆产能']],['networkCapacity','高速网络供给',['network_capacity','switch_capacity','高速网络供给']],['transformerCapacity','变压器 / 配电产能',['transformer_capacity','power_equipment_capacity','变压器产能']],['coolingCapacity','液冷交付能力',['cooling_capacity','liquid_cooling','液冷交付']],['constructionLabor','工程施工能力',['construction_labor','engineering_capacity','施工能力']],['accelerators','AI 加速卡',['accelerator_revenue','gpu_revenue','加速卡收入']],['memoryStack','HBM 存储价值',['hbm_revenue','memory_stack','hbm收入']],['foundryPackage','晶圆代工与封装',['foundry_revenue','packaging_revenue','晶圆代工']],['networkFabric','网络与光互连',['network_revenue','optical_revenue','网络收入']],['powerCooling','电力与液冷系统',['power_cooling_revenue','thermal_revenue','液冷收入']],['cloudServices','云与算力服务',['cloud_revenue','ai_cloud_revenue','云收入']],['aiSoftware','AI 软件与应用',['ai_software_revenue','ai_application_revenue','ai软件收入']]]
    },
    'coal-steel':{
      id:'coal-steel',name:'焦煤—钢铁',status:'SUPPORTED',
      keywords:['coal','coking','coke','steel','blast_furnace','bof','eaf','scrap','mine','jm.dce','焦煤','煤炭','焦化','钢材','钢铁','高炉','废钢','港口库存'],
      nodeIds:['cokingCoalPrice','steelDemand','minePolicy','rates','coalRealization','steelRawCost','steelOrders','cokeDemand','mineVolume','importSubstitution','bofRoute','eafRoute','mineHeadroom','portInventory','cokeCapacity','steelUtilization','scrapSupply','coalMiningPool','cokingPool','blastFurnacePool','specialSteelPool','downstreamPool','shenhua','shaanxi','yankuang','baosteel','citicsteel'],
      companies:[
        {id:'shenhua',name:'中国神华',aliases:['601088.sh','601088','中国神华','shenhua']},{id:'shaanxi',name:'陕西煤业',aliases:['601225.sh','601225','陕西煤业']},{id:'yankuang',name:'兖矿能源',aliases:['600188.sh','600188','兖矿能源','yankuang']},{id:'baosteel',name:'宝钢股份',aliases:['600019.sh','600019','宝钢股份','baosteel']},{id:'citicsteel',name:'中信特钢',aliases:['000708.sz','000708','中信特钢']}
      ],
      metrics:[
        ['cokingCoalPrice','焦煤价格',['coking_coal_price','jm_price','jm.dce','焦煤价格']],['steelDemand','钢材终端需求',['steel_demand','steel_consumption','钢材需求']],['minePolicy','煤矿供给政策',['mine_policy','coal_supply_policy','煤矿供给']],['rates','实际利率',['real_rate','interest_rate','实际利率']],['coalRealization','煤炭实现售价',['coal_realization','realized_coal_price','煤炭实现售价']],['steelRawCost','钢铁原料成本',['steel_raw_cost','raw_material_cost','钢铁原料成本']],['steelOrders','钢材订单',['steel_orders','steel_order','钢材订单']],['cokeDemand','焦化需求',['coke_demand','coking_demand','焦化需求']],['mineVolume','煤炭销量',['mine_volume','coal_sales_volume','煤炭销量']],['importSubstitution','进口替代',['import_substitution','import_mix','进口替代']],['bofRoute','高炉—转炉路线',['bof_route','blast_furnace','bf_bof']],['eafRoute','电炉替代路线',['eaf_route','electric_arc_furnace','电炉路线']],['mineHeadroom','煤矿供应余量',['mine_headroom','coal_headroom','煤矿余量']],['portInventory','港口库存',['port_inventory','coal_inventory','港口库存']],['cokeCapacity','焦化产能余量',['coke_capacity','coking_capacity','焦化产能']],['steelUtilization','钢厂利用率',['steel_utilization','mill_utilization','钢厂利用率']],['scrapSupply','废钢供给',['scrap_supply','scrap_volume','废钢供给']],['coalMiningPool','煤炭开采价值池',['coal_mining_profit','coal_ebitda','煤炭利润']],['cokingPool','焦化价值池',['coking_margin','coke_margin','焦化利润']],['blastFurnacePool','普钢冶炼价值池',['blast_furnace_margin','steel_margin','普钢利润']],['specialSteelPool','特钢价值池',['special_steel_margin','special_steel_profit','特钢利润']],['downstreamPool','下游制造价值池',['downstream_margin','manufacturing_margin','下游利润']]]
    },
    'new-energy-vehicle':{
      id:'new-energy-vehicle',name:'新能源汽车',status:'CANDIDATE_ONLY',
      keywords:['lithium','battery','cell','cathode','anode','electrolyte','ev','bev','vehicle','锂价','电池','电芯','正极','负极','电解液','新能源汽车','整车'],
      nodeIds:['rates','evDemand','lithiumPrice','lithiumSupply','cathodeRoute','lfpRoute','cellCapacity','batteryInventory','batteryCost','cellPool','vehicleMargin','catl','byd','tesla'],
      companies:[{id:'catl',name:'宁德时代',aliases:['300750.sz','300750','宁德时代','catl']},{id:'byd',name:'比亚迪',aliases:['002594.sz','002594','比亚迪','byd']},{id:'tesla',name:'Tesla',aliases:['tsla','tesla','特斯拉']}],
      metrics:[['rates','实际利率',['real_rate','interest_rate','实际利率']],['evDemand','新能源汽车需求',['ev_demand','bev_sales','新能源汽车销量']],['lithiumPrice','锂价',['lithium_price','lithium_carbonate_price','碳酸锂价格','锂价']],['lithiumSupply','锂供给',['lithium_supply','lithium_output','锂供给']],['cellCapacity','电芯产能',['cell_capacity','battery_capacity','电芯产能']],['batteryInventory','电池库存',['battery_inventory','cell_inventory','电池库存']],['batteryCost','电池成本',['battery_cost','cell_cost','电池成本']],['vehicleMargin','整车毛利率',['vehicle_margin','auto_margin','整车毛利率']]]
    }
  };
  const genericMetrics=[
    ['observationDate','观察日期',['date','observation_date','trade_date','report_date','日期'],'SOURCE_METADATA'],['announcementDate','公告日期',['ann_dt','actual_ann_dt','announcement_date','公告日期'],'SOURCE_METADATA'],['reportPeriod','报告期',['report_period','fiscal_period','报告期'],'SOURCE_METADATA'],['entityCode','证券代码',['ticker','security_code','s_info_windcode','windcode','证券代码'],'SOURCE_METADATA'],['companyName','公司名称',['company','company_name','issuer_name','公司名称'],'SOURCE_METADATA'],['reportedRevenue','营业收入',['revenue','operating_revenue','营业收入']],['reportedNetProfit','净利润',['net_profit','net_income','归母净利润','净利润']],['reportedOperatingCashFlow','经营现金流',['operating_cash_flow','cash_from_operations','经营现金流']],['reportedCapex','资本开支',['company_capex','capital_expenditure','资本开支']],['reportedFcf','自由现金流',['free_cash_flow','fcf','自由现金流']],['reportedAssets','总资产',['total_assets','总资产']],['reportedDebt','债务',['total_debt','net_debt','总债务','净负债']]
  ];
  const normalize=(value)=>String(value??'').toLowerCase().replace(/[\s\-\/\\.()（）]+/g,'_').replace(/_+/g,'_');
  const has=(text,alias)=>text.includes(normalize(alias));
  function stableHash(value){const text=JSON.stringify(value);let result=2166136261;for(let i=0;i<text.length;i+=1){result^=text.charCodeAt(i);result=Math.imul(result,16777619)}return 'DIFF-'+(result>>>0).toString(16).padStart(8,'0');}
  function sourceText(input){const profile=input.profile||[],entities=input.entityHints||[];return normalize([input.fileName||'',input.companyHint||'',...profile.map((item)=>item.column),...entities].join('|'));}
  function scoreCatalog(catalog,text){
    const keywordHits=catalog.keywords.filter((keyword)=>has(text,keyword));
    const metricHits=catalog.metrics.filter(([, ,aliases])=>aliases.some((alias)=>has(text,alias)));
    const companyHits=catalog.companies.filter((company)=>company.aliases.some((alias)=>has(text,alias)));
    return{domainId:catalog.id,name:catalog.name,status:catalog.status,score:keywordHits.length+metricHits.length*2+companyHits.length*6,keywordHits,metricHits:metricHits.map((item)=>item[0]),companyHits:companyHits.map((item)=>item.id)};
  }
  function mapFields(profile,catalog){
    return(profile||[]).map((field)=>{
      const column=normalize(field.column),domainMetric=catalog?.metrics.find(([, ,aliases])=>aliases.some((alias)=>column===normalize(alias)||column.includes(normalize(alias)))),generic=genericMetrics.find(([, ,aliases])=>aliases.some((alias)=>column===normalize(alias)||column.includes(normalize(alias)))),match=domainMetric||generic;
      return{source:field.column,target:match?.[0]||'OUT_OF_SCOPE',label:match?.[1]||'未映射字段',scope:domainMetric?'DOMAIN_NODE':generic?(generic[3]||'COMPANY_FINANCIAL'):'OUT_OF_SCOPE',status:match?'MATCHED':'OUT_OF_SCOPE',valueClass:'PENDING_REVIEW',candidateValue:field.candidateValue??null,dtype:field.dtype||'unknown',nullRate:field.nullRate??null};
    });
  }
  function resolveCompanies(catalog,text,companyHint){
    const matched=catalog?catalog.companies.filter((company)=>company.aliases.some((alias)=>has(text,alias))):[];
    const hint=String(companyHint||'').trim();
    const candidate=hint&&!matched.length?{id:'candidate-'+stableHash(hint).slice(-8),name:hint,status:'EXPOSURE_ONLY',reason:'COMPANY_ADAPTER_REQUIRED'}:null;
    return{matched,candidate};
  }
  function infer(input={}){
    const activeDomain=catalogs[input.activeDomain]?input.activeDomain:'ai-infrastructure',intent=['supplement','replace','new-domain'].includes(input.intent)?input.intent:'supplement',text=sourceText(input),scores=Object.values(catalogs).map((catalog)=>scoreCatalog(catalog,text)).sort((a,b)=>b.score-a.score||a.domainId.localeCompare(b.domainId)),top=scores[0],runner=scores[1];
    const ambiguous=!top||top.score<3||(runner&&runner.score>0&&top.score-runner.score<2),detectedDomain=ambiguous?null:top.domainId,target=catalogs[detectedDomain]||null,mappings=mapFields(input.profile||[],target),companies=resolveCompanies(target,text,input.companyHint),active=catalogs[activeDomain],targetNodes=new Set(target?.nodeIds||[]),activeNodes=new Set(active.nodeIds),matchedNodeIds=[...new Set(mappings.filter((row)=>row.scope==='DOMAIN_NODE').map((row)=>row.target))],unknownFields=mappings.filter((row)=>row.status==='OUT_OF_SCOPE').map((row)=>row.source),unavailableNodes=intent==='replace'&&target?[...targetNodes].filter((id)=>!matchedNodeIds.includes(id)&&!target.companies.some((company)=>company.id===id)):[];
    let action='HOLD_FOR_REVIEW',executable=false,reason='DOMAIN_NOT_IDENTIFIED';
    if(target){
      if(target.status!=='SUPPORTED'){action='CREATE_DOMAIN_CANDIDATE';reason='DOMAIN_PACKAGE_NOT_IMPLEMENTED';}
      else if(detectedDomain!==activeDomain){action='SWITCH_DOMAIN';reason='SUPPORTED_DOMAIN_DIFFERS';executable=true;}
      else if(companies.candidate){action='ADD_COMPANY_CANDIDATE';reason='COMPANY_ADAPTER_REQUIRED';}
      else{action='UPDATE_ACTIVE_DOMAIN';reason=intent==='replace'?'REPLACE_SNAPSHOT_REVIEW':'SUPPLEMENT_SNAPSHOT';executable=matchedNodeIds.length>0||companies.matched.length>0;}
    }
    const addedNodes=target?[...targetNodes].filter((id)=>!activeNodes.has(id)):[],removedNodes=target?[...activeNodes].filter((id)=>!targetNodes.has(id)):[],sharedNodes=target?[...targetNodes].filter((id)=>activeNodes.has(id)):[];
    const plan={schemaVersion:'domain-diff-plan-1.0.0',activeDomain,detectedDomain,intent,action,reason,executable,formalReady:false,causalStatus:'ABSTAIN',scores,mappings,matchedNodeIds,unknownFields,companies:{matched:companies.matched,candidate:companies.candidate},diff:{addedNodes,removedNodes,sharedNodes,updatedNodes:matchedNodeIds,unavailableNodes},gates:{domain:detectedDomain?'MATCHED':'WAITING_REVIEW',mapping:mappings.some((row)=>row.status==='MATCHED')?'PARTIAL':'UNAVAILABLE',company:companies.candidate?'COMPANY_ADAPTER_REQUIRED':companies.matched.length?'MATCHED':'NOT_PROVIDED',activation:executable?'HUMAN_CONFIRMATION_REQUIRED':'ABSTAIN'}};
    plan.planId=stableHash(plan);
    return plan;
  }
  function compile(input={}){const plan=infer(input);return{...plan,compiledAt:new Date().toISOString(),targetDomain:plan.detectedDomain?{id:plan.detectedDomain,name:catalogs[plan.detectedDomain].name,status:catalogs[plan.detectedDomain].status,layers,nodeIds:catalogs[plan.detectedDomain].nodeIds}:null,activation:{allowed:plan.executable,mode:plan.action==='SWITCH_DOMAIN'?'RELOAD_DOMAIN':plan.action==='UPDATE_ACTIVE_DOMAIN'?'RELOAD_OVERLAY':'BLOCKED'}};}
  root.NEXUS_V216_DOMAIN_RESOLVER={schemaVersion:'domain-resolver-1.0.0',catalogs,genericMetrics,normalize,infer,compile,stableHash};
})(typeof window==='undefined'?globalThis:window);
