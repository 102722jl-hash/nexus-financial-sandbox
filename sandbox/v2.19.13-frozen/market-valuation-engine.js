(function(){
  const runtime=window.NEXUS_ACTIVE_RUNTIME;
  const market=window.NEXUS_V214_MARKET_DATA;
  const round=(value,digits=3)=>{const factor=10**digits;return Math.round(Number(value)*factor)/factor;};
  const valid=(...values)=>values.every((value)=>Number.isFinite(Number(value)));
  function profile(companyId){
    const quote=(runtime.id==='coal-steel'?market.coal:market.ai)[companyId];
    const financial=runtime.id==='coal-steel'?runtime.database.companies?.[companyId]:null;
    if(!quote)return{status:'DATA_MISSING',companyId};
    return{status:'VALUATION_INPUT_CANDIDATE',companyId,...quote,financial,impliedSharesBn:round(quote.marketCapBn/quote.price,6),dataStatus:'NEEDS_HUMAN_REVIEW',formal_ready:false};
  }
  function evaluateAi(item,p){
    if(!valid(p.marketCapBn,p.evEbitda,p.netDebtEbitda,p.fcfYield,item.revenue,item.margin,item.multipleChange,item.fcf)||p.evEbitda<=p.netDebtEbitda)return{status:'ABSTAIN',reason:'AI_VALUATION_INPUT_INVALID'};
    const baselineEbitda=p.marketCapBn/(p.evEbitda-p.netDebtEbitda),baselineNetDebt=baselineEbitda*p.netDebtEbitda,baselineFcf=p.marketCapBn*p.fcfYield;
    const ebitdaChangePct=round(item.revenue+item.margin),multipleChangePct=round(item.multipleChange),fcfChangePct=round(item.fcf);
    const scenarioEbitda=baselineEbitda*(1+ebitdaChangePct/100),scenarioMultiple=Math.max(.1,p.evEbitda*(1+multipleChangePct/100));
    const incrementalFcf=baselineFcf*fcfChangePct/100,scenarioNetDebt=baselineNetDebt-incrementalFcf;
    const operatingValue=scenarioEbitda*p.evEbitda-baselineNetDebt,multipleValue=scenarioEbitda*scenarioMultiple-baselineNetDebt,scenarioEquityValue=multipleValue+incrementalFcf;
    const operations=round(operatingValue-p.marketCapBn),multiple=round(multipleValue-operatingValue),totalChange=round(scenarioEquityValue-p.marketCapBn);
    const attribution={operations,multiple,cashFlow:round(totalChange-operations-multiple)};
    return{baselineEbitda:round(baselineEbitda),baselineNetDebt:round(baselineNetDebt),baselineFcf:round(baselineFcf),scenarioEbitda:round(scenarioEbitda),scenarioMultiple:round(scenarioMultiple),scenarioNetDebt:round(scenarioNetDebt),scenarioEquityValue,ebitdaChangePct,multipleChangePct,fcfChangePct,attribution,formula:'情景 EBITDA × 情景 EV/EBITDA − 情景净债务'};
  }
  function evaluateCoal(item,p){
    const baselineNetIncome=Number(p.financial?.netProfitBn),baselinePe=Number(p.pe||p.marketCapBn/baselineNetIncome);
    if(!valid(p.marketCapBn,baselineNetIncome,baselinePe,item.revenue,item.margin,item.multipleChange)||baselineNetIncome<=0||baselinePe<=0)return{status:'ABSTAIN',reason:'COAL_VALUATION_INPUT_INVALID'};
    const earningsChangePct=round(item.revenue+item.margin),multipleChangePct=round(item.multipleChange),scenarioNetIncome=baselineNetIncome*(1+earningsChangePct/100),scenarioPe=Math.max(.1,baselinePe*(1+multipleChangePct/100));
    const operatingValue=scenarioNetIncome*baselinePe,scenarioEquityValue=scenarioNetIncome*scenarioPe;
    const operations=round(operatingValue-p.marketCapBn),multiple=round(scenarioEquityValue-p.marketCapBn-operations),attribution={operations,multiple,cashFlow:0};
    return{baselineNetIncome:round(baselineNetIncome),baselinePe:round(baselinePe),scenarioNetIncome:round(scenarioNetIncome),scenarioPe:round(scenarioPe),earningsChangePct,multipleChangePct,attribution,scenarioEquityValue,formula:'情景净利润 × 情景 P/E'};
  }
  function evaluate(companyResult){
    const p=profile(companyResult?.id);
    if(p.status!=='VALUATION_INPUT_CANDIDATE')return{status:'DATA_MISSING',companyId:companyResult?.id,currentMarketCap:null,scenarioEquityValue:null,valueChangeAmount:null,valueChangePct:null};
    const detail=runtime.id==='coal-steel'?evaluateCoal(companyResult,p):evaluateAi(companyResult,p);
    if(detail.status==='ABSTAIN')return{...detail,companyId:companyResult.id,currentMarketCap:p.marketCapBn,formal_ready:false};
    const baselineEquityValue=p.marketCapBn,scenarioEquityValue=Number(detail.scenarioEquityValue),valueChangeAmount=scenarioEquityValue-baselineEquityValue,valueChangePct=valueChangeAmount/baselineEquityValue*100;
    return{...detail,status:'CANDIDATE_VALUATION',companyId:companyResult.id,method:p.method,currency:p.currency,scale:'bn',quoteDate:p.quoteDate,fundamentalDate:p.fundamentalDate||p.financial?.reportPeriod||null,price:p.price,impliedSharesBn:p.impliedSharesBn,currentMarketCap:round(p.marketCapBn),baselineEquityValue:round(baselineEquityValue),scenarioEquityValue:round(scenarioEquityValue),valueChangeAmount:round(valueChangeAmount),valueChangePct:round(valueChangePct),marketUpsidePct:round(valueChangePct),reviewStatus:'NEEDS_HUMAN_REVIEW',formal_ready:false,source:{quoteStatus:p.quoteStatus,fundamentalStatus:p.fundamentalStatus,quoteSourceUrl:p.quoteSourceUrl||null,quoteLocator:p.quoteLocator||null}};
  }
  function evaluateAll(companies){return companies.map(evaluate).sort((a,b)=>(b.valueChangePct??-Infinity)-(a.valueChangePct??-Infinity));}
  function industry(companies){const results=evaluateAll(companies).filter((item)=>item.status==='CANDIDATE_VALUATION');const changes=results.map((item)=>item.valueChangePct);return{status:results.length===companies.length?'CANDIDATE_VALUATION':'PARTIAL_CALCULATED',index:round(100+changes.reduce((sum,value)=>sum+value,0)/Math.max(1,changes.length)),low:round(100+Math.min(...changes)),high:round(100+Math.max(...changes)),results};}
  window.NEXUS_V214_MARKET_VALUATION={schemaVersion:'market-calibrated-scenario-valuation-1.0.0',profile,evaluate,evaluateAll,industry};
}());
