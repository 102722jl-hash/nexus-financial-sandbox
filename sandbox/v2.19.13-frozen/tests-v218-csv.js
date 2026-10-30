(async()=>{
  const fs=require('node:fs'),assert=require('node:assert/strict');const base='http://127.0.0.1:4179',headers={'Content-Type':'application/json','X-Client-Id':'CLIENT-v218-csv-e2e'};
  const call=async(method,path,body)=>{const r=await fetch(base+path,{method,headers,body:body?JSON.stringify(body):undefined});const data=await r.json();if(!r.ok)throw new Error(JSON.stringify(data));return data};
  const content=fs.readFileSync('fixtures/v218-steel-sample.csv').toString('base64');
  const source=await call('POST','/api/sources/profile',{sourceType:'file',name:'v218-steel-sample.csv',content,cutoff:'2026-05-08'});assert.ok(source.sourceId);assert.equal(source.mappings.length,7);
  for(const m of source.mappings)await call('POST','/api/mappings/'+m.mappingId+'/confirm',{action:'confirm',metricCode:m.metricCode});
  const sync=await call('POST','/api/sources/'+source.sourceId+'/sync',{dataCutoff:'2026-05-08',rowLimit:20});assert.equal(sync.rowsRead,2);assert.equal(sync.acceptedRows,2);assert.equal(sync.metricValuesCreated,6);
  const values=await call('GET','/api/sources/'+source.sourceId+'/metric-values');assert.equal(values.total,6);console.log('V2.18 CSV actual-row test: 8/8 passed');
})().catch((error)=>{console.error(error);process.exitCode=1});
