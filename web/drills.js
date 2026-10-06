/* Authored simulations only. This player never executes a displayed command. */
(()=>{
  'use strict';
  const D=window.ArcadeDrillsCore;
  async function request(path,params){
    const response=await fetch(path+(params?'?'+new URLSearchParams(params):''));
    if(!response.ok)throw new Error('Practice could not be loaded. Check the local server and try again.');
    return response.json();
  }
  const route=id=>'#/drill/'+encodeURIComponent(id);
  const duration=ms=>`${Math.max(1,Math.round(ms/60000))} min`;
  async function desk(target,context){
    const {esc,icon,getState,isCurrent}=context;
    const catalog=(await request('/api/drills')).drills;
    if(!isCurrent())return;
    const state=D.normalize(getState()),suggestion=D.suggest(catalog,state);
    const recommended=catalog.find(item=>item.id===suggestion?.id);
    target.innerHTML=`<section class="drill-hero"><div><span class="eyebrow">PRACTICE DESK · NO AWS REQUIRED</span><h1>Make the call.<br><span>Then defend it.</span></h1><p>Similar symptoms. Different causes. Choose the evidence that matters, review a Terraform change, and explain what you would do next.</p><div class="drill-benefits"><span>7 short drills</span><span>$0 AWS spending</span><span>Terraform repairs</span></div></div>${recommended?`<aside class="drill-recommendation"><span class="eyebrow">A PLACE TO START</span><h2>${esc(recommended.title)}</h2><p>${esc(suggestion.reason)}</p><a class="button primary" href="${route(recommended.id)}">Open drill ${icon('arrow')}</a><small>A practice suggestion, never a skill rating.</small></aside>`:''}</section>
      <div class="drill-explainer">${icon('book')}<p><strong>This is an investigation, not a command race.</strong> Request as much evidence as you need. All outputs here are authored simulations. The hands-on labs are where you test real infrastructure.</p></div>
      ${[['investigation','Evidence Room','Separate plausible causes'],['plan','Plan Clinic','Explain the change before applying it']].map(([kind,title,subtitle])=>`<section class="drill-section"><div class="section-heading"><div><span class="section-kicker">${esc(subtitle)}</span><h2>${title}</h2></div><span class="section-count">${catalog.filter(d=>d.kind===kind).length} drills</span></div><div class="drill-grid">${catalog.filter(d=>d.kind===kind).map(d=>{const attempts=state.history.filter(a=>a.drillId===d.id);return `<a class="drill-card" href="${route(d.id)}"><span class="drill-card-icon">${icon(kind==='plan'?'layers':'search')}</span><span class="drill-time">${d.minutes} min</span><h3>${esc(d.title)}</h3><p>${esc(d.summary)}</p><div class="drill-skill-list">${d.skills.map(s=>`<span>${esc(s.replaceAll('-',' '))}</span>`).join('')}</div><div class="drill-card-footer"><span>${attempts.length?`${attempts.length} saved attempt${attempts.length===1?'':'s'}`:'Fresh investigation'}</span>${icon('arrow')}</div></a>`;}).join('')}</div></section>`).join('')}
      <section class="drill-plan-handoff"><div><h2>Bring your own Terraform plan.</h2><p>Run <code>arcade review-plan plan.json</code> locally for an explanation of actions and uncertainty. Your plan stays in your terminal.</p></div><a class="button secondary" href="#/guide/plan-review">Plan coach guide ${icon('arrow')}</a></section>
      <section class="drill-history"><h2>Recent attempts</h2><p>Up to 20 completed attempts, saved with your existing progress backup. These records do not mark live missions complete.</p>${state.history.length?`<ol>${state.history.slice(0,7).map(a=>`<li><a href="${route(a.drillId)}">${esc(catalog.find(d=>d.id===a.drillId)?.title||a.drillId)}</a><span>${a.firstCorrect?'First answer matched':'Worth another look'} · ${duration(a.durationMs)} · ${a.observations.length} observations</span></li>`).join('')}</ol>`:'<p class="drill-empty">Finish a drill to save your first attempt.</p>'}</section>`;
  }
  async function mount(target,id,context){
    const {esc,icon,getState,setState,isCurrent,notify}=context;
    let live=true,generation=0,feedback=null,answerBusy=false;
    const outputs=new Map(),busy=new Set();
    const active=()=>live&&isCurrent()&&target.isConnected;
    const drill=await request('/api/drill',{id});
    if(!active())return ()=>{};
    const makeId=()=>crypto.randomUUID();
    let state=D.normalize(getState());
    if(!state.current[id])state=D.begin(state,id,makeId());
    else if(!state.current[id].finishedAt&&state.current[id].runningSince===null){state.current[id].runningSince=Date.now();state.current[id].updatedAt=Math.max(Date.now(),state.current[id].updatedAt+1);}
    setState(state);
    const attempt=()=>D.normalize(getState()).current[id];
    const write=transform=>{if(active())setState(transform(getState()));};
    const keepFocus=()=>document.activeElement?.dataset?.evidence||null;
    function render(){
      if(!active())return;
      const a=attempt(),focus=keepFocus(),history=D.normalize(getState()).history.filter(x=>x.drillId===id);
      target.innerHTML=`<a class="back-link" href="#/practice">${icon('back')} Practice desk</a><header class="drill-header"><span class="eyebrow">${drill.kind==='plan'?'PLAN CLINIC':'EVIDENCE ROOM'} · AUTHORED SIMULATION</span><h1>${esc(drill.title)}</h1><p>${esc(drill.summary)}</p><div class="drill-benefits"><span>${drill.minutes} min suggested</span><span>No AWS resources</span><span>No command penalty</span></div></header><div class="drill-layout"><div class="drill-main"><section class="drill-brief"><span class="section-kicker">THE SITUATION</span><p>${esc(drill.brief)}</p><small>${esc(drill.provenance)}</small></section><section class="drill-evidence"><div class="section-heading"><div><span class="section-kicker">01 / INVESTIGATE</span><h2>What will you inspect?</h2></div></div><p>Choose an observation. Compare explanations before changing anything.</p>${drill.observations.map(o=>`<article class="drill-observation"><button class="drill-evidence-button" data-evidence="${esc(o.id)}" ${busy.has(o.id)?'disabled':''} aria-expanded="${outputs.has(o.id)}"><span>${icon(outputs.has(o.id)?'check':'terminal')}<strong>${esc(o.label)}</strong></span><span>${busy.has(o.id)?'Loading…':outputs.has(o.id)?'Observed':'Inspect'}</span></button><code class="drill-command">${esc(o.command)}</code>${outputs.has(o.id)?`<pre tabindex="0" aria-label="${esc(o.label)} simulated output">${esc(outputs.get(o.id))}</pre>`:''}</article>`).join('')}</section><section class="drill-decision"><span class="section-kicker">02 / MAKE THE CALL</span><h2>${esc(drill.question.prompt)}</h2><p>Your first answer is recorded when you finish. You can review alternatives before then.</p><div class="drill-options">${drill.question.options.map(o=>`<button class="drill-option ${a.selectedAnswer===o.id?'is-selected':''}" data-option="${esc(o.id)}" ${answerBusy||a.finishedAt?'disabled':''}><span>${esc(o.text)}</span>${a.selectedAnswer===o.id?icon('check'):icon('arrow')}</button>`).join('')}</div><div class="drill-feedback" aria-live="polite">${answerBusy?'<p>Reviewing the evidence…</p>':feedback?`<section class="drill-debrief"><span class="drill-result ${feedback.correct?'matched':'rethink'}">${feedback.correct?'Your answer matches the evidence':'Compare your answer with the evidence'}</span><h3>Why this explanation fits</h3><p>${esc(feedback.explanation)}</p><p><strong>Decisive observations:</strong> ${feedback.decisiveEvidence.map(key=>esc(drill.observations.find(o=>o.id===key)?.label||key)).join(', ')}</p>${[['repair','Repair through Terraform'],['verification','Prove recovery'],['cleanup','Close the session'],['followUp','Now change one constraint']].map(([key,title])=>`<h3>${title}</h3><p class="drill-preserve">${esc(feedback[key])}</p>`).join('')}<div class="drill-related"><strong>Try it on real infrastructure</strong>${drill.relatedLabs.map(lab=>`<a href="${window.ArcadeCore.labRoute(lab)}">${esc(lab.replaceAll('-',' '))} ${icon('arrow')}</a>`).join('')}</div>${a.finishedAt?'<p class="drill-finished">Attempt saved. The live mission remains unchanged.</p>':'<button class="button primary" data-finish>Finish attempt and save summary</button>'}</section>`:''}</div></section></div><aside class="drill-notebook"><span class="eyebrow">YOUR INVESTIGATION</span><h2>Follow the evidence.</h2><p>The order you chose is a useful interview story. Extra observations never cost points.</p><ol class="drill-order">${a.observations.map(key=>`<li>${esc(drill.observations.find(o=>o.id===key)?.label||key)}</li>`).join('')||'<li class="drill-empty">No observations yet.</li>'}</ol><button class="button secondary" data-new>New attempt ${icon('arrow')}</button><p class="field-note">A new attempt clears this investigation. Only explicitly finished attempts enter history.</p><div class="drill-attempt-list"><h3>${history.length} saved attempt${history.length===1?'':'s'}</h3>${history.slice(0,5).map(h=>`<p>${h.firstCorrect?'First answer matched':'First answer differed'}<small>${duration(h.durationMs)} · ${h.observations.length} observations</small></p>`).join('')}</div><a class="inline-link" href="#/practice">Choose another drill ${icon('arrow')}</a></aside></div>`;
      target.querySelectorAll('[data-evidence]').forEach(button=>button.onclick=()=>reveal(button.dataset.evidence));
      target.querySelectorAll('[data-option]').forEach(button=>button.onclick=()=>answer(button.dataset.option));
      target.querySelector('[data-new]').onclick=()=>{generation++;outputs.clear();busy.clear();feedback=null;answerBusy=false;write(s=>D.begin(s,id,makeId()));render();target.querySelector('[data-evidence]')?.focus();};
      target.querySelector('[data-finish]')?.addEventListener('click',()=>{write(s=>D.finish(s,id));render();notify('Attempt saved. Export progress to keep a backup.');});
      if(focus)target.querySelector(`[data-evidence="${focus}"]`)?.focus();
    }
    async function reveal(evidenceId,restoring=false){
      if(busy.has(evidenceId)||outputs.has(evidenceId))return;
      const token=generation,attemptId=attempt()?.attemptId;busy.add(evidenceId);render();
      try{
        const data=await request('/api/drill-evidence',{id,evidence:evidenceId});
        if(!active()||token!==generation||attempt()?.attemptId!==attemptId)return;
        outputs.set(evidenceId,data.output);
        if(!restoring)write(s=>D.reveal(s,id,evidenceId));
      }catch(error){if(active()&&token===generation&&attempt()?.attemptId===attemptId)notify(error.message);}
      finally{if(active()&&token===generation&&attempt()?.attemptId===attemptId){busy.delete(evidenceId);render();}}
    }
    async function answer(optionId,restoring=false){
      if(answerBusy)return;
      const token=generation,attemptId=attempt()?.attemptId;answerBusy=true;render();
      try{
        const data=await request('/api/drill-answer',{id,answer:optionId});
        if(!active()||token!==generation||attempt()?.attemptId!==attemptId)return;
        feedback=data;if(!restoring)write(s=>D.respond(s,id,optionId,data.correct));
      }catch(error){if(active()&&token===generation&&attempt()?.attemptId===attemptId)notify(error.message);}
      finally{if(active()&&token===generation&&attempt()?.attemptId===attemptId){answerBusy=false;render();}}
    }
    render();
    for(const observation of attempt().observations)void reveal(observation,true);
    if(attempt().selectedAnswer)void answer(attempt().selectedAnswer,true);
    return ()=>{live=false;generation++;};
  }
  window.ArcadeDrills={desk,mount};
})();
