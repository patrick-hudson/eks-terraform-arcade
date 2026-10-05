const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const D=require('../drills-core.js');
const source=fs.readFileSync(require.resolve('../drills.js'),'utf8');
const brief={id:'case-a',kind:'investigation',title:'Case A',summary:'Investigate',brief:'Same symptom',minutes:5,provenance:'Simulation',relatedLabs:[],observations:[{id:'events',label:'Events',command:'kubectl get events'}],question:{prompt:'Which cause?',options:[{id:'right',text:'Correct explanation'}]}};
const feedback={correct:true,explanation:'EXPLANATION',decisiveEvidence:['events'],repair:'Terraform repair',verification:'Proof',cleanup:'Cleanup',followUp:'Constraint'};
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
async function mounted(){
  const requests=[],messages=[];let state=D.normalize(null),current=true,sequence=0;
  const target={isConnected:true,html:'',buttons:[],set innerHTML(html){this.html=html;this.buttons=[...html.matchAll(/<button[^>]*data-(evidence|option|new|finish)(?:="([^"]+)")?[^>]*>/g)].map(m=>({dataset:{[m[1]]:m[2]||''},kind:m[1],focus(){},addEventListener(_event,fn){this.onclick=fn;}}));},get innerHTML(){return this.html;},querySelectorAll(selector){const kind=selector.match(/data-(\w+)/)?.[1];return this.buttons.filter(b=>b.kind===kind);},querySelector(selector){const kind=selector.match(/data-(\w+)/)?.[1];return this.buttons.find(b=>b.kind===kind)||null;}};
  const scope={window:{ArcadeDrillsCore:D,ArcadeCore:{labRoute:id=>'#/lab/'+id}},document:{activeElement:null},URLSearchParams,crypto:{randomUUID:()=>`attempt-${++sequence}`},fetch:async url=>{if(url.startsWith('/api/drill?'))return {ok:true,json:async()=>brief};const pending=deferred();requests.push({url,...pending});return pending.promise;}};
  vm.runInNewContext(source,scope);
  const cleanup=await scope.window.ArcadeDrills.mount(target,'case-a',{esc:value=>String(value).replaceAll('<','&lt;'),icon:()=>'',getState:()=>state,setState:value=>{state=value;},isCurrent:()=>current,notify:message=>messages.push(message)});
  return {target,requests,messages,cleanup,getState:()=>state,externalAttempt:()=>{state=D.begin(state,'case-a',`external-${++sequence}`);},navigate:()=>{current=false;},click:kind=>target.querySelector(`[data-${kind}]`).onclick()};
}
const response=data=>({ok:true,json:async()=>data});

for(const kind of ['evidence','option'])test(`new attempt drops stale ${kind} response and permits a new request`,async()=>{
  const m=await mounted();const pending=m.click(kind);m.click('new');
  m.requests[0].resolve(response(kind==='evidence'?{output:'OLD_SECRET_OUTPUT'}:feedback));await pending;
  assert.ok(!m.target.html.includes(kind==='evidence'?'OLD_SECRET_OUTPUT':'EXPLANATION'));
  assert.equal(m.getState().current['case-a'].selectedAnswer,null);
  assert.equal(m.getState().current['case-a'].observations.length,0);
  const next=m.click(kind);assert.equal(m.requests.length,2);m.requests[1].resolve(response(kind==='evidence'?{output:'NEW_OUTPUT'}:feedback));await next;
  assert.ok(m.target.html.includes(kind==='evidence'?'NEW_OUTPUT':'EXPLANATION'));
});

test('navigation and unmount discard both late success and error without saving or notifying',async()=>{
  const m=await mounted();const pending=m.click('evidence');m.navigate();m.cleanup();m.requests[0].reject(new Error('late'));await pending;
  assert.equal(m.messages.length,0);assert.equal(m.getState().current['case-a'].observations.length,0);
});

test('rendered observations escape markup and explicit finish creates one summary',async()=>{
  const m=await mounted();let pending=m.click('evidence');m.requests[0].resolve(response({output:'<img src=x>'}));await pending;
  assert.ok(m.target.html.includes('&lt;img src=x>'));assert.ok(!m.target.html.includes('<img src=x>'));
  pending=m.click('option');m.requests[1].resolve(response(feedback));await pending;
  assert.equal(m.getState().history.length,0);m.click('finish');assert.equal(m.getState().history.length,1);assert.equal(m.target.querySelector('[data-finish]'),null);
});

for(const kind of ['evidence','option'])test(`cross-tab new attempt discards stale ${kind} response`,async()=>{
  const m=await mounted();const pending=m.click(kind);m.externalAttempt();
  m.requests[0].resolve(response(kind==='evidence'?{output:'STALE_CROSS_TAB'}:feedback));await pending;
  assert.equal(m.getState().current['case-a'].observations.length,0);
  assert.equal(m.getState().current['case-a'].selectedAnswer,null);
  assert.ok(!m.target.html.includes(kind==='evidence'?'STALE_CROSS_TAB':'EXPLANATION'));
});
