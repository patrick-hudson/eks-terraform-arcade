/* Pure persisted practice state. No timers, browser APIs or cloud calls here. */
(function (root) {
  'use strict';
  const stages = ['brief','build','investigate','verify','cleanup'];
  const evidenceFields = ['symptom','hypothesis','observation','fix','verification','cleanup'];
  const safeKey = key => !['__proto__','constructor','prototype'].includes(key);
  const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  function normalize(raw) {
    const value = object(raw), timer = object(value.timer);
    return {
      stage: stages.includes(value.stage) ? value.stage : 'brief',
      completed: stages.filter(stage => Array.isArray(value.completed) && value.completed.includes(stage)),
      tasks: Object.fromEntries(Object.entries(object(value.tasks)).filter(([key,val]) => safeKey(key) && key.length < 160 && val === true)),
      evidence: Object.fromEntries(evidenceFields.map(key => [key,typeof value.evidence?.[key] === 'string' ? value.evidence[key].slice(0,50000) : ''])),
      hintCounts: Object.fromEntries(stages.map(key => [key,Number.isInteger(value.hintCounts?.[key]) ? Math.max(0,Math.min(10,value.hintCounts[key])) : 0])),
      timer: {elapsedMs:Number.isFinite(timer.elapsedMs) ? Math.max(0,timer.elapsedMs) : 0, runningSince:Number.isFinite(timer.runningSince) && timer.runningSince >= 0 ? timer.runningSince : null},
      mode: value.mode === 'interview' ? 'interview' : 'guided'
    };
  }
  function elapsed(value, now=Date.now()) {
    return value.timer.elapsedMs + (value.timer.runningSince === null ? 0 : Math.max(0,now-value.timer.runningSince));
  }
  function toggleTimer(value, now=Date.now()) {
    return {...value,timer: value.timer.runningSince === null ? {elapsedMs:value.timer.elapsedMs,runningSince:now} : {elapsedMs:elapsed(value,now),runningSince:null}};
  }
  function stageReady(value, stage) { return stage.tasks.length > 0 && stage.tasks.every(task => value.tasks[`${stage.id}:${task.id}`] === true); }
  function setTask(value, stage, task, checked) {
    return {...value,tasks:{...value.tasks,[`${stage}:${task}`]:checked},completed:checked ? value.completed : value.completed.filter(id => id !== stage)};
  }
  function formatTime(ms) {
    const seconds=Math.floor(ms/1000), minutes=Math.floor(seconds/60);
    return `${String(Math.floor(minutes/60)).padStart(2,'0')}:${String(minutes%60).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
  }
  const api = {stages,evidenceFields,normalize,elapsed,toggleTimer,stageReady,setTask,formatTime};
  if (typeof module !== 'undefined' && module.exports) module.exports=api; else root.ArcadePracticeCore=api;
})(globalThis);
