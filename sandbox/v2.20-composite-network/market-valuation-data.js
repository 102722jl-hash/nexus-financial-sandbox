(function(){
  const common={retrievedAt:'2026-09-01',sourceTier:'T3_DATA_PROVIDER',reviewStatus:'NEEDS_HUMAN_REVIEW',formal_ready:false};
  const ai={
    nvda:{symbol:'NVDA',currency:'USD',price:220.78,marketCapBn:5347.51238,quoteDate:'2026-09-01 RETRIEVED',fundamentalDate:'2026-01-25',evEbitda:31.43,netDebtEbitda:.01,fcfYield:.0213},
    amd:{symbol:'AMD',currency:'USD',price:470.72,marketCapBn:767.556032,quoteDate:'2026-09-01 RETRIEVED',fundamentalDate:'2025-12-27',evEbitda:47.85,netDebtEbitda:-.15,fcfYield:.0193},
    avgo:{symbol:'AVGO',currency:'USD',price:370.34,marketCapBn:1761.9221772,quoteDate:'2026-09-01 RETRIEVED',fundamentalDate:'2025-11-02',evEbitda:50.62,netDebtEbitda:1.41,fcfYield:.0158},
    tsmc:{symbol:'TSM',currency:'USD',price:415.32,marketCapBn:2154.0488736,quoteDate:'2026-09-01 RETRIEVED',fundamentalDate:'2025-12-31',evEbitda:17.32,netDebtEbitda:-.62,fcfYield:.0222},
    skhynix:{symbol:'000660.KS',currency:'KRW',price:1696000,marketCapBn:1203913.895136,quoteDate:'2026-09-01 RETRIEVED',fundamentalDate:'2025-12-31',evEbitda:7.03,netDebtEbitda:.15,fcfYield:.0552},
    micron:{symbol:'MU',currency:'USD',price:958.73,marketCapBn:1082.7800747,quoteDate:'2026-09-01 RETRIEVED',fundamentalDate:'2025-08-28',evEbitda:7.67,netDebtEbitda:.30,fcfYield:.0123},
    arista:{symbol:'ANET',currency:'USD',price:195.69,marketCapBn:246.406867322,quoteDate:'2026-09-01 RETRIEVED',fundamentalDate:'2025-12-31',evEbitda:37.68,netDebtEbitda:-.45,fcfYield:.0258},
    vertiv:{symbol:'VRT',currency:'USD',price:258.72,marketCapBn:99.60409536,quoteDate:'2026-09-01 RETRIEVED',fundamentalDate:'2025-12-31',evEbitda:29.73,netDebtEbitda:.78,fcfYield:.0305},
    eaton:{symbol:'ETN',currency:'USD',price:401.88,marketCapBn:156.050004,quoteDate:'2026-09-01 RETRIEVED',fundamentalDate:'2025-12-31',evEbitda:22.56,netDebtEbitda:1.77,fcfYield:.0287},
    msft:{symbol:'MSFT',currency:'USD',price:507.29,marketCapBn:3766.9072595,quoteDate:'2026-09-01 RETRIEVED',fundamentalDate:'2026-06-30',evEbitda:13.87,netDebtEbitda:.52,fcfYield:.0242}
  };
  const coal={
    shenhua:{symbol:'601088.SH',currency:'CNY',price:48.78,marketCapBn:1058.010605154,quoteDate:'2026-08-31',pe:20.0195},
    shaanxi:{symbol:'601225.SH',currency:'CNY',price:27.62,marketCapBn:267.7759,quoteDate:'2026-08-31',pe:15.9725},
    yankuang:{symbol:'600188.SH',currency:'CNY',price:23.62,marketCapBn:237.07044424,quoteDate:'2026-08-31',pe:28.2868},
    baosteel:{symbol:'600019.SH',currency:'CNY',price:5.82,marketCapBn:126.771732954,quoteDate:'2026-08-31',pe:12.2537},
    citicsteel:{symbol:'000708.SZ',currency:'CNY',price:13.75,marketCapBn:69.39843075,quoteDate:'2026-08-31',pe:11.7056}
  };
  Object.values(ai).forEach((item)=>Object.assign(item,common,{method:'MARKET_CALIBRATED_EV_EBITDA',quoteSourceUrl:'https://site.financialmodelingprep.com/?ref=quote-'+item.symbol,fundamentalSourceUrl:'https://site.financialmodelingprep.com/?ref=fundamental-'+item.symbol,quoteStatus:'MARKET_DATA_CANDIDATE',fundamentalStatus:'FUNDAMENTAL_DATA_CANDIDATE'}));
  Object.values(coal).forEach((item)=>Object.assign(item,common,{method:'MARKET_CALIBRATED_PE',quoteSourceUrl:null,quoteLocator:'AnySearch finance.quote result 1 / '+item.symbol+' / trade_date=20260831',quoteStatus:'MARKET_DATA_CANDIDATE',fundamentalStatus:'POSTGRESQL_DATABASE_CANDIDATE'}));
  window.NEXUS_V214_MARKET_DATA={schemaVersion:'market-valuation-candidate-1.0.0',asOf:'2026-09-01',ai,coal,audit:{status:'NEEDS_HUMAN_REVIEW',formal_ready:false,causalStatus:'NOT_IDENTIFIED',causalConclusion:'ABSTAIN',limitations:['国际行情缺少交易所时间戳原文定位','第三方行情与公司概览尚未交叉复核','情景倍数与净债务响应仍为模型假设']}};
}());
