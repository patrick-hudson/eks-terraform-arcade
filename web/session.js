/* Two clients, one local session: the API returns the same projection as the TUI. */
(() => {
  'use strict';
  const labels={prepare:'Prepare workspace',configure:'Save environment',plan:'Plan changes',plan_destroy:'Plan cleanup',apply:'Apply reviewed plan',submit:'Submit repair',verify:'Check evidence',begin_incident:'Prepare broken update'};
  const money=value=>Number(value||0)===0?'$0':`$${Number(value).toFixed(2)}`;
  const words=value=>String(value||'').replaceAll('_',' ');
  function render(data,esc){
    const s=data.session,c=s.costs||{},p=s.plan,job=data.job,busy=data.activeJob?.status==='running';
    const operationLabel=op=>op==='prepare'&&s.prepared?'Resume workspace':op==='verify'&&s.alias==='11-10'?(s.phase==='baseline'?'Verify healthy baseline':'Inspect live evidence'):labels[op];
    const button=(op,primary=false)=>`<button class="button ${primary?'primary':'secondary'}" data-operation="${op}" ${busy||(!s.prepared&&op!=='prepare')||(op==='begin_incident'&&s.phase!=='baseline')?'disabled':''}>${operationLabel(op)}</button>`;
    const runbook=(items,title)=>items?.length?`<details class="session-runbook"><summary>${title}</summary>${items.map(step=>`<h4>${esc(step.title||'Step')}</h4>${step.description?`<p>${esc(step.description)}</p>`:''}<pre tabindex="0"><code>${esc(step.command||'')}</code></pre>`).join('')}</details>`:'';
    const prerequisites=(s.prerequisites||[]).map(item=>`<li>${item.recipeId===s.id&&item.root?`<button class="button ghost small" data-prerequisite-root="${esc(item.root)}">Open ${esc(item.root)} prerequisite</button>`:`<a href="${window.ArcadeCore.labRoute(item.recipeId,'session')}">${esc(item.title||'Lab '+item.alias)}</a>`}<span>${esc(item.status)}</span></li>`).join('');
    const configuration=s.configuration||{};
    const allFields=[['profile','AWS profile','default'],['account_id','AWS account ID','12-digit sandbox account'],['region','Region','us-west-2'],['lab_id','Unique resource prefix','arcade-yourname'],['admin_principal_arn','EKS administrator ARN (foundation only)','arn:aws:iam::…'],['allowed_cidr','Your public IP /32 (foundation only)','203.0.113.10/32']];
    const inherited=['08','09','10','13'].includes(s.alias)||s.alias.startsWith('11-');
    const fields=allFields.filter(([key])=>key==='admin_principal_arn'?s.alias==='07':key==='allowed_cidr'?s.alias==='07'||(s.alias==='13'&&s.root==='access'):key==='lab_id'?!inherited:true).map(field=>field[0]==='allowed_cidr'?[field[0],'Your public IPv4 /32',field[2]]:field);
    return `<section class="cloud-session" aria-label="Environment session"><div class="session-heading"><div><p class="eyebrow">${s.alias==='00'?'LOCAL TERRAFORM':'AWS PRACTICE SESSION'} · GAME ${esc(s.alias)}${s.roots.length>1?' / '+esc(s.root):''}</p><h2>Build. Diagnose. Prove it.</h2><p>Keep repairs in Terraform. Review each plan, check the result, then clean up.</p></div><span class="session-state">${esc(words(s.status))}</span></div>
      <div class="session-summary"><div><span>Next step</span><strong>${esc(words(s.nextAction))}</strong></div><div><span>Estimated 1 hour</span><strong>${money(c.oneHourUsd)}</strong></div><div><span>Estimated 2 hours</span><strong>${money(c.twoHoursUsd)}</strong></div></div>
      <details class="session-assumptions"><summary>What this estimate includes</summary><p>${esc(c.description||'')}</p><ul>${(c.assumptions||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul><p>${esc(c.activityBased||'')} ${esc(c.notice||'Estimate, not a billing cap.')}</p><small>${esc(c.region||'Local')} · Pricing assumptions ${esc(c.asOf||'')}</small></details>
      ${prerequisites?`<div class="session-prerequisites"><h3>Prepare these first</h3><ul>${prerequisites}</ul></div>`:''}
      ${(s.roots||[]).length>1?'<p class="session-root-help">Each root is a directory with its own Terraform state. Follow the setup order above, then clean up in reverse order.</p>':''}<div class="session-toolbar">${(s.roots||[]).length>1?`<label>Terraform root <select data-session-root ${busy?'disabled':''}>${s.roots.map(root=>`<option ${root===s.root?'selected':''} value="${esc(root)}">${esc(root==='.'?'Infrastructure':root)}</option>`).join('')}</select></label>`:''}<button class="button ghost small" data-session-refresh>Refresh status</button><span>${esc(s.path||'This mission follows the complete runbook.')}</span></div>
      ${!data.runnerEnabled?`<div class="session-enable"><h3>Enable the local runner</h3><p>Restart the app with <code>./arcade serve --runner</code> to use these controls. It runs tools on this computer using your named AWS profile.</p><p>Or use <code>./arcade tui</code> in your terminal. Both use the same registered workspaces and saved plans.</p></div>`:''}
      ${data.runnerEnabled?`<div class="session-actions">${(s.capabilities||[]).includes('prepare')?`<label>Starting point <select data-session-mode ${s.prepared||busy?'disabled':''}>${(s.modes||[]).map(mode=>`<option value="${esc(mode)}" ${mode===s.mode?'selected':''}>${esc(words(mode))}</option>`).join('')}</select></label>${button('prepare')}`:''}${(s.capabilities||[]).filter(x=>['plan','submit','plan_destroy','begin_incident'].includes(x)||(x==='verify'&&s.alias==='11-10')).map(op=>button(op,op==='submit')).join('')}</div>`:''}
      ${s.alias==='11-10'?`<p class="session-root-help">${s.phase==='incident'?'The broken update is prepared. Plan and apply it in this same workspace, then diagnose and repair it through Terraform. Inspect live evidence shows current pods; complete the runbook HTTP checks before calling the repair complete.':'This incident starts with a working application. Apply the healthy baseline, verify its HTTP response, then prepare the broken update. Preparing it changes the input file only; review and apply a fresh plan to deploy the fault.'}</p>`:''}
      ${data.runnerEnabled&&s.supported&&s.alias!=='00'?`<details class="session-config" ${s.nextAction==='configure'?'open':''}><summary>Account & environment</summary><p>Use a named AWS CLI profile already authenticated on this computer. Never paste access keys here.</p><form data-configuration-form><div class="session-fields">${fields.map(([key,label,placeholder])=>`<label>${label}<input name="${key}" value="${esc(configuration[key]|| (key==='region'?'us-west-2':key==='profile'?'default':''))}" placeholder="${esc(placeholder)}" ${['profile','account_id','region','lab_id'].includes(key)?'required':''} autocomplete="off"></label>`).join('')}</div><button class="button secondary" ${busy||!s.prepared?'disabled':''}>Save environment</button></form></details>`:''}
      ${!s.supported?`<div class="session-enable"><h3>Follow the ordered runbook</h3><p>This mission includes deliberate state or multi-lab steps. The commands below remain part of the exercise; they are not run automatically.</p></div>`:''}
      ${p?`<section class="session-plan"><div class="section-heading"><h3>${p.operation==='destroy'?'Cleanup plan':'Saved plan'}</h3><span>${p.consumed?'Already applied':p.stale?'Needs a new plan':'Ready for review'}</span></div><p>${esc(p.scope||'Review the metadata below; values remain private in your workspace.')}</p><pre tabindex="0">${esc(p.reviewText||'')}</pre>${p.stale&&!p.consumed?'<p class="session-warning">Source, inputs or state changed. Create a fresh plan before applying.</p>':''}${data.runnerEnabled&&!p.stale&&!p.consumed?`<form data-approval-form><label>To approve this ${p.operation==='destroy'?'deletion':'change'}, type <strong>${esc(p.approval)}</strong><input name="approval" autocomplete="off" required placeholder="${esc(p.approval)}"></label><button class="button ${p.operation==='destroy'?'danger':'primary'}" ${busy?'disabled':''}>${p.operation==='destroy'?'Delete planned resources':'Apply reviewed plan'}</button></form>`:''}</section>`:''}
      ${job?`<section class="session-job" role="status" aria-live="polite"><div class="section-heading"><h3>${esc(labels[job.operation]||words(job.operation))}</h3><span>${esc(job.status)}</span></div>${job.error?`<p class="session-warning">${esc(job.error)}</p>`:''}<ol>${(job.events||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ol><small>${job.status==='running'?'You can leave this page. The operation keeps running; return here for its result.':'State and resource identifiers are retained in the workspace.'}</small></section>`:''}
      ${busy&&data.activeJob?.lab!==s.id?'<p class="session-warning">Another mission has an operation running. Wait for it to finish before starting this one.</p>':''}
      ${s.repair?`<section class="session-repair"><div class="section-heading"><h3>Repair evidence</h3><span class="session-evidence-state ${esc(s.repair.status)}">${s.repair.status==='pass'?'Checks passed':s.repair.status==='fail'?'Repair needed':'Incomplete'}${s.repair.stale?' · Needs a new check':''}</span></div><p>${esc(s.repair.scope)}</p>${(s.repair.checks||[]).map(check=>`<details><summary><span>${esc(check.status)}</span> ${esc(check.label)}</summary><p><strong>Expected:</strong> ${esc(check.expected)}</p><p><strong>Observed:</strong> ${esc(check.observed)}</p></details>`).join('')}<small>${esc(s.repair.generatedAt||'')} · Separate from your study completion checkbox.</small></section>`:'<p class="session-evidence-empty">No repair check yet. A successful apply alone does not pass this exercise.</p>'}
      <details class="session-inventory"><summary>Resource inventory · ${(s.inventory?.resources||[]).length} observed</summary><p>${esc(s.inventory?.scope||'Identifiers only. Empty Terraform state does not prove cloud absence.')}</p>${(s.inventory?.resources||[]).map(item=>`<div><strong>${esc(item.address)}</strong><code>${esc(item.arn||item.id||'No identifier recorded')}</code></div>`).join('')}<p>Cloud absence: <strong>${esc(s.inventory?.absence||'unknown')}</strong></p></details>
      <div class="session-cleanup"><h3>Before you leave</h3><p>Plan cleanup, review the deletion, then apply it. Delete dependent workloads before their shared infrastructure.</p><ol>${(s.cleanupOrder||[]).map(item=>`<li>Lab ${esc(item.lab)} · ${esc(item.root==='.'?'infrastructure':item.root)}</li>`).join('')}</ol><a class="inline-link" href="${window.ArcadeCore.labRoute(s.id,'brief')}">Open full mission and absence checks →</a></div>
      ${runbook(s.runbookSteps,'Complete setup & exercise commands')}${runbook(s.runbookCleanup,'Complete cleanup commands')}
    </section>`;
  }
  async function mount(target,lab,context){
    const {esc,notify}=context;let disposed=false,timer=null,data=null,root=null,inFlight=false,refreshing=false,requestVersion=0;
    const current=()=>!disposed&&target.isConnected&&(!context.isCurrent||context.isCurrent());
    async function request(path,options){const response=await fetch(path,options);const body=await response.json();if(!response.ok)throw new Error(body.error||'Session request failed.');return body;}
    async function refresh(){
      if(!current())return;
      const version=++requestVersion;
      refreshing=true;
      target.querySelectorAll('button').forEach(button=>button.disabled=true);
      const refreshButton=target.querySelector('[data-session-refresh]');if(refreshButton)refreshButton.textContent='Refreshing…';
      try{
        const params=new URLSearchParams({id:lab.id});if(root!==null)params.set('root',root);
        const result=await request('/api/session?'+params);
        if(!current()||version!==requestVersion)return;refreshing=false;data=result;draw();
        clearTimeout(timer);if(data.activeJob?.status==='running')timer=setTimeout(refresh,1500);
      }catch(error){if(current()&&version===requestVersion){target.innerHTML=`<section class="session-enable"><h2>Session status unavailable</h2><p>${esc(error.message)}</p><p>Keep any existing state. Use <code>./arcade tui</code> or the mission runbook.</p><button class="button secondary" data-retry>Retry</button></section>`;target.querySelector('[data-retry]').onclick=refresh;}}
    }
    async function perform(operation,parameters={}){
      if(inFlight||refreshing||!data?.runnerEnabled)return;inFlight=true;
      target.querySelectorAll('button').forEach(x=>x.disabled=true);
      try{
        await request('/api/session/operation',{method:'POST',headers:{'Content-Type':'application/json','X-Arcade-Token':data.token},body:JSON.stringify({lab:lab.id,root:data.session.root,operation,parameters})});
        if(current())await refresh();
      }catch(error){if(current()){notify(error.message);draw();}}finally{inFlight=false;}
    }
    function draw(){
      if(!current())return;target.innerHTML=render(data,esc);
      target.querySelector('[data-session-refresh]').onclick=refresh;
      const rootControl=target.querySelector('[data-session-root]');if(rootControl)rootControl.onchange=()=>{root=rootControl.value;refresh();};
      target.querySelectorAll('[data-prerequisite-root]').forEach(button=>button.onclick=()=>{root=button.dataset.prerequisiteRoot;refresh();});
      target.querySelectorAll('[data-operation]').forEach(button=>button.onclick=()=>perform(button.dataset.operation,button.dataset.operation==='prepare'?{mode:target.querySelector('[data-session-mode]').value}:{}));
      const config=target.querySelector('[data-configuration-form]');if(config)config.onsubmit=event=>{event.preventDefault();const params={};for(const [key,value] of new FormData(config)){if(value.trim())params[key]=value.trim();}perform('configure',params);};
      const approval=target.querySelector('[data-approval-form]');if(approval)approval.onsubmit=event=>{event.preventDefault();const phrase=new FormData(approval).get('approval');if(phrase!==data.session.plan.approval){notify('Type the exact approval shown above.');return;}perform('apply',{approval:phrase,plan_digest:data.session.plan.digest});};
    }
    target.innerHTML='<div class="loading-state" role="status">Reading your environment session…</div>';
    await refresh();
    return ()=>{disposed=true;clearTimeout(timer);};
  }
  window.ArcadeSession={mount,render};
})();
