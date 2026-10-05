/* A terminal handoff only. The browser never starts a process or contacts AWS. */
(() => {
  'use strict';
  const L=window.ArcadeLauncherCore, C=window.ArcadeCore;
  const recipes=new Map(), selections=new Map();
  async function load(id) {
    if(!recipes.has(id)) {
      const pending=fetch(`/api/launch?${new URLSearchParams({id})}`).then(async response=>{
        if(!response.ok)throw new Error(response.status===404?'This server does not have a launch recipe for this mission yet. Restart the updated arcade server, or continue with the complete runbook.':'The launch recipe could not be loaded. Check the local server and retry.');
        return L.validate(await response.json(),id);
      }).catch(error=>{recipes.delete(id);throw error;});
      recipes.set(id,pending);
    }
    return recipes.get(id);
  }
  async function mount(target,labId,context) {
    const {esc,icon,copyText}=context;
    target.innerHTML='<div class="launch-loading" role="status">Loading the terminal launch recipe…</div>';
    try {
      const recipe=await load(labId);
      if(!target.isConnected)return;
      let mode=selections.get(labId)||L.defaultMode(recipe);
      const prerequisites=()=>recipe.environmentPrerequisites.length?`<div class="launch-prerequisites"><span>Prepare first</span>${recipe.environmentPrerequisites.map(id=>`<a href="${C.labRoute(id)}">Lab ${esc(id.slice(0,2))} ${icon('arrow')}</a>`).join('')}</div>`:'';
      function render() {
        if(!target.isConnected)return;
        const runbook=recipe.kind==='runbook', command=L.commands(recipe,mode);
        target.innerHTML=`<section class="mission-launcher" aria-label="Launch this lab"><div class="launch-heading"><span class="launch-icon" aria-hidden="true">${icon('terminal')}</span><div><span class="eyebrow">${runbook?'PLAN THE NEXT BUILD':'FROM BRIEF TO TERMINAL'}</span><h3>${runbook?'Use the mission runbook.':'Prepare your lab workspace.'}</h3></div><span class="launch-tag">${runbook?'Runbook':'Local preparation'}</span></div>
        <p class="launch-intro">${runbook?'This mission coordinates earlier labs and has no separate starter directory. Follow its runbook after preparing the prerequisites.':'Choose your starting point, then paste the commands into Bash. The launcher prepares exercise files and prints the next steps; AWS changes happen only when you run those steps.'}</p>
        ${prerequisites()}
        ${runbook?'':`<fieldset class="launch-modes"><legend>Starting point</legend>${Object.entries(recipe.modes).map(([key,value])=>`<label class="launch-mode ${key===mode?'is-selected':''}"><input type="radio" name="launch-mode-${recipe.alias}" value="${key}" ${key===mode?'checked':''}><span><strong>${esc(value.label)}</strong><small>${esc(value.description)}</small></span></label>`).join('')}</fieldset>
        <div class="code-frame launch-command"><div class="code-toolbar"><span>Bash · run from any directory</span><button class="copy-button" data-launch-copy>${icon('copy')} Copy launch commands</button></div><pre class="code-content" tabindex="0" aria-label="Lab preparation commands"><code>${esc(command)}</code></pre></div>
        <div class="launch-preservation"><strong>Already started?</strong><p>Run the same command to resume. Your edits and Terraform state stay in place. The launcher refuses to switch modes or replace an existing unregistered directory.</p></div>`}
        <div class="launch-cost"><span>SESSION COST</span><p>${esc(recipe.cost)}</p></div>
        <div class="launch-links"><a class="inline-link" href="#/guide/lab-launcher">Launcher guide ${icon('arrow')}</a><a class="inline-link" href="${C.labRoute(labId,'brief')}">Complete runbook ${icon('arrow')}</a></div>
        ${runbook?'':`<details class="launch-status"><summary>When you return: inspect status and clean up</summary><p>Run <code>arcade status</code> to inspect local workspaces. It cannot certify what remains in AWS. Run <code>arcade next ${recipe.alias}</code> for this lab’s commands, including cleanup, and confirm deletion with its runbook before ending the session.</p><button class="button secondary small" data-status-copy>${icon('copy')} Copy status command</button></details><p class="field-note launch-footnote">The browser does not run these commands or read your AWS credentials. If <code>arcade</code> is unavailable, follow <a href="#/guide/setup">tool and PATH setup</a> first.</p>`}</section>`;
        target.querySelectorAll('.launch-mode input').forEach(input=>input.onchange=()=>{mode=input.value;selections.set(labId,mode);render();target.querySelector(`.launch-mode input[value="${mode}"]`)?.focus();});
        target.querySelector('[data-launch-copy]')?.addEventListener('click',event=>copyText(command,event.currentTarget));
        target.querySelector('[data-status-copy]')?.addEventListener('click',event=>copyText('arcade status',event.currentTarget));
      }
      render();
    } catch(error) {
      if(!target.isConnected)return;
      target.innerHTML=`<section class="launch-unavailable" aria-label="Launch recipe unavailable"><strong>Continue with the runbook.</strong><p>${esc(error.message)}</p><div class="launch-links"><button class="button secondary small" data-launch-retry>Retry launch recipe</button><a class="inline-link" href="#/guide/lab-launcher">Launcher guide ${icon('arrow')}</a><a class="inline-link" href="${C.labRoute(labId,'brief')}">Complete runbook ${icon('arrow')}</a></div></section>`;
      target.querySelector('[data-launch-retry]').onclick=()=>mount(target,labId,context);
    }
  }
  window.ArcadeLauncher={mount};
})();
