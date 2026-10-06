/* Bounded, self-reported practice history. No live infrastructure conclusions. */
(function(root){
  'use strict';
  const validId=value=>typeof value==='string'&&/^[a-zA-Z0-9_-]{1,100}$/.test(value);
  const time=value=>Number.isFinite(value)&&value>=0?value:0;
  const ids=value=>Array.isArray(value)?[...new Set(value.filter(validId))].slice(0,50):[];
  function normalize(value){
    const clean={current:{},history:[]};
    if(!value||typeof value!=='object')return clean;
    for(const [drillId,a] of Object.entries(value.current||{}).slice(0,100)){
      if(!validId(drillId)||['__proto__','constructor','prototype'].includes(drillId)||!a||!validId(a.attemptId))continue;
      clean.current[drillId]={attemptId:a.attemptId,drillId,startedAt:time(a.startedAt),updatedAt:time(a.updatedAt),elapsedMs:time(a.elapsedMs),runningSince:typeof a.runningSince==='number'?time(a.runningSince):null,observations:ids(a.observations),selectedAnswer:validId(a.selectedAnswer)?a.selectedAnswer:null,firstCorrect:typeof a.firstCorrect==='boolean'?a.firstCorrect:null,finishedAt:time(a.finishedAt)};
    }
    const seen=new Map();
    for(const a of Array.isArray(value.history)?value.history:[]){
      if(!a||!validId(a.attemptId)||!validId(a.drillId)||typeof a.firstCorrect!=='boolean'||!time(a.completedAt))continue;
      const item={attemptId:a.attemptId,drillId:a.drillId,completedAt:time(a.completedAt),firstCorrect:a.firstCorrect,observations:ids(a.observations),durationMs:time(a.durationMs)};
      if(!seen.has(item.attemptId)||seen.get(item.attemptId).completedAt<item.completedAt)seen.set(item.attemptId,item);
    }
    clean.history=[...seen.values()].sort((a,b)=>b.completedAt-a.completedAt||a.attemptId.localeCompare(b.attemptId)).slice(0,20);
    return clean;
  }
  const elapsed=(a,now)=>time(a.elapsedMs)+(a.runningSince===null?0:Math.max(0,now-a.runningSince));
  function begin(value,drillId,attemptId,now=Date.now()){
    const s=normalize(value);
    if(!validId(drillId)||!validId(attemptId)||['__proto__','constructor','prototype'].includes(drillId))return s;
    s.current[drillId]={attemptId,drillId,startedAt:now,updatedAt:Math.max(now,(s.current[drillId]?.updatedAt||0)+1),elapsedMs:0,runningSince:now,observations:[],selectedAnswer:null,firstCorrect:null,finishedAt:0};
    return s;
  }
  function update(value,drillId,now,change){
    const s=normalize(value),a=s.current[drillId];
    if(a&&!a.finishedAt){change(a);a.updatedAt=Math.max(now,a.updatedAt+1);}
    return s;
  }
  const reveal=(s,id,observation,now=Date.now())=>update(s,id,now,a=>{if(validId(observation)&&!a.observations.includes(observation))a.observations.push(observation);});
  const respond=(s,id,option,correct,now=Date.now())=>update(s,id,now,a=>{if(validId(option)&&typeof correct==='boolean'){a.selectedAnswer=option;if(a.firstCorrect===null)a.firstCorrect=correct;}});
  function finish(value,id,now=Date.now()){
    const s=normalize(value),a=s.current[id];
    if(!a||a.finishedAt||typeof a.firstCorrect!=='boolean')return s;
    a.elapsedMs=elapsed(a,now);a.runningSince=null;a.finishedAt=now;a.updatedAt=Math.max(now,a.updatedAt+1);
    s.history.push({attemptId:a.attemptId,drillId:id,completedAt:now,firstCorrect:a.firstCorrect,observations:[...a.observations],durationMs:a.elapsedMs});
    return normalize(s);
  }
  function snapshot(value,now=Date.now()){
    const s=normalize(value);
    for(const a of Object.values(s.current)){a.elapsedMs=elapsed(a,now);a.runningSince=null;}
    return s;
  }
  function merge(left,right){
    const a=normalize(left),b=normalize(right);
    for(const [id,attempt] of Object.entries(b.current))if(!a.current[id]||attempt.updatedAt>a.current[id].updatedAt)a.current[id]=attempt;
    a.history.push(...b.history);
    return normalize(a);
  }
  function suggest(catalog,value){
    const s=normalize(value),latest=new Map();
    for(const item of s.history)if(!latest.has(item.drillId))latest.set(item.drillId,item);
    const retry=catalog.find(d=>latest.get(d.id)?.firstCorrect===false);
    if(retry)return {id:retry.id,reason:'Your first answer differed from the evidence last time. Try a fresh investigation.'};
    const unseen=catalog.find(d=>!latest.has(d.id));
    if(unseen)return {id:unseen.id,reason:'You have no completed attempt for this drill yet.'};
    const oldest=[...catalog].sort((a,b)=>latest.get(a.id).completedAt-latest.get(b.id).completedAt)[0];
    return oldest?{id:oldest.id,reason:'This is your least recently completed drill. Explain it again without the debrief.'}:null;
  }
  const api={normalize,begin,reveal,respond,finish,snapshot,merge,suggest,elapsed};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ArcadeDrillsCore=api;
})(globalThis);
