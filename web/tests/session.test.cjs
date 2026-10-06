const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const scope={window:{ArcadeCore:{labRoute:id=>'#/lab/'+id}}};
vm.runInNewContext(fs.readFileSync(require.resolve('../session.js'),'utf8'),scope);
const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
function fixture(){return {runnerEnabled:true,session:{id:'00',alias:'00',title:'Local',supported:true,prepared:true,roots:['.'],root:'.',status:'planned',nextAction:'review and approve',capabilities:['plan','plan_destroy','apply','submit'],prerequisites:[],cleanupOrder:[],costs:{oneHourUsd:0,twoHoursUsd:0,assumptions:[]},inventory:{resources:[],absence:'unknown'},plan:{operation:'apply',digest:'abcd',approval:'APPLY LOCAL',reviewText:'Safe metadata',stale:false,consumed:false},modes:['guided'],configuration:{}}};}
test('read-only mode offers runner startup instead of active mutation buttons',()=>{const data=fixture();data.runnerEnabled=false;const html=scope.window.ArcadeSession.render(data,esc);assert.match(html,/arcade serve --runner/);assert.ok(!html.includes('data-operation="apply"'));});
test('stale plan cannot display an approval form',()=>{const data=fixture();data.session.plan.stale=true;const html=scope.window.ArcadeSession.render(data,esc);assert.match(html,/changed/i);assert.ok(!html.includes('data-approval-form'));});
test('current saved plan shows explicit bound approval; evidence stays separate',()=>{const data=fixture();data.session.repair={status:'unknown',stale:true,checks:[],scope:'Observed only'};const html=scope.window.ArcadeSession.render(data,esc);assert.match(html,/data-approval-form/);assert.match(html,/APPLY LOCAL/);assert.match(html,/Needs a new check/);assert.match(html,/Incomplete/);});
test('resource metadata and authored command text are escaped',()=>{const data=fixture();data.session.inventory.resources=[{address:'<script>',id:'<secret>',arn:'arn:example'}];data.session.runbookSteps=[{title:'Step',command:'echo <script>'}];const html=scope.window.ArcadeSession.render(data,esc);assert.ok(!html.includes('<script>'));assert.match(html,/&lt;script>/);});

test('the stalled-update incident offers its required baseline proof before preparing the fault',()=>{
  const data=fixture();Object.assign(data.session,{alias:'11-10',phase:'baseline',capabilities:['plan','submit','verify','begin_incident']});
  const html=scope.window.ArcadeSession.render(data,esc);
  assert.match(html,/data-operation="verify"[^>]*>Verify healthy baseline</);
  assert.match(html,/verify its HTTP response/);
  assert.match(html,/data-operation="begin_incident"[^>]*>Prepare broken update</);
  data.session.phase='incident';
  const incident=scope.window.ArcadeSession.render(data,esc);
  assert.match(incident,/data-operation="begin_incident" disabled/);
  assert.match(incident,/data-operation="verify"[^>]*>Inspect live evidence</);
});

async function mountedControls(data){
  const posts=[],notices=[],refreshButton={},approvalForm={},verifyButton={dataset:{operation:'verify'}};
  const target={isConnected:true,innerHTML:'',querySelector(selector){
    return selector==='[data-session-refresh]'?refreshButton:selector==='[data-approval-form]'?approvalForm:null;
  },querySelectorAll(selector){return selector==='[data-operation]'||selector==='button'?[verifyButton]:[];}};
  const local={window:{ArcadeCore:{labRoute:id=>'#/lab/'+id}},URLSearchParams,clearTimeout,setTimeout,
    FormData:class {get(){return approvalForm.value;}},
    fetch:async(url,options)=>{if(options)posts.push({url,...options});return {ok:true,json:async()=>options?{id:'job'}:data};}};
  vm.runInNewContext(fs.readFileSync(require.resolve('../session.js'),'utf8'),local);
  const dispose=await local.window.ArcadeSession.mount(target,{id:data.session.id},{esc,notify:message=>notices.push(message)});
  return {posts,notices,approvalForm,verifyButton,dispose};
}

