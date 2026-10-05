const {test}=require('node:test');
const assert=require('node:assert/strict');
const L=require('../launcher-core.js');

const recipe=(changes={})=>({
  id:'05-serverless-counter', alias:'05', title:'Repair a serverless counter', kind:'terraform',
  runDirectory:'05-serverless-counter', prerequisites:['00-terraform-contracts'],
  cost:'Short Lambda and DynamoDB practice session.',
  modes:{guided:{label:'Guided build',description:'Start with the deliberate fault.'},starter:{label:'Blank starter',description:'Write the resources yourself.'}},
  ...changes
});

test('launch commands select starter by default and prepare the exact workspace without applying',()=>{
  const clean=L.validate(recipe(),'05-serverless-counter');
  assert.equal(L.defaultMode(clean),'starter');
  assert.equal(L.commands(clean,'starter'),[
    'source "$(arcade root)/scripts/env.sh" &&',
    'arcade start 05 --mode starter &&',
    'cd "$LAB_ROOT/run/05-serverless-counter" &&',
    'arcade next 05'
  ].join('\n'));
  assert.match(L.commands(clean,'guided'),/arcade start 05 --mode guided/);
  assert.doesNotMatch(L.commands(clean,'guided'),/terraform apply|kubectl apply|destroy/);
});

test('incident aliases and nested run directories remain fixed shell arguments',()=>{
  const incident=recipe({id:'11-incident-gauntlet/scenario-01',alias:'11-01',kind:'kubernetes',runDirectory:'11-incident-gauntlet/scenario-01',modes:{guided:{label:'Broken deployment',description:'Diagnose the workload.'}}});
  assert.equal(L.defaultMode(L.validate(incident,incident.id)),'guided');
  assert.match(L.commands(incident,'guided'),/arcade start 11-01 --mode guided/);
  assert.match(L.commands(incident,'guided'),/cd "\$LAB_ROOT\/run\/11-incident-gauntlet\/scenario-01"/);
});

test('wrong mission identities, unknown modes and shell-bearing paths never produce commands',()=>{
  assert.throws(()=>L.validate(recipe(),'07-eks-foundation'));
  for(const runDirectory of ['../other','/tmp/other','run/../other','safe//other','safe; touch nope','$(whoami)','safe/"bad','safe\\bad','safe\nother','safe/.hidden']) {
    assert.throws(()=>L.commands(recipe({runDirectory}),'starter'),runDirectory);
  }
  for(const change of [{alias:'05;id'},{alias:'07'},{id:'05;id'},{kind:'shell'},{modes:{custom:{label:'Custom',description:'No.'}}}]) {
    assert.throws(()=>L.commands(recipe(change),'starter'));
  }
  assert.throws(()=>L.commands(recipe(),'solution'));
  assert.throws(()=>L.commands(recipe({modes:{guided:recipe().modes.guided}}),'starter'));
});

test('runbook-only missions expose prerequisites without a generated start command',()=>{
  const runbook=recipe({id:'12-capstone',alias:'12',kind:'runbook',runDirectory:null,modes:{},prerequisites:['07-eks-foundation','08-kubernetes-release']});
  const clean=L.validate(runbook,runbook.id);
  assert.equal(L.defaultMode(clean),null);
  assert.equal(L.commands(clean,null),null);
  assert.deepEqual(clean.prerequisites,['07-eks-foundation','08-kubernetes-release']);
  assert.throws(()=>L.validate({...runbook,runDirectory:'12-capstone'},runbook.id));
});
