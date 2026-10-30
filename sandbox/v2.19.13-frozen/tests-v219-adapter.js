const assert=require('node:assert/strict');
const fs=require('node:fs');
const ui=fs.readFileSync('v217-db-ui.js','utf8');
const client=fs.readFileSync('service-client.js','utf8');
const mock=fs.readFileSync('mock-adapter.js','utf8');
const html=fs.readFileSync('index.html','utf8');
let passed=0;
const check=(condition,message)=>{assert.ok(condition,message);passed+=1};

check(ui.includes("已选 '+count+' 张表"),'必须显示已选表数量');
check(ui.includes("正在画像 '+(index+1)+' / '+tables.length"),'必须逐表显示画像进度');
check(ui.includes("连接正常 · 画像失败"),'画像失败必须与连接失败分离');
check(ui.includes("数据库连接失败"),'连接失败必须保留独立状态');
check(ui.includes("'表 '+currentTable+'：'+error.message"),'按钮旁必须显示具体失败表及原因');
check(html.includes('id="v217DbFailure"')&&html.includes('role="status"'),'失败原因必须位于数据库操作区并可被辅助技术读取');
check(html.includes('id="v217SelectedCount"')&&html.includes('id="v217ProfileProgress"'),'选择数与画像进度必须有独立状态位');
check(client.includes('mock.sources.analyze(sourceAnalyze[1],body)'),'Mock 与 HTTP 必须传递同一画像请求体');
check(mock.includes('2026年一季报.财务数据'),'Mock 必须覆盖中文和日期表名');
check(mock.includes('sourceLocator:{database,schema,table,column}'),'Mock 映射必须使用结构化字段定位');
check(mock.includes("identifierMode:'DRIVER_ESCAPED'")&&mock.includes("sourceFieldMode:'STRUCTURED_LOCATOR'"),'表适配器必须声明安全标识符与结构化定位模式');

console.log('V2.19 custom table adapter UI tests: '+passed+'/11 passed');
