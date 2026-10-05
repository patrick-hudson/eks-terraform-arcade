/* Public recipes become fixed local preparation commands, never executable API input. */
(function(root) {
  'use strict';
  const identifier=/^\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*(?:\/scenario-\d{2})?$/;
  const relativePath=/^[a-zA-Z0-9_-]+(?:\/[a-zA-Z0-9_-]+)*$/;
  const text=(value,max)=>typeof value==='string' && value.length>0 && value.length<=max;
  function validate(value,expectedId=value?.id) {
    const invalid=()=>{throw new Error('The launch recipe is unavailable or incompatible. Open the launcher guide or retry after restarting the local server.');};
    if(!value || !text(value.id,100) || !identifier.test(value.id) || value.id!==expectedId) invalid();
    const alias=value.id.includes('/scenario-')?`${value.id.slice(0,2)}-${value.id.slice(-2)}`:value.id.slice(0,2);
    if(value.alias!==alias || !['terraform','kubernetes','runbook'].includes(value.kind) || !text(value.title,200) || !text(value.cost,1000)) invalid();
    if(!Array.isArray(value.prerequisites) || value.prerequisites.length>20 || value.prerequisites.some(id=>!text(id,100)||!identifier.test(id))) invalid();
    if(!value.modes || typeof value.modes!=='object' || Array.isArray(value.modes)) invalid();
    const modes={};
    for(const [key,mode] of Object.entries(value.modes)) {
      if(!['starter','guided'].includes(key) || !mode || !text(mode.label,100) || !text(mode.description,1000)) invalid();
      modes[key]={label:mode.label,description:mode.description};
    }
    if(value.kind==='runbook') {
      if(value.runDirectory!==null || Object.keys(modes).length) invalid();
    } else if(!text(value.runDirectory,200) || !relativePath.test(value.runDirectory) || !Object.keys(modes).length) invalid();
    return {id:value.id,alias,title:value.title,kind:value.kind,runDirectory:value.runDirectory,prerequisites:[...value.prerequisites],cost:value.cost,modes};
  }
  function defaultMode(recipe) {return recipe.modes.starter?'starter':Object.keys(recipe.modes)[0]||null;}
  function commands(recipe,mode=defaultMode(recipe)) {
    const clean=validate(recipe);
    if(clean.kind==='runbook')return null;
    if(!Object.hasOwn(clean.modes,mode))throw new Error('Choose an available starting point.');
    return [
      'source "$(arcade root)/scripts/env.sh" &&',
      `arcade start ${clean.alias} --mode ${mode} &&`,
      `cd "$LAB_ROOT/run/${clean.runDirectory}" &&`,
      `arcade next ${clean.alias}`
    ].join('\n');
  }
  const api={validate,defaultMode,commands};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ArcadeLauncherCore=api;
})(globalThis);
