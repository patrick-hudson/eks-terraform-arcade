/* Receipt data is user-supplied evidence, never an authenticated cloud attestation. */
(function(root) {
  'use strict';
  const supported = new Set(['07-eks-foundation','08-kubernetes-release',...Array.from({length:8},(_,i)=>`11-incident-gauntlet/scenario-${String(i+1).padStart(2,'0')}`)]);
  const text=(value,max)=>typeof value==='string' && value.length>0 && value.length<=max;
  const iso=value=>text(value,40) && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$/.test(value) && Number.isFinite(Date.parse(value));
  function validate(value,labId) {
    const invalid=()=>{throw new Error('This is not a supported verification receipt. Run the current verifier and choose its JSON output.');};
    if(!value || value.schemaVersion!==1 || value.kind!=='aws-arcade-verification' || value.toolVersion!=='1') invalid();
    if(!supported.has(value.labId)) invalid();
    if(value.labId!==labId) throw new Error('This receipt belongs to another mission. Open that mission before importing it.');
    if(!['verify','cleanup'].includes(value.phase) || !iso(value.generatedAt) || !text(value.scope,2000)) invalid();
    const env=value.environment;
    if(!env || typeof env.account!=='string' || !/^\d{12}$/.test(env.account) || !text(env.region,40) || !text(env.cluster,100) || !text(env.context,200)) invalid();
    if(!Array.isArray(value.checks) || !value.checks.length || value.checks.length>40) invalid();
    const ids=new Set(), summary={passed:0,failed:0,errors:0};
    const checks=value.checks.map(check=>{
      if(!check || !text(check.id,100) || ids.has(check.id) || !text(check.label,200) || !['pass','fail','error'].includes(check.status) || !text(check.expected,4000) || !text(check.observed,4000)) invalid();
      ids.add(check.id);summary[{pass:'passed',fail:'failed',error:'errors'}[check.status]]++;
      return {id:check.id,label:check.label,status:check.status,expected:check.expected,observed:check.observed};
    });
    if(!value.summary || Object.keys(summary).some(key=>value.summary[key]!==summary[key])) invalid();
    return {schemaVersion:1,kind:value.kind,toolVersion:'1',labId,phase:value.phase,generatedAt:value.generatedAt,scope:value.scope,environment:{account:env.account,region:env.region,cluster:env.cluster,context:env.context},checks,summary};
  }
  function parse(raw,labId) {
    if(typeof raw!=='string' || raw.length>262144) throw new Error('Choose a verifier JSON receipt smaller than 256 KB.');
    let value;try{value=JSON.parse(raw);}catch{throw new Error('The receipt is not valid JSON.');}
    return validate(value,labId);
  }
  const identity=value=>[value.labId,value.phase,value.generatedAt,...Object.values(value.environment)].join('|');
  function add(history,receipt) {
    const clean=validate(receipt,receipt.labId);
    const all=[clean,...history.filter(item=>identity(item)!==identity(clean))].sort((a,b)=>Date.parse(b.generatedAt)-Date.parse(a.generatedAt));
    const counts={verify:0,cleanup:0};return all.filter(item=>++counts[item.phase]<=3);
  }
  function importHistory(history,receipt) {
    const updated=add(history,receipt);
    const selected=updated.filter(item=>item.phase===receipt.phase).findIndex(item=>identity(item)===identity(receipt));
    if(selected<0) throw new Error('This receipt is older than the three retained reports for this phase. It was not imported; your existing history is unchanged.');
    return {history:updated,selected};
  }
  function normalizeHistory(values,labId) {
    let history=[];
    if(Array.isArray(values)) for(const value of values.slice(0,20)) {try{history=add(history,validate(value,labId));}catch{/* Preserve notes even if one old receipt is damaged. */}}
    return history;
  }
  function compare(current,previous) {
    if(!current || !previous || current.labId!==previous.labId || current.phase!==previous.phase || ['account','region','cluster','context'].some(key=>current.environment[key]!==previous.environment[key])) return [];
    return current.checks.flatMap(check=>{const before=previous.checks.find(item=>item.id===check.id);return before && before.status!==check.status ? [{id:check.id,label:check.label,from:before.status,to:check.status}] : [];});
  }
  function outcome(receipt) {return receipt.summary.errors?'error':receipt.summary.failed?'fail':'pass';}
  const api={supported,parse,validate,add,importHistory,normalizeHistory,compare,outcome};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ArcadeVerificationCore=api;
})(globalThis);