test('the baseline proof action submits only the fixed verify operation for the selected root',async()=>{
  const data=fixture();data.session.id='11-incident-gauntlet/scenario-10';data.session.alias='11-10';data.session.phase='baseline';data.token='local-capability';
  const ui=await mountedControls(data);
  await ui.verifyButton.onclick();
  assert.equal(ui.posts.length,1);
  assert.deepEqual(JSON.parse(ui.posts[0].body),{lab:data.session.id,root:'.',operation:'verify',parameters:{}});
  assert.equal(ui.posts[0].headers['X-Arcade-Token'],'local-capability');ui.dispose();
});

test('approval must match exactly and submits the reviewed root and saved-plan digest',async()=>{
  const data=fixture();data.session.root='access';data.session.plan.approval='DESTROY 123456789012';data.session.plan.operation='destroy';
  const ui=await mountedControls(data);
  ui.approvalForm.value='DESTROY 123456789012 ';ui.approvalForm.onsubmit({preventDefault(){}});
  assert.equal(ui.posts.length,0);assert.match(ui.notices[0],/exact approval/);
  ui.approvalForm.value='DESTROY 123456789012';ui.approvalForm.onsubmit({preventDefault(){}});
  await new Promise(setImmediate);
  assert.deepEqual(JSON.parse(ui.posts[0].body),{lab:data.session.id,root:'access',operation:'apply',parameters:{approval:'DESTROY 123456789012',plan_digest:'abcd'}});ui.dispose();
});

test('fast root switching discards an older response instead of showing the wrong workspace',async()=>{
  const requests=[];const rootControl={value:'.'},refreshButton={};
  const target={isConnected:true,innerHTML:'',querySelector(selector){return selector==='[data-session-refresh]'?refreshButton:selector==='[data-session-root]'?rootControl:null;},querySelectorAll(){return [];}};
  const local={window:{ArcadeCore:{labRoute:id=>'#/lab/'+id}},URLSearchParams,clearTimeout,setTimeout,
    fetch:url=>new Promise(resolve=>requests.push({url,resolve}))};
  vm.runInNewContext(fs.readFileSync(require.resolve('../session.js'),'utf8'),local);
  const state=root=>{const d=fixture();d.runnerEnabled=false;d.session.root=root;d.session.path='PATH_'+root;d.session.roots=['.','workload','access'];return d;};
  const response=data=>({ok:true,json:async()=>data});
  const pending=local.window.ArcadeSession.mount(target,{id:'13'},{esc,notify:()=>{}});
  requests[0].resolve(response(state('.')));await pending;
  rootControl.value='workload';rootControl.onchange();rootControl.value='access';rootControl.onchange();
  requests[2].resolve(response(state('access')));await new Promise(setImmediate);
  requests[1].resolve(response(state('workload')));await new Promise(setImmediate);
  assert.ok(target.innerHTML.includes('PATH_access'));assert.ok(!target.innerHTML.includes('PATH_workload'));
});

test('operations cannot target the old root while the selected root is loading',async()=>{
  const requests=[],posts=[],rootControl={value:'.'},refreshButton={},planButton={dataset:{operation:'plan'}};
  const target={isConnected:true,innerHTML:'',querySelector(selector){return selector==='[data-session-refresh]'?refreshButton:selector==='[data-session-root]'?rootControl:null;},querySelectorAll(selector){return selector==='[data-operation]'||selector==='button'?[planButton]:[];}};
  const local={window:{ArcadeCore:{labRoute:id=>'#/lab/'+id}},URLSearchParams,clearTimeout,setTimeout,
    fetch:(url,options)=>{if(options){posts.push(JSON.parse(options.body));return Promise.resolve({ok:true,json:async()=>({id:'job'})});}return new Promise(resolve=>requests.push({url,resolve}));}};
  vm.runInNewContext(fs.readFileSync(require.resolve('../session.js'),'utf8'),local);
  const state=root=>{const d=fixture();d.session.root=root;d.session.roots=['.','access'];return d;};
  const response=data=>({ok:true,json:async()=>data});
  const pending=local.window.ArcadeSession.mount(target,{id:'13'},{esc,notify:()=>{}});
  requests[0].resolve(response(state('.')));const dispose=await pending;
  rootControl.value='access';rootControl.onchange();
  planButton.onclick();
  assert.equal(posts.length,0,'loading another root must not submit the previous root');
  assert.equal(planButton.disabled,true);
  requests[1].resolve(response(state('access')));await new Promise(setImmediate);
  planButton.onclick();
  assert.equal(posts[0].root,'access');dispose();
});
