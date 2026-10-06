const {test}=require('node:test');
const assert=require('node:assert/strict');
const D=require('../drills-core.js');
const C=require('../core.js');

test('finishing explicitly archives once, preserves first answer, and reset makes a fresh attempt',()=>{
  let s=D.begin(null,'service-a','attempt-1',1000);
  s=D.reveal(s,'service-a','events',2000);
  s=D.respond(s,'service-a','wrong',false,3000);
  s=D.respond(s,'service-a','right',true,4000);
  assert.equal(s.history.length,0);
  s=D.finish(s,'service-a',5000);
  assert.deepEqual(s.history[0],{attemptId:'attempt-1',drillId:'service-a',completedAt:5000,firstCorrect:false,observations:['events'],durationMs:4000});
  assert.equal(D.finish(s,'service-a',6000).history.length,1);
  s=D.begin(s,'service-a','attempt-2',7000);
  assert.deepEqual(s.current['service-a'].observations,[]);
  assert.equal(s.history.length,1);
});

test('history merges by attempt identity and retains only the newest twenty',()=>{
  let left=D.normalize(null),right=D.normalize(null);
  for(let i=1;i<=25;i++){
    let s=D.begin(null,'case-a',`attempt-${i}`,i*1000);
    s=D.respond(s,'case-a','yes',true,i*1000+1);
    s=D.finish(s,'case-a',i*1000+2);
    if(i%2)left=D.merge(left,s); else right=D.merge(right,s);
  }
  const merged=D.merge(D.merge(left,right),left);
  assert.equal(merged.history.length,20);
  assert.equal(new Set(merged.history.map(x=>x.attemptId)).size,20);
  assert.equal(merged.history[0].attemptId,'attempt-25');
  assert.equal(merged.history.at(-1).attemptId,'attempt-6');
});

test('old mission backups migrate and drill state survives snapshot and restore with paused clocks',()=>{
  const old=C.readProgress(JSON.stringify({schemaVersion:2,labs:{a:{notes:'keep my notes',receipts:[]}},lastLab:'a'}));
  assert.equal(old.schemaVersion,3);
  old.drills=D.begin(null,'case-a','attempt-a',1000);
  const snapshot=C.snapshotProgress(old,4000);
  assert.equal(snapshot.drills.current['case-a'].runningSince,null);
  assert.equal(snapshot.drills.current['case-a'].elapsedMs,3000);
  const restored=C.mergeProgress(C.readProgress(null),JSON.stringify(snapshot),['a']).progress;
  assert.equal(restored.labs.a.notes,'keep my notes');
  assert.equal(restored.drills.current['case-a'].elapsedMs,3000);
});

test('suggestion explains latest incorrect attempt, then unseen, then oldest; no mastery score',()=>{
  const catalog=[{id:'a'},{id:'b'},{id:'c'}];
  let s=D.respond(D.begin(null,'a','a-1',100),'a','x',false,200);
  s=D.finish(s,'a',300);
  assert.equal(D.suggest(catalog,s).id,'a');
  assert.match(D.suggest(catalog,s).reason,/first answer/i);
  s=D.respond(D.begin(s,'a','a-2',400),'a','y',true,500);
  s=D.finish(s,'a',600);
  assert.equal(D.suggest(catalog,s).id,'b');
  assert.equal(C.parseRoute('#/practice').kind,'practice');
  assert.deepEqual(C.parseRoute('#/drill/case-a'),{kind:'drill',id:'case-a'});
});
