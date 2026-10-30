const fs=require('fs'),vm=require('vm'),assert=require('assert');
const context={};context.window=context;vm.createContext(context);vm.runInContext(fs.readFileSync('domains.js','utf8'),context);
const {layers,packages}=context.DOMAIN_PACKAGES;
assert.equal(layers.length,6,'必须保留六层结构');
assert.deepStrictEqual(Array.from(layers,(x)=>x.id),['macro','demand','route','constraint','chain','company']);
assert.equal(packages.length,2,'原型必须包含两个领域包');
for(const domain of packages){
  assert(domain.id&&domain.version&&domain.cutoff,'领域清单不完整');
  for(const layer of layers)assert(domain.nodes.some((node)=>node.layer===layer.id),domain.id+' 缺少层 '+layer.id);
  for(const node of domain.nodes)assert(['MATCHED','PARTIAL','UNAVAILABLE'].includes(node.status),'非法节点状态 '+node.status);
  for(const edge of domain.edges){assert(domain.nodes.some((node)=>node.id===edge.from));assert(domain.nodes.some((node)=>node.id===edge.to));}
  for(const company of domain.companies)assert(domain.nodes.some((node)=>node.id===company.id&&node.layer==='company'),'公司节点不一致 '+company.id);
}
const coal=packages.find((x)=>x.id==='coal-steel'),bank=packages.find((x)=>x.id==='banking');
assert(coal.companies.every((x)=>x.method==='EV / EBITDA'));
assert(coal.companies.every((x)=>x.market.status==='DATABASE_CANDIDATE'));
assert(bank.companies.every((x)=>x.baseline===null));
assert(bank.companies.every((x)=>x.output==='EXPOSURE_ONLY'));
const equity=(x)=>x.baseline.ebitda*x.baseline.multiple-x.baseline.netDebt+x.baseline.nonOperating-x.baseline.minority;
for(const company of coal.companies)assert(Number.isFinite(equity(company))&&equity(company)>0,'股权价值桥接失败 '+company.id);
const html=fs.readFileSync('index.html','utf8');
for(const id of ['domainSelect','layerGrid','marketCap','baselineValue','scenarioValue','scenarioChange','marketSpace','mappingTable','manifestList'])assert(html.includes('id="'+id+'"'),'DOM 缺少 '+id);
for(const forbidden of ['行业估值指数','估值贡献相对最高'])assert(!html.includes(forbidden),'仍含旧估值措辞 '+forbidden);
console.log('multi-industry template tests: PASS');
