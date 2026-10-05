/* Guided workspace. Knowledge checks use a read-only API; commands never execute. */
(() => {
  'use strict';
  const P=window.ArcadePracticeCore, C=window.ArcadeCore;
  const names={brief:'Brief',build:'Build',investigate:'Investigate',verify:'Verify',cleanup:'Cleanup'};
  const fields={symptom:'Observed symptom',hypothesis:'Working hypothesis',observation:'Decisive evidence / command output',fix:'Change made and why',verification:'Acceptance evidence',cleanup:'Deletion evidence / remaining resources'};
  async function request(endpoint, params) {
    const response=await fetch(`/api/${endpoint}?${new URLSearchParams(params)}`);
    if (!response.ok) throw new Error('Coaching could not be loaded. Check the local server and retry.');
    return response.json();
  }
  async function mount(panel, lab, context) {
    const {esc,icon,record,updateRecord,notify,copyText,getFile,renderMarkdown,isCurrent}=context;
    const lesson=await request('lesson',{id:lab.id});
    if (!isCurrent()) return () => {};
    let state=P.normalize(record(lab.id).practice), coachTab='coach', hintBodies=new Map(), disposed=false, busy=false, attempt=0;
    const alive=()=>!disposed && isCurrent() && panel.isConnected;
    // Hint requests belong to an attempt, even when the learner changes stages.
    const currentAttempt=generation=>alive() && generation===attempt;
    const persist=(next, changes={})=>{
      state=P.normalize(next);
      updateRecord(lab.id,{practice:state,...changes});
    };
    const stageCheck={build:'reproduce',investigate:'diagnose',verify:'verify',cleanup:'cleanup'};
    function saveTask(stage,task,checked) {
      const next=P.setTask(state,stage,task,checked), checks={...record(lab.id).checks};
      if (!checked && stageCheck[stage]) checks[stageCheck[stage]]=false;
      persist(next,{checks,status:'active'});
      const focus=`[data-task="${CSS.escape(task)}"]`;
      render(); panel.querySelector(focus)?.focus();
    }
    function completeStage(stage) {
      if (!P.stageReady(state,stage)) return;
      const completed=[...new Set([...state.completed,stage.id])], checks={...record(lab.id).checks};
      if (stageCheck[stage.id]) checks[stageCheck[stage.id]]=true;
      const done=lesson.stages.every(item=>completed.includes(item.id)) && C.isComplete({checks});
      const nextStage=lesson.stages[lesson.stages.findIndex(item=>item.id===stage.id)+1]?.id || stage.id;
      let next={...state,completed,stage:nextStage};
      if (done && next.timer.runningSince !== null) next=P.toggleTimer(next);
      persist(next,{checks,status:done?'done':'active'});
      notify(done?'Mission complete. Your evidence is ready for the debrief.':`${names[stage.id]} recorded. These are your own checks.`);
      render(); panel.querySelector('.stage-heading')?.focus();
    }
    function codeCards(stage) {
      return stage.commands.map((command,index)=>`<div class="code-frame"><div class="code-toolbar"><span>${esc(command.label)}</span><button class="copy-button" data-command="${index}">${icon('copy')} Copy</button></div><pre class="code-content" tabindex="0"><code>${esc(command.code)}</code></pre></div><p class="field-note"><strong>Expected:</strong> ${esc(command.expected)}</p>`).join('');
    }
    function render() {
      if (!alive()) return;
      const stage=lesson.stages.find(item=>item.id===state.stage), index=lesson.stages.indexOf(stage);
      panel.innerHTML=`<div class="session-banner"><span><strong>${state.completed.length} / 5 stages</strong> · Your checks</span>${record(lab.id).status==='done'?'<button class="button secondary small" id="new-attempt">New attempt · keep evidence</button>':''}<div class="mode-toggle" aria-label="Practice mode"><button data-mode="guided" class="${state.mode==='guided'?'is-active':''}" aria-pressed="${state.mode==='guided'}">Guided</button><button data-mode="interview" class="${state.mode==='interview'?'is-active':''}" aria-pressed="${state.mode==='interview'}">Interview</button></div><button class="button ghost small coach-jump" id="jump-coach">Coach & evidence ↓</button><a class="inline-link" href="${C.labRoute(lab.id,'notes')}">Freeform notes ${icon('arrow')}</a></div>
        <div class="skills-row">${lesson.skills.map(skill=>`<span class="skill-chip">${esc(skill)}</span>`).join('')}</div>
        <div class="guided-layout"><nav class="stage-rail" aria-label="Mission stages"><div class="stage-rail-title">MISSION WORKFLOW</div>${lesson.stages.map((item,i)=>`<button class="stage-button ${state.stage===item.id?'is-current':''} ${state.completed.includes(item.id)?'is-complete':''}" data-stage="${item.id}" ${state.stage===item.id?'aria-current="step"':''}><span class="stage-number">${String(i+1).padStart(2,'0')}</span><span><strong>${names[item.id]}</strong><small>${state.completed.includes(item.id)?'Recorded':state.stage===item.id?'You are here':'Not recorded'}</small></span>${state.completed.includes(item.id)?`<span class="stage-check">${icon('check')}</span>`:''}</button>`).join('')}<p class="field-note">Jump to cleanup at any time.</p></nav>
        <section class="stage-workspace"><div class="stage-heading" tabindex="-1"><span class="eyebrow">STEP ${String(index+1).padStart(2,'0')} OF 05</span><h2>${esc(stage.title)}</h2><p>${esc(stage.summary)}</p></div>
        ${stage.id==='brief'?`<div class="acceptance-box"><span>MISSION OBJECTIVE</span><p>${esc(lesson.objective)}</p></div>${lesson.prerequisites.length?`<div class="prerequisite-list"><span>Before this mission</span>${lesson.prerequisites.map(id=>`<a class="prerequisite-chip" href="${C.labRoute(id)}">Lab ${esc(id.split('-')[0])} ${icon('arrow')}</a>`).join('')}</div>`:''}<p class="session-reminder">${esc(lab.cost)} <a href="#/guide/cost-and-cleanup">Plan your $20 allowance and teardown.</a></p>`:''}
        ${['brief','build'].includes(stage.id)?'<div id="launcher-panel"></div>':''}
        <div class="task-list">${stage.tasks.map(task=>`<label class="task-item"><input type="checkbox" data-task="${esc(task.id)}" ${state.tasks[`${stage.id}:${task.id}`]?'checked':''}><span class="task-copy"><strong>${esc(task.title)}</strong><p>${esc(task.instruction)}</p><small><strong>Success:</strong> ${esc(task.success)}</small></span></label>`).join('')}</div>
        <div class="acceptance-box"><span>CHECKPOINT</span><p>${esc(stage.checkpoint)}</p></div>
        ${stage.commands.length?`<details class="stage-commands" ${state.mode==='guided'?'open':''}><summary>Command checkpoints · complete setup first</summary>${codeCards(stage)}</details>`:''}
        <div class="runbook-actions"><button class="button secondary" id="open-runbook">${icon('book')} Open complete runbook here</button><a class="runbook-link" href="${C.labRoute(lab.id,'brief')}">Full-screen instructions ${icon('arrow')}</a><a class="runbook-link" href="${C.labRoute(lab.id,'files')}">Starter & reference files ${icon('arrow')}</a></div><div id="inline-runbook" hidden></div>
        ${['verify','cleanup'].includes(stage.id)?'<div id="verification-panel"></div>':''}
        ${stage.id==='verify'?`<div class="reasoning-check"><span class="eyebrow">INTERVIEW CHECK · KNOWLEDGE ONLY</span>${lesson.questions.map(question=>`<form data-question="${esc(question.id)}"><fieldset><legend>${esc(question.prompt)}</legend>${question.options.map((option,i)=>`<label class="answer-option"><input type="radio" name="answer" value="${i}" required><span>${esc(option)}</span></label>`).join('')}</fieldset><button class="button secondary" type="submit">Check my reasoning</button><div class="feedback" role="status"></div></form>`).join('')}</div>`:''}
        ${stage.id==='cleanup'?`<div class="debrief-card"><span class="eyebrow">TAKE IT INTO THE INTERVIEW</span><h3>Explain the decision, then the proof.</h3><ul>${lesson.debriefPrompts.map(prompt=>`<li>${esc(prompt)}</li>`).join('')}</ul><button class="button secondary" id="export-debrief">${icon('download')} Export interview debrief</button><p class="field-note">Includes your structured evidence and freeform notes. Check the Evidence panel before exporting.</p></div>`:''}
        <div class="stage-footer"><button class="button ghost" id="previous-stage" ${index===0?'disabled':''}>${icon('back')} Previous</button><button class="button primary" id="complete-stage" ${P.stageReady(state,stage)?'':'disabled'}>${state.completed.includes(stage.id)?'Recorded · continue':stage.id==='cleanup'?'Record cleanup':'Record & continue'} ${icon('arrow')}</button></div><p class="field-note">Check tasks only after doing them. Progress is self-reported; the app does not inspect AWS.</p>
        </section><aside class="coach-panel" aria-label="Coaching and evidence"><div class="session-clock"><span>PRACTICE TIME</span><strong class="clock-value" id="practice-clock">${P.formatTime(P.elapsed(state))}</strong><div class="clock-controls"><button class="button secondary small" id="toggle-timer">${state.timer.runningSince===null?'Start / resume':'Pause'}</button></div><p class="field-note">Practice time only. Pausing does not stop AWS charges.</p></div><div class="coach-tabs"><button data-coach="coach" class="${coachTab==='coach'?'is-active':''}" aria-pressed="${coachTab==='coach'}">Coach</button><button data-coach="evidence" class="${coachTab==='evidence'?'is-active':''}" aria-pressed="${coachTab==='evidence'}">Evidence</button></div><div class="coach-body" id="coach-body"></div><button class="button ghost small coach-jump" id="back-to-task">↑ Back to task</button></aside></div>`;
      panel.querySelectorAll('[data-stage]').forEach(button=>button.onclick=()=>{persist({...state,stage:button.dataset.stage});render();panel.querySelector('.stage-heading')?.focus();});
      panel.querySelectorAll('[data-mode]').forEach(button=>button.onclick=()=>{persist({...state,mode:button.dataset.mode});render();});
      panel.querySelectorAll('[data-task]').forEach(input=>input.onchange=()=>saveTask(stage.id,input.dataset.task,input.checked));
      panel.querySelectorAll('[data-command]').forEach(button=>button.onclick=()=>copyText(stage.commands[Number(button.dataset.command)].code,button));
      panel.querySelector('#jump-coach').onclick=()=>{panel.querySelector('.coach-panel').scrollIntoView({behavior:'smooth',block:'start'});panel.querySelector('[data-coach=coach]').focus({preventScroll:true});};
      panel.querySelector('#back-to-task').onclick=()=>panel.querySelector('.stage-heading').focus();
      panel.querySelector('#new-attempt')?.addEventListener('click',()=>{attempt++;busy=false;const reset=C.resetPractice(record(lab.id));persist(reset.practice,reset);hintBodies.clear();render();notify('New attempt started. Previous evidence and notes are retained.');});
      panel.querySelector('#complete-stage').onclick=()=>completeStage(stage);
      panel.querySelector('#previous-stage').onclick=()=>{persist({...state,stage:lesson.stages[index-1].id});render();};
      panel.querySelector('#toggle-timer').onclick=()=>{persist(P.toggleTimer(state),{status:record(lab.id).status==='new'?'active':record(lab.id).status});render();};
      panel.querySelectorAll('[data-coach]').forEach(button=>button.onclick=()=>{coachTab=button.dataset.coach;renderCoach(stage);panel.querySelectorAll('[data-coach]').forEach(b=>{b.classList.toggle('is-active',b.dataset.coach===coachTab);b.setAttribute('aria-pressed',String(b.dataset.coach===coachTab));});});
      panel.querySelector('#open-runbook').onclick=async event=>{
        const button=event.currentTarget, target=panel.querySelector('#inline-runbook');
        if (!target.hidden) {target.hidden=true;button.textContent='Open complete runbook here';return;}
        button.disabled=true;
        try {const file=await getFile(stage.sourcePath);if (!alive() || !target.isConnected) return;renderMarkdown(target,file.content,stage.sourcePath);target.hidden=false;button.textContent='Close runbook';} catch(error) {notify(error.message);} finally {button.disabled=false;}
      };
      panel.querySelectorAll('[data-question]').forEach(form=>form.onsubmit=async event=>{
        event.preventDefault(); const answer=form.querySelector('input:checked');if (!answer) return;
        const button=form.querySelector('button');button.disabled=true;
        try {const result=await request('check',{id:lab.id,question:form.dataset.question,answer:answer.value});if (!alive()||!form.isConnected)return;const feedback=form.querySelector('.feedback');feedback.className=`feedback ${result.correct?'correct':'incorrect'}`;feedback.textContent=`${result.correct?'Correct.':'Revisit your reasoning.'} ${result.explanation}`;} catch(error){notify(error.message);} finally {button.disabled=false;}
      });
      if(['brief','build'].includes(stage.id)) window.ArcadeLauncher.mount(panel.querySelector('#launcher-panel'),lab.id,{esc,icon,copyText});
      if(['verify','cleanup'].includes(stage.id)) window.ArcadeVerification.mount(panel.querySelector('#verification-panel'),lab.id,stage.id,{esc,icon,record,updateRecord,notify,copyText});
      panel.querySelector('#export-debrief')?.addEventListener('click',exportDebrief);
      renderCoach(stage);
    }
    function renderCoach(stage) {
      const target=panel.querySelector('#coach-body');
      if(coachTab==='evidence') {
        target.innerHTML=`<div class="hint-intro"><h3>Leave a useful trail.</h3><p>Save observations before conclusions. This stays in your browser; export a backup to keep it.</p></div><div class="evidence-fields">${P.evidenceFields.map(field=>`<label for="evidence-${field}">${fields[field]}</label><textarea id="evidence-${field}" data-evidence="${field}" rows="3" maxlength="50000" placeholder="${field==='hypothesis'?'What could explain this? What would disprove it?':'Capture the command, result, and what it establishes.'}">${esc(state.evidence[field])}</textarea>`).join('')}</div><p class="field-note">Avoid credentials and secrets. Updates save as you type.</p><button class="button secondary small" id="export-evidence">${icon('download')} Export debrief</button>`;
        target.querySelectorAll('[data-evidence]').forEach(input=>input.oninput=()=>persist({...state,evidence:{...state.evidence,[input.dataset.evidence]:input.value}}));
        target.querySelector('#export-evidence').onclick=exportDebrief;return;
      }
      const hintStage=stage.hintCount?stage:lesson.stages.find(item=>item.id==='investigate'), count=Math.min(state.hintCounts[hintStage.id],hintStage.hintCount);
      target.innerHTML=`<div class="hint-intro"><span class="eyebrow">${state.mode==='interview'?'INTERVIEW MODE':'PROGRESSIVE COACHING'}</span><h3>One nudge at a time.</h3><p>${state.mode==='interview'?'Talk through your hypothesis first. Hints are available when you decide to use them.':'Observe the symptom, choose a layer, then test one explanation.'}</p></div><div class="hint-counter">${count} / ${hintStage.hintCount} investigation hints revealed</div><div class="hint-levels">${Array.from({length:count},(_,i)=>{const hint=hintBodies.get(`${hintStage.id}:${i+1}`);return `<article class="hint-card"><span class="hint-label">HINT ${i+1}</span><h4>${esc(hint?.title||'Saved hint unavailable')}</h4><p>${esc(hint?.body||'Retry loading this previously revealed hint.')}</p></article>`;}).join('')}</div><button class="button secondary" id="next-hint" ${count>=hintStage.hintCount||busy?'disabled':''}>${count>=hintStage.hintCount?'All hints revealed':count?'Reveal next hint':'Reveal first hint'}</button>${Array.from({length:count},(_,i)=>hintBodies.has(`${hintStage.id}:${i+1}`)).every(Boolean)?'':'<button class="button ghost small" id="retry-hints">Retry saved hints</button>'}<p class="field-note">Hints guide diagnosis. <a href="${C.labRoute(lab.id,'answers')}">Open reference solution</a> when you are ready to compare.</p><div class="session-reminder"><strong>Session cost</strong><p>${esc(lab.cost)}</p><a href="#/guide/cost-and-cleanup">Cleanup & cost guide</a></div>`;
      target.querySelector('#retry-hints')?.addEventListener('click',async event=>{const generation=attempt;event.currentTarget.disabled=true;await restoreHints(generation);if(currentAttempt(generation)&&coachTab==='coach')renderCoach(lesson.stages.find(item=>item.id===state.stage));});
      target.querySelector('#next-hint').onclick=async()=>{
        if(busy||count>=hintStage.hintCount)return;
        const generation=attempt;busy=true;renderCoach(stage);
        try {
          const hint=await request('hint',{id:lab.id,stage:hintStage.id,level:count+1});
          if(!currentAttempt(generation))return;
          hintBodies.set(`${hintStage.id}:${count+1}`,hint);
          persist({...state,hintCounts:{...state.hintCounts,[hintStage.id]:count+1}});
        } catch(error) {
          if(currentAttempt(generation))notify(error.message);
        } finally {
          if(currentAttempt(generation)) {
            busy=false;
            if(coachTab==='coach')renderCoach(lesson.stages.find(item=>item.id===state.stage));
          }
        }
      };
    }
    function exportDebrief() {
      const reports=(record(lab.id).receipts||[]).map(report=>`### ${report.phase} — ${report.generatedAt}\n\nCluster: ${report.environment.cluster} (${report.environment.region})\n${report.checks.map(check=>`- ${check.status.toUpperCase()} ${check.label}: ${check.observed}`).join('\n')}\n\nLimits: ${report.scope}\n`).join('\n');
      const text=`# ${lab.title} — interview debrief\n\nMission: ${lesson.objective}\nPractice time: ${P.formatTime(P.elapsed(state))}\nHints used: ${Object.values(state.hintCounts).reduce((a,b)=>a+b,0)}\n\n${P.evidenceFields.map(field=>`## ${fields[field]}\n\n${state.evidence[field]||'(not recorded)'}\n`).join('\n')}\n## Freeform notes\n\n${record(lab.id).notes||'(not recorded)'}\n\n## Imported CLI observations\n\n${reports||'(none imported)'}\n\n## Discussion prompts\n\n${lesson.debriefPrompts.map(prompt=>`- ${prompt}`).join('\n')}\n\nChecklist progress is self-reported. Imported CLI receipts are point-in-time observations, not signed attestations or complete cloud validation.\n`;
      const url=URL.createObjectURL(new Blob([text],{type:'text/markdown'})), link=document.createElement('a');link.href=url;link.download=`${lab.id.replaceAll('/','-')}-debrief.md`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('Interview debrief exported.');
    }
    // Restore only hints previously requested by this learner; never prefetch new levels.
    async function restoreHints(generation=attempt) {
      await Promise.all(lesson.stages.flatMap(stage=>Array.from({length:Math.min(stage.hintCount,state.hintCounts[stage.id])},(_,i)=>
        request('hint',{id:lab.id,stage:stage.id,level:i+1})
          .then(hint=>{if(currentAttempt(generation))hintBodies.set(`${stage.id}:${i+1}`,hint);})
          .catch(()=>{})
      )));
    }
    await restoreHints();
    render();
    const interval=setInterval(()=>{if(!alive()){clearInterval(interval);return;}const clock=panel.querySelector('#practice-clock');if(clock)clock.textContent=P.formatTime(P.elapsed(state));},1000);
    return ()=>{disposed=true;clearInterval(interval);};
  }
  window.ArcadePractice={mount};
})();
