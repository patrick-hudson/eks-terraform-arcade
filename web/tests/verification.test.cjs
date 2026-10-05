const {test}=require('node:test');
const assert=require('node:assert/strict');
const V=require('../verification-core.js');
const lab='11-incident-gauntlet/scenario-01';
const receipt=(status='pass',time='2026-10-04T12:00:00Z')=>({schemaVersion:1,kind:'aws-arcade-verification',toolVersion:'1',labId:lab,phase:'verify',generatedAt:time,scope:'Read-only snapshot; HTTP checks remain manual.',environment:{account:'123456789012',region:'us-east-1',cluster:'arcade-smoke',context:'arcade-lab'},checks:[{id:'replicas',label:'Ready replica',status,expected:'1',observed:status==='pass'?'1':'0'}],summary:{passed:status==='pass'?1:0,failed:status==='fail'?1:0,errors:status==='error'?1:0}});
test('receipt import validates identity, version, phase, timestamps and bounded checks',()=>{
 assert.equal(V.parse(JSON.stringify(receipt()),lab).checks[0].status,'pass');
 for(const change of [{labId:'08-kubernetes-release'},{phase:'apply'},{generatedAt:'yesterday'},{schemaVersion:9},{checks:[]},{summary:{passed:999,failed:0,errors:0}},{environment:{...receipt().environment,account:'root'}}]) assert.throws(()=>V.parse(JSON.stringify({...receipt(),...change}),lab));
 assert.throws(()=>V.parse('{broken',lab));
 assert.throws(()=>V.parse(JSON.stringify({...receipt(),checks:[...receipt().checks,...receipt().checks]}),lab));
});
test('history compares same environment and phase; failed-to-passed is an observation',()=>{
 let history=V.add([],receipt('fail'));
 history=V.add(history,receipt('pass','2026-10-04T12:05:00Z'));
 assert.equal(history.length,2);
 assert.deepEqual(V.compare(history[0],history[1]),[{id:'replicas',label:'Ready replica',from:'fail',to:'pass'}]);
 assert.deepEqual(V.compare(history[0],{...history[1],environment:{...history[1].environment,cluster:'other'}}),[]);
 assert.deepEqual(V.compare(history[0],{...history[1],phase:'cleanup'}),[]);
});
test('deduplicated receipts keep three per phase, newest first',()=>{
 let history=[];
 for(let i=0;i<5;i++)history=V.add(history,receipt('pass',`2026-10-04T12:0${i}:00Z`));
 assert.equal(history.length,3);assert.equal(history[0].generatedAt,'2026-10-04T12:04:00Z');
 assert.equal(V.add(history,history[0]).length,3);
 history=V.add(history,{...receipt(),phase:'cleanup'});assert.equal(history.length,4);
});
test('receipts survive progress roundtrip without marking a mission complete',()=>{
 const C=require('../core.js');
 const saved=C.readProgress(JSON.stringify({schemaVersion:2,labs:{[lab]:{status:'active',notes:'my evidence',receipts:[receipt()]}}}));
 assert.equal(saved.labs[lab].receipts.length,1);assert.equal(saved.labs[lab].status,'active');assert.equal(saved.labs[lab].checks.verify,false);
 assert.equal(C.resetPractice(saved.labs[lab]).receipts.length,1);
 assert.equal(saved.labs[lab].notes,'my evidence');
});
test('an older import selects that failure and reports retention rejection honestly',()=>{
 const newest=receipt('pass','2026-10-04T12:05:00Z');
 const imported=V.importHistory([newest],receipt('fail'));
 assert.equal(imported.selected,1);
 assert.equal(imported.history[imported.selected].checks[0].status,'fail');
 const full=[newest,receipt('pass','2026-10-04T12:04:00Z'),receipt('pass','2026-10-04T12:03:00Z')];
 assert.throws(()=>V.importHistory(full,receipt('fail')),/not imported/);
 assert.equal(full.length,3);assert.equal(full[0],newest);
 const cleanup=V.importHistory(full,{...receipt('pass'),phase:'cleanup'});
 assert.equal(cleanup.selected,0);assert.equal(cleanup.history.length,4);
});
