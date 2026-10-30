(function(){
  const companies={
    shenhua:{code:'601088.SH',name:'中国神华',industry:'煤炭',industryScore:87.4723,industryRank:1,revenueBn:294.916,netProfitBn:52.849,ebitdaBn:96.795,cfoBn:75.059,capexBn:48.398,fcfBn:28.872,cashBn:96.772,debtBn:null,debtComponentsBn:{shortTermBorrowing:.409,currentPortion:9.364,longTermBorrowing:28.268,bondsPayable:null,leaseLiability:.971},assetsBn:627.761,liabilitiesBn:146.310},
    shaanxi:{code:'601225.SH',name:'陕西煤业',industry:'煤炭',industryScore:83.6206,industryRank:2,revenueBn:158.179,netProfitBn:16.765,ebitdaBn:41.858,cfoBn:35.269,capexBn:17.060,fcfBn:12.803,cashBn:31.798,debtBn:null,debtComponentsBn:{shortTermBorrowing:1.639,currentPortion:3.768,longTermBorrowing:19.822,bondsPayable:null,leaseLiability:.363},assetsBn:236.269,liabilitiesBn:98.862},
    yankuang:{code:'600188.SH',name:'兖矿能源',industry:'煤炭',industryScore:72.3492,industryRank:5,revenueBn:144.933,netProfitBn:8.381,ebitdaBn:36.872,cfoBn:19.485,capexBn:18.521,fcfBn:3.317,cashBn:37.428,debtBn:null,debtComponentsBn:{shortTermBorrowing:20.958,currentPortion:32.074,longTermBorrowing:57.100,bondsPayable:22.964,leaseLiability:.426},assetsBn:452.944,liabilitiesBn:281.847},
    baosteel:{code:'600019.SH',name:'宝钢股份',industry:'钢铁',industryScore:70.8781,industryRank:2,revenueBn:317.508,netProfitBn:10.346,ebitdaBn:32.822,cfoBn:33.597,capexBn:18.507,fcfBn:23.897,cashBn:19.158,debtBn:null,debtComponentsBn:{shortTermBorrowing:5.252,currentPortion:21.903,longTermBorrowing:4.841,bondsPayable:5.000,leaseLiability:5.342},assetsBn:363.020,liabilitiesBn:137.830},
    citicsteel:{code:'000708.SZ',name:'中信特钢',industry:'钢铁',industryScore:71.7580,industryRank:1,revenueBn:107.373,netProfitBn:5.929,ebitdaBn:12.658,cfoBn:14.636,capexBn:.770,fcfBn:10.963,cashBn:11.273,debtBn:null,debtComponentsBn:{shortTermBorrowing:6.818,currentPortion:5.595,longTermBorrowing:15.774,bondsPayable:4.998,leaseLiability:.049},assetsBn:110.323,liabilitiesBn:64.849}
  };
  Object.values(companies).forEach((item)=>{
    item.netMarginPct=Number((item.netProfitBn/item.revenueBn*100).toFixed(2));
    item.fcfMarginPct=Number((item.fcfBn/item.revenueBn*100).toFixed(2));
    item.debtRatioPct=Number((item.liabilitiesBn/item.assetsBn*100).toFixed(2));
    const visibleDate=item.code==='600019.SH'?'2026-04-30':item.code==='601225.SH'?'2026-04-25':item.code==='601088.SH'?'2026-03-31':item.code==='600188.SH'?'2026-03-28':'2026-03-17';
    const balanceOpdate=item.code==='600019.SH'?'2026-04-29':item.code==='601225.SH'?'2026-04-24':item.code==='601088.SH'?'2026-03-30':item.code==='600188.SH'?'2026-03-27':'2026-03-16';
    const incomeOpdate=item.code==='600188.SH'?'2026-04-18':item.code==='600019.SH'?'2026-04-30':balanceOpdate;
    const cashflowOpdate=item.code==='600188.SH'?'2026-03-28':item.code==='600019.SH'?'2026-04-30':balanceOpdate;
    Object.assign(item,{reportPeriod:'2025-12-31',availableAt:visibleDate,statementType:'408001000',financialSource:'PostgreSQL public consolidated statements',financialStatus:'DATABASE_CANDIDATE',valuationLineage:{cutoff:'2026-05-08',balance:{visibleDate,opdate:balanceOpdate},income:{visibleDate,opdate:incomeOpdate},cashflow:{visibleDate,opdate:cashflowOpdate}}});
  });
  window.NEXUS_COAL_DB_SNAPSHOT={
    snapshotVersion:'coal-valuation-inputs-2026-09-01',runId:'coal-valuation-20260901-01',standalone:true,parentUi:'NEXUS V2.12',
    scenario:{id:'coking-coal-minus-20',label:'焦煤价格下降 20%',marketCode:'JM.DCE',baselineClose:1288,tradeDate:'2026-07-23',unit:'元/吨',source:'MySQL workspace.ccommodityfutureseodprices_202607231545',status:'DATABASE_CANDIDATE'},
    coverage:{industryCompanies:5100,industries:28,coalCompanies:37,steelCompanies:45,financialPeriodMin:'2023-12-31',financialPeriodMax:'2026-03-31',financialCutoff:'2026-05-08'},
    companies,
    quarantine:[
      {id:'Q-METHOD1-COPY',status:'QUARANTINED',reason:'28 张 2023方法1 表均重复为同一批 434 家医药生物公司'},
      {id:'Q-SCORE-DIV0',status:'QUARANTINED',reason:'电子、机械设备、基础化工、电力设备、家电共 1,930 家公司评分为 #DIV/0!'},
      {id:'Q-PROVENANCE-EMPTY',status:'NEEDS_HUMAN_REVIEW',reason:'原文件、字段映射、原文及单元格溯源表为空'}
    ],
    audit:{status:'NEEDS_HUMAN_REVIEW',formal_ready:false,causalStatus:'NOT_IDENTIFIED',causalConclusion:'ABSTAIN',sourceFactsClosed:0,financialRows:'CALCULATED_LINEAGE_CANDIDATE',parameterClass:'ANALYST_ASSUMPTION'}
  };
}());
