const {test} = require('node:test');
const assert = require('node:assert/strict');
const P = require('../practice-core.js');
const C = require('../core.js');

test('v1 notes and completion survive migration to guided practice', () => {
  const old = {schemaVersion:1,labs:{a:{status:'done',notes:'real evidence',checks:{reproduce:true,diagnose:true,verify:true,cleanup:true}}},lastLab:'a'};
  const result = C.readProgress(JSON.stringify(old));
  assert.equal(result.schemaVersion,3);
  assert.equal(result.labs.a.notes,'real evidence');
  assert.equal(result.labs.a.status,'done');
  assert.deepEqual(result.labs.a.practice.completed,[]);
});
test('timer resumes across reload, pauses once, and rejects malformed timestamps', () => {
  const value=P.normalize({timer:{elapsedMs:4000,runningSince:1000}});
  assert.equal(P.elapsed(value,6000),9000);
  const paused=P.toggleTimer(value,6000);
  assert.equal(P.elapsed(paused,10000),9000);
  assert.equal(P.normalize({timer:{elapsedMs:-1,runningSince:'yesterday'}}).timer.runningSince,null);
  assert.equal(P.elapsed(P.normalize({timer:{elapsedMs:0,runningSince:999999999}}),1),0);
});
test('task changes invalidate only their stage and cleanup remains independent', () => {
  const stage={id:'build',tasks:[{id:'apply'},{id:'observe'}]};
  let value=P.normalize({completed:['build','cleanup'],tasks:{'build:apply':true,'build:observe':true}});
  assert.equal(P.stageReady(value,stage),true);
  value=P.setTask(value,'build','apply',false);
  assert.equal(P.stageReady(value,stage),false);
  assert.deepEqual(value.completed,['cleanup']);
});
test('practice state survives storage and untrusted keys are rejected', () => {
  const saved=C.readProgress(JSON.stringify({schemaVersion:2,labs:{a:{practice:{stage:'verify',evidence:{hypothesis:'selector mismatch'},hintCounts:{investigate:2},mode:'interview'}}}}));
  assert.equal(saved.labs.a.practice.stage,'verify');
  assert.equal(saved.labs.a.practice.evidence.hypothesis,'selector mismatch');
  assert.equal(saved.labs.a.practice.hintCounts.investigate,2);
  assert.equal(saved.labs.a.practice.mode,'interview');
  assert.equal(P.normalize({stage:'hacked',completed:['cleanup','hacked'],tasks:JSON.parse('{"__proto__":true}')}).stage,'brief');
  assert.equal({}.polluted,undefined);
});
test('backup merge preserves newer notes, ignores unknown labs and rejects wrong versions', () => {
  const current=C.readProgress(JSON.stringify({schemaVersion:2,labs:{a:{notes:'new',updatedAt:'2026-10-04T12:00:00Z'},b:{notes:'old',updatedAt:'2026-10-01T12:00:00Z'}}}));
  const imported={schemaVersion:1,labs:{a:{notes:'stale',updatedAt:'2026-10-03T12:00:00Z'},b:{notes:'restored',updatedAt:'2026-10-04T12:00:00Z'},unknown:{notes:'skip'}}};
  const result=C.mergeProgress(current,JSON.stringify(imported),['a','b']);
  assert.equal(result.progress.labs.a.notes,'new');
  assert.equal(result.progress.labs.b.notes,'restored');
  assert.equal(result.progress.labs.unknown,undefined);
  assert.equal(result.imported,1);
  assert.throws(()=>C.mergeProgress(current,'{}',['a']),/backup/i);
  assert.throws(()=>C.mergeProgress(current,JSON.stringify({...imported,schemaVersion:9}),['a']),/backup/i);
});
test('export snapshots running clocks and later imports never accrue time',()=>{
  const state=C.readProgress(JSON.stringify({schemaVersion:2,labs:{a:{updatedAt:new Date(60000).toISOString(),practice:{timer:{elapsedMs:1000,runningSince:0}}}}}));
  const snapshot=C.snapshotProgress(state,60000);
  assert.deepEqual(snapshot.labs.a.practice.timer,{elapsedMs:61000,runningSince:null});
  const restored=C.mergeProgress(C.readProgress(null),JSON.stringify(snapshot),['a']);
  assert.equal(P.elapsed(restored.progress.labs.a.practice,1000000000),61000);
  const legacy=C.mergeProgress(C.readProgress(null),JSON.stringify(state),['a']);
  assert.equal(legacy.progress.labs.a.practice.timer.elapsedMs,61000);
});
test('cross-tab merging preserves independent edits without pausing live clocks',()=>{
  const first=C.readProgress(JSON.stringify({schemaVersion:2,labs:{a:{notes:'tab one',updatedAt:'2026-10-04T12:00:00Z'}}}));
  const second=C.readProgress(JSON.stringify({schemaVersion:2,labs:{b:{notes:'tab two',updatedAt:'2026-10-04T12:01:00Z',practice:{timer:{runningSince:2000,elapsedMs:0}}}}}));
  const result=C.mergeStored(first,second);
  assert.equal(result.labs.a.notes,'tab one');assert.equal(result.labs.b.notes,'tab two');
  assert.equal(result.labs.b.practice.timer.runningSince,2000);
});
test('repeat attempt resets every completion flag while retaining evidence and notes',()=>{
  const record=C.blankRecord();record.status='done';record.notes='keep';record.practice=P.normalize({completed:P.stages,tasks:{'build:a':true},evidence:{symptom:'keep too'},hintCounts:{investigate:3},timer:{elapsedMs:9000}});
  const result=C.resetPractice(record);
  assert.equal(result.status,'active');assert.deepEqual(result.practice.completed,[]);assert.deepEqual(result.practice.tasks,{});assert.equal(result.practice.timer.elapsedMs,0);assert.equal(result.practice.hintCounts.investigate,0);assert.equal(result.practice.evidence.symptom,'keep too');assert.equal(result.notes,'keep');
});
