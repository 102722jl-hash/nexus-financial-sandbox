(function(){
  window.NEXUS_V28_DB_SNAPSHOT={
    snapshotVersion:'db-coverage-2026-09-01',
    capturedAt:'2026-09-01T09:00:00+08:00',
    requestedCutoff:'20260831',
    connection:{database:'pg',user:'dwzq',sslmode:'prefer',transactionReadOnly:'on'},
    queryPolicy:{preferredStatementType:'408001000',visibleDate:'COALESCE(actual_ann_dt, ann_dt) <= cutoff',versionOrder:'visible_date DESC, opdate DESC',opdateCutoffRequired:true},
    tables:[
      {name:'asharebalancesheet',rows:869671,securities:8642,reportPeriod:['19891231','20260630'],visibleDate:['19900321','20260812'],preferredRows:373293},
      {name:'asharecashflow',rows:2269088,securities:8633,reportPeriod:['19961231','20260630'],visibleDate:['19970809','20260812'],preferredRows:371265},
      {name:'ashareincome',rows:2360311,securities:8338,reportPeriod:['19881231','20260630'],visibleDate:['19900321','20260812'],preferredRows:378894}
    ],
    targetCompanies:[
      {id:'nvda',name:'NVIDIA',expectedCodes:['NVDA.O','NVDA.OQ'],matches:[],status:'DATA_MISSING'},
      {id:'tsmc',name:'TSMC',expectedCodes:['TSM.N','2330.TW'],matches:[],status:'DATA_MISSING'},
      {id:'skhynix',name:'SK hynix',expectedCodes:['000660.KS'],matches:[],excludedFalseMatches:['000660.SZ'],status:'DATA_MISSING'},
      {id:'vertiv',name:'Vertiv',expectedCodes:['VRT.N'],matches:[],status:'DATA_MISSING'},
      {id:'msft',name:'Microsoft',expectedCodes:['MSFT.O','MSFT.OQ'],matches:[],status:'DATA_MISSING'}
    ],
    accessibleFinancialTables:['public.asharebalancesheet','public.asharecashflow','public.ashareincome'],
    overseasFinancialTables:[],
    targetCoverage:{matched:0,required:5,status:'DATA_MISSING'},
    sourceRole:'DATABASE_CANDIDATE',
    evidenceStatus:'NEEDS_HUMAN_REVIEW',
    formal_ready:false
  };
}());
