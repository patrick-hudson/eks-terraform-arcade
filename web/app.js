/* The browser reads authored lessons. Commands are displayed and copied, never run. */
(() => {
  'use strict';
  const C = window.ArcadeCore;
  const P = window.ArcadePracticeCore;
  const KEY = 'aws-interview-arcade:v1';
  const $ = selector => document.querySelector(selector);
  const esc = text => String(text ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const icons = {
    grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    terminal:'<path d="m4 6 6 6-6 6m9 0h7"/>',
    bolt:'<path d="m13 2-9 12h7l-1 8 10-12h-7z"/>',
    book:'<path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1zm0 0v15"/>',
    arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
    back:'<path d="M20 12H4m6-6-6 6 6 6"/>',
    search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    check:'<path d="m5 12 4 4L19 6"/>',
    clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    layers:'<path d="m12 3 10 5-10 5L2 8zm-9 10 9 5 9-5M3 18l9 5 9-5"/>',
    cloud:'<path d="M6 18a5 5 0 0 1-1-10 7 7 0 0 1 13-1 5.5 5.5 0 0 1 0 11z"/>',
    cube:'<path d="m12 2 9 5v10l-9 5-9-5V7zm0 10 9-5M12 12 3 7m9 5v10"/>',
    flag:'<path d="M5 22V3c5-4 9 4 14 0v10c-5 4-9-4-14 0"/>',
    file:'<path d="M14 2H5v20h14V7zm0 0v5h5M8 12h8m-8 4h6"/>',
    lock:'<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v2"/>',
    copy:'<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
    shield:'<path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6zm-4 10 3 3 5-6"/>'
  };
  const icon = name => `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.file}</svg>`;
  const trackIcon = track => ({Terraform:'layers',AWS:'cloud',Kubernetes:'cube',Capstone:'flag'}[track] || 'terminal');
  let practiceCleanup = () => {}, toolchain = null;
  let catalog, exercises = [], route, renderVersion = 0, query = '', track = 'All';
  let progress = C.readProgress(null), storageAvailable = true;
  const revealed = new Set();
  const cache = new Map();
  let toastTimer;

  function notify(message) {
    $('#toast').textContent = message;
    $('#toast').classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 3200);
  }
  function storageWarning(message) {
    $('#storage-warning').hidden = false;
    $('#storage-warning').textContent = message;
  }
  function loadProgress() {
    try {
      const raw = localStorage.getItem(KEY);
      progress = C.readProgress(raw);
      if (raw) {
        try {
          const parsed = JSON.parse(raw);
          if (![1,2,3].includes(parsed?.schemaVersion) || !parsed?.labs || Array.isArray(parsed.labs) || typeof parsed.labs !== 'object') throw new Error('Invalid state');
        } catch { storageWarning('Saved progress could not be read. The labs still work; new changes will start a fresh record.'); }
      }
    } catch {
      storageAvailable = false;
      storageWarning('Browser storage is unavailable. Notes and progress will last for this page session only. Export them before closing.');
    }
  }
  function saveProgress() {
    try {
      progress=C.mergeStored(progress,C.readProgress(localStorage.getItem(KEY)));
      localStorage.setItem(KEY, JSON.stringify(progress));
      storageAvailable = true;
    } catch {
      storageAvailable = false;
      storageWarning('Changes could not be saved in this browser. Export your progress before closing this page.');
    }
  }
  const record = id => progress.labs[id] || C.blankRecord();
  function updateRecord(id, changes) {
    const previousStatus=record(id).status;
    progress.labs[id] = { ...record(id), ...changes, updatedAt: new Date().toISOString() };
    progress.lastLab = id;
    saveProgress();
    if(catalog && previousStatus!==record(id).status) renderSidebar();
  }
  async function getFile(path) {
    if (cache.has(path)) return cache.get(path);
    const response = await fetch(`/api/file?path=${encodeURIComponent(path)}`);
    if (!response.ok) throw new Error('The source file could not be loaded. Check the local server and try again.');
    const data = await response.json();
    cache.set(path, data);
    return data;
  }
  const doneCount = () => catalog.labs.filter(lab => record(lab.id).status === 'done').length;
  function navLink(href, name, glyph, selected, extra = '') {
    return `<a class="nav-link ${selected ? 'active' : ''}" href="${esc(href)}" ${selected ? 'aria-current="page"' : ''}><span class="nav-icon">${icon(glyph)}</span>${esc(name)}${extra}</a>`;
  }
  function renderSidebar() {
    const completed = doneCount();
    const guidePath = id => `#/guide/${encodeURIComponent(id)}`;
    const guideIcon = id => /cost|cleanup/i.test(id) ? 'shield' : 'book';
    const guideLabels = {'setup':'Setup & tools','tui':'Terminal workspace','offline-practice':'Offline practice','plan-review':'Review a Terraform plan','cost-and-cleanup':'Cost & cleanup','interview-scorecard':'Interview scorecard','VALIDATION':'What was verified','overview':'Course overview','web-ui':'Using this workspace','toolchain':'Current toolchain','learning-design':'How practice works','aws-testing':'Connect AWS for testing','lab-launcher':'Launch and resume labs', 'live-verification':'Check real lab results', 'glossary':'Plain-English glossary'};
    const guideOrder = Object.keys(guideLabels);
    const guideRank=id=>guideOrder.includes(id)?guideOrder.indexOf(id):guideOrder.length;
    const guides = [...catalog.docs].sort((a,b) => guideRank(a.id) - guideRank(b.id));
    $('#sidebar').innerHTML = `<a class="brand" href="#/"><span class="brand-mark">${icon('terminal')}</span><span><span class="brand-name">AWS ARCADE</span><span class="brand-subtitle">INTERVIEW PRACTICE</span></span></a>
      <div class="nav-section-label">YOUR WORKSPACE</div><nav aria-label="Main navigation">
      ${navLink('#/', 'Lab directory', 'grid', route.kind === 'home', `<span class="nav-count">${catalog.labs.length}</span>`)}
      ${navLink('#/practice', 'Practice desk', 'search', ['practice','drill'].includes(route.kind), '<span class="nav-count">7</span>')}
      ${navLink('#/incidents', 'Incident gauntlet', 'bolt', route.kind === 'incidents' || route.id?.includes('/scenario-'), `<span class="nav-count">${catalog.labs.reduce((sum, lab) => sum + lab.scenarios.length, 0)}</span>`)}
      </nav><div class="nav-section-label">FIELD GUIDES</div><nav aria-label="Field guides">${guides.map(doc => navLink(guidePath(doc.id), guideLabels[doc.id] || doc.title, guideIcon(doc.id), route.kind === 'guide' && route.id === doc.id)).join('')}</nav>
      <div class="sidebar-footer"><div class="progress-caption"><span>YOUR PROGRESS</span><strong>${completed} / ${catalog.labs.length}</strong></div><progress class="progress-track" value="${completed}" max="${catalog.labs.length}" aria-label="Labs complete">${completed} of ${catalog.labs.length}</progress><p>Build. Diagnose. Explain.<br>Always leave a clean account.</p><button class="button ghost small" id="export-progress">${icon('download')} Export progress</button><label class="button ghost small progress-import">Restore backup<input id="import-progress" class="visually-hidden" type="file" accept="application/json,.json" aria-label="Restore progress backup"></label><span class="sidebar-local">Saved in this browser</span></div>`;
    $('#export-progress').addEventListener('click', exportProgress);
    $('#import-progress').addEventListener('change', importProgress);
    $('#sidebar').querySelectorAll('a').forEach(a => a.addEventListener('click', () => closeMenu(false)));
  }
  function exportProgress() {
    const blob = new Blob([JSON.stringify(C.snapshotProgress(progress), null, 2)], {type:'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url; link.download = `aws-arcade-progress-${new Date().toISOString().slice(0,10)}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify('Progress and notes exported.');
  }
  async function importProgress(event) {
    const file=event.target.files[0]; if(!file) return;
    try {
      if(file.size>20971520) throw new Error('Choose a progress backup smaller than 20 MB.');
      const raw=await file.text();
      const preview=C.mergeProgress(progress,raw,exercises.map(lab=>lab.id));
      closeMenu();
      const dialog=document.createElement('dialog'); dialog.className='backup-dialog';
      dialog.innerHTML=`<h2>Restore your practice</h2><p>${preview.imported} mission records and ${preview.drillAttempts} completed drill attempts are in this backup. ${preview.skipped} older or unknown mission records will be skipped. Newer browser notes are kept, and duplicate drill attempts are merged.</p><p>Imported practice clocks will be paused. This does not change running AWS resources.</p><div class="hero-actions"><button class="button primary" id="confirm-import">Merge backup</button><button class="button secondary" id="cancel-import">Cancel</button></div>`;
      document.body.append(dialog);dialog.showModal();
      dialog.addEventListener('close',()=>dialog.remove());
      dialog.querySelector('#cancel-import').onclick=()=>dialog.close();
      dialog.querySelector('#confirm-import').onclick=()=>{
        const result=C.mergeProgress(progress,raw,exercises.map(lab=>lab.id));progress=result.progress;saveProgress();dialog.close();renderRoute();notify('Backup merged, including drill attempts.');
      };
    } catch(error) {notify(error.message);}
    event.target.value='';
  }
  function statusBadge(id) {
    const status = record(id).status;
    return `<span class="card-status ${status === 'done' ? 'done' : status === 'active' ? 'active-status' : ''}">${status === 'done' ? `${icon('check')} Complete` : status === 'active' ? 'In progress' : 'Not started'}</span>`;
  }
  function labCard(lab, incident = false) {
    return `<a class="lab-card" data-track="${esc(lab.track)}" href="${esc(C.labRoute(lab.id))}"><div class="card-top"><span class="card-icon">${icon(incident ? 'bolt' : trackIcon(lab.track))}</span><span class="lab-number">${incident ? 'INCIDENT' : 'LAB'} ${esc(lab.number)}</span></div><div class="card-tags"><span class="track-pill" data-track="${esc(lab.track)}">${esc(incident ? 'Break / fix' : lab.track)}</span><span class="tag">${esc(lab.mode)}</span></div><h3 class="card-title">${esc(lab.title)}</h3><p class="card-description">${esc(lab.summary)}</p><div class="card-footer"><span>${icon('clock')} ${esc(lab.duration)}</span><span class="card-arrow">${icon('arrow')}</span></div>${statusBadge(lab.id)}</a>`;
  }
  function renderHome() {
    $('#topbar-title').textContent = 'Workspace / Lab directory';
    const next = exercises.find(l => l.id === progress.lastLab && record(l.id).status !== 'done') || catalog.labs.find(l => record(l.id).status !== 'done') || catalog.labs[0];
    const active = exercises.filter(l => record(l.id).status === 'active');
    const pendingCleanup = exercises.filter(l => record(l.id).status !== 'new' && !record(l.id).checks.cleanup).length;
    const paths=[
      {name:'Terraform & AWS foundations',range:[0,6],glyph:'layers',description:'Stable state, private services, IAM boundaries and recoverable changes.'},
      {name:'Build the EKS platform',range:[7,10],glyph:'cube',description:'A lean cluster, workload health, Pod Identity and persistent storage.'},
      {name:'On-call & public access',range:[11,13],glyph:'bolt',description:`${catalog.labs.reduce((sum, lab) => sum + lab.scenarios.length, 0)} blind incidents, a capstone, and a real internet path to open and close.`}
    ];
    const terraform=toolchain?.components.find(item=>item.name.toLowerCase()==='terraform')?.version;
    $('#main').innerHTML = `<section class="launchpad"><div><div class="eyebrow"><span class="status-dot"></span> TERRAFORM + EKS · MID–SENIOR</div><h1>Build the system.<br><span>Earn the explanation.</span></h1><p>Work a mission from first failure to proven fix. Keep the evidence, defend the tradeoffs, and close every session with teardown.</p><div class="hero-actions"><a class="button primary" href="#/practice">Practice without AWS ${icon('arrow')}</a><a class="button secondary" href="#/incidents">${icon('bolt')} Pick a blind incident</a><a class="inline-link" href="${guideLink('setup')}">Set up your tools ${icon('arrow')}</a></div></div><div class="resume-panel"><div class="eyebrow">${active.length?'PICK UP WHERE YOU LEFT OFF':'YOUR NEXT MISSION'}</div><h2>${esc(next.title)}</h2><p>${esc(next.summary)}</p><div class="path-meta"><span>LAB ${esc(next.number)} · ${esc(next.duration)}</span><span>${P.normalize(record(next.id).practice).completed.length} / 5 stages</span></div><a class="button primary" href="${esc(C.labRoute(next.id))}">${active.length?'Resume mission':'Enter mission'} ${icon('arrow')}</a><progress class="progress-track" value="${P.normalize(record(next.id).practice).completed.length}" max="5" aria-label="Next mission stages recorded"></progress></div></section>
      <section class="practice-strip" aria-label="Practice overview"><div class="practice-stat"><span>LABS COMPLETE</span><div class="practice-stat-value">${doneCount()} <small>of ${catalog.labs.length}</small></div><p>Plus ${catalog.labs.reduce((sum, lab) => sum + lab.scenarios.length, 0)} isolated incidents</p></div><div class="practice-stat"><span>PRACTICE ALLOWANCE</span><div class="practice-stat-value">$20 <small>total</small></div><a href="${guideLink('cost')}">Plan cost & teardown</a></div><div class="practice-stat"><span>CLEANUP CHECKLIST</span><div class="practice-stat-value">${pendingCleanup?`${pendingCleanup} pending`:'No pending'}</div><p>Self-reported · verify in AWS</p></div><div class="practice-stat"><span>CURRENT TOOLCHAIN</span><div class="practice-stat-value">EKS ${esc(toolchain?.eks?.version||'—')}</div><a href="${guideLink('toolchain')}">${terraform?`Terraform ${esc(terraform)} · `:''}Release & validation details</a></div></section>
      <section><div class="catalog-heading"><div><div class="eyebrow">THREE PATHS · ONE COMPLETE PRACTICE LOOP</div><h2>Choose what to sharpen.</h2></div></div><div class="path-grid">${paths.map(path=>{const labs=catalog.labs.filter(lab=>Number(lab.number)>=path.range[0]&&Number(lab.number)<=path.range[1]),done=labs.filter(lab=>record(lab.id).status==='done').length,target=labs.find(lab=>record(lab.id).status!=='done')||labs[0];return `<a class="path-card" href="${C.labRoute(target.id)}"><span class="path-icon">${icon(path.glyph)}</span><span class="path-label">LABS ${String(path.range[0]).padStart(2,'0')}–${String(path.range[1]).padStart(2,'0')}</span><h3>${path.name}</h3><p>${path.description}</p><div class="path-meta"><span>${done} / ${labs.length} complete</span>${icon('arrow')}</div><progress class="path-progress" value="${done}" max="${labs.length}" aria-label="${path.name} progress"></progress></a>`;}).join('')}</div></section>
      <section class="lab-section"><div class="section-heading"><div><div class="section-kicker">THE PRACTICE PATH</div><h2>Choose your next challenge</h2></div><span class="section-count" id="result-count">${catalog.labs.length} labs</span></div><div class="toolbar"><div class="filter-tabs" aria-label="Filter labs by track">${['All','Terraform','AWS','Kubernetes','Capstone'].map(t => `<button class="filter-button ${track === t ? 'active' : ''}" data-filter="${t}" aria-pressed="${track === t}">${t === 'All' ? 'All labs' : t}</button>`).join('')}</div><label class="search-field">${icon('search')}<input id="lab-search" type="search" placeholder="Find a lab…" aria-label="Search labs" value="${esc(query)}"><kbd>/</kbd></label></div><div class="lab-grid" id="lab-grid"></div></section><p class="footer-note">Small infrastructure. Serious practice. Run commands in your terminal and tear down at the end of every session.</p>`;
    $('#lab-search').addEventListener('input', e => { query = e.target.value; renderCards(); });
    document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
      track = button.dataset.filter;
      document.querySelectorAll('[data-filter]').forEach(b => { b.classList.toggle('active', b === button); b.setAttribute('aria-pressed', String(b === button)); });
      renderCards();
    }));
    renderCards();
  }
  function guideLink(fragment) {
    const doc = catalog.docs.find(d => `${d.id} ${d.path}`.includes(fragment));
    return doc ? `#/guide/${encodeURIComponent(doc.id)}` : '#/';
  }
  function renderCards() {
    const labs = C.filterLabs(catalog.labs, query, track);
    $('#result-count').textContent = `${labs.length} ${labs.length === 1 ? 'lab' : 'labs'}`;
    $('#lab-grid').innerHTML = labs.length ? labs.map(l => labCard(l)).join('') : '<div class="empty-state"><h3>No labs found</h3><p>Try “state”, “IAM”, or another track.</p><button class="button secondary" id="clear-filters">Clear filters</button></div>';
    $('#clear-filters')?.addEventListener('click', () => { query = ''; track = 'All'; renderHome(); });
  }
  function renderIncidents() {
    const lab = catalog.labs.find(l => l.number === '11');
    $('#topbar-title').textContent = 'Workspace / Incident gauntlet';
    $('#main').innerHTML = `<div class="page-header"><div class="eyebrow">ON-CALL SIMULATOR</div><h1>Something is broken.<br>Find out why.</h1><p>${lab.scenarios.length} isolated incidents. Begin with the symptom, collect evidence, and make the smallest Terraform repair.</p><div class="hero-actions"><a class="button secondary" href="${C.labRoute(lab.id)}">Read the gauntlet briefing ${icon('arrow')}</a><button class="button primary" id="random-incident">${icon('bolt')} Surprise me</button></div></div><div class="callout"><strong>Use your Game 07 cluster.</strong> Run one incident at a time. Use its Terraform root to remove the workload when done; destroy the cluster when the session ends.</div><div class="lab-grid scenario-grid">${lab.scenarios.map(l => labCard(l,true)).join('')}</div>`;
    $('#random-incident').addEventListener('click', () => { location.hash = C.labRoute(lab.scenarios[Math.floor(Math.random()*lab.scenarios.length)].id); });
  }
  const checkpoints = [['reproduce','Build or reproduce','I reached the expected starting state.'],['diagnose','Explain the behavior','I can explain the cause and tradeoffs.'],['verify','Prove the result','I ran the mission’s acceptance checks.'],['cleanup','Complete teardown','I followed cleanup and checked for leftovers.']];
  function renderSession(lab) {
    const saved = record(lab.id);
    return `<aside class="session-panel" aria-label="Mission progress"><div class="session-label">YOUR SESSION</div><h3>Make it count.</h3><p class="session-intro">A working fix is only part of the answer.</p><div id="mission-status">${statusBadge(lab.id)}</div><button class="button ${saved.status === 'new' ? 'primary' : 'secondary'}" id="start-mission">${saved.status === 'new' ? 'Start this mission' : saved.status === 'done' ? 'Practice again' : 'Session in progress'} ${icon(saved.status === 'done' ? 'arrow' : 'terminal')}</button><div class="checklist">${checkpoints.map(([id,label,hint]) => `<label class="check-item"><input type="checkbox" data-check="${id}" ${saved.checks[id] ? 'checked' : ''}><span class="check-copy"><strong>${label}</strong><span class="check-hint">${hint}</span></span></label>`).join('')}</div><button class="button primary" id="complete-mission" ${!C.isComplete(saved) || saved.status === 'done' ? 'disabled' : ''}>${icon('check')} ${saved.status === 'done' ? 'Mission complete' : 'Mark complete'}</button><p class="session-fineprint">These are your own checks. The app cannot verify AWS cleanup.</p><div class="session-section"><div class="session-label">COST & CLEANUP</div><p>${esc(lab.cost)}</p><a class="inline-link" href="${guideLink('cost')}">Open the cleanup guide ${icon('arrow')}</a></div><div class="session-section"><div class="session-label">INTERVIEW REMINDER</div><p>What proved your hypothesis? Why does the fix work? What would you change in production?</p></div></aside>`;
  }
  function wireSession(lab) {
    $('#start-mission').addEventListener('click', () => {
      if (record(lab.id).status === 'active') { notify('Use the checklist as you work through the mission.'); return; }
      const wasDone = record(lab.id).status === 'done';
      updateRecord(lab.id, wasDone ? C.resetPractice(record(lab.id)) : {status:'active'});
      renderRoute();
    });
    document.querySelectorAll('[data-check]').forEach(input => input.addEventListener('change', () => {
      const current = record(lab.id);
      const checks = {...current.checks,[input.dataset.check]:input.checked};
      const stage={reproduce:'build',diagnose:'investigate',verify:'verify',cleanup:'cleanup'}[input.dataset.check];
      const practice={...current.practice,completed:input.checked?current.practice.completed:current.practice.completed.filter(id=>id!==stage)};
      updateRecord(lab.id, {checks,practice,status:current.status === 'done' && C.isComplete({checks}) ? 'done' : 'active'});
      $('#mission-status').innerHTML = statusBadge(lab.id);
      $('#complete-mission').disabled = !C.isComplete(record(lab.id)) || record(lab.id).status === 'done';
      $('#complete-mission').innerHTML = `${icon('check')} ${record(lab.id).status === 'done' ? 'Mission complete' : 'Mark complete'}`;
      $('#start-mission').innerHTML = `Session in progress ${icon('terminal')}`;
      renderSidebar();
    }));
    $('#complete-mission').addEventListener('click', () => {
      if (!C.isComplete(record(lab.id))) return;
      updateRecord(lab.id, {status:'done'});
      notify('Mission complete. Keep your evidence for the interview.');
      renderRoute();
    });
  }
  async function renderLab(lab, version) {
    $('#topbar-title').textContent = `Workspace / ${lab.id.includes('/') ? 'Incident gauntlet' : 'Lab directory'} / ${lab.number}`;
    const parentHref = lab.id.includes('/') ? '#/incidents' : '#/';
    const tabs = [['workspace','Workspace'],['brief','Runbook'],['files','Files'], ...(lab.hints ? [['hints','Hints']] : []), ...(lab.answers ? [['answers','Solution']] : []),['notes','My notes']];
    let prerequisites='';
    try {
      const response=await fetch(`/api/launch?${new URLSearchParams({id:lab.id})}`);
      if(response.ok){
        const recipe=await response.json();
        const sequence={'02':'Apply the bootstrap root first. Configure the workload backend and migrate its state before continuing.','09':'Apply the IAM and Pod Identity root first, then the workload root.','10':'Apply the IAM root and finish the EBS driver setup before applying the workload root.','13':'Apply the workload root first, then the access root. Prove the final endpoint from outside the cluster. Remove access before destroying the workload.'}[recipe.alias];
        if(recipe.prerequisites.length||sequence)prerequisites=`<section class="mission-prerequisites" aria-label="Required infrastructure"><h2>Before this exercise: bring up the prerequisites.</h2><p>Prepared files are not a running environment. Review and apply the prerequisite Terraform, then complete its readiness checks.</p>${recipe.prerequisites.length?`<ol>${recipe.prerequisites.map(id=>`<li><a href="${C.labRoute(id)}">${esc(exercises.find(item=>item.id===id)?.title||id)}</a> — follow its setup, plan, apply and verification steps.</li>`).join('')}</ol>`:''}${sequence?`<p><strong>Setup order:</strong> ${sequence}</p>`:''}<p>Use <code>arcade tui</code> for supported environment actions. Keep the foundation until dependent workloads have been destroyed. Live readiness has not been checked by this browser.</p></section>`;
      }
    }catch{prerequisites='<section class="mission-prerequisites"><h2>Check prerequisites in the runbook.</h2><p>The setup list could not be loaded. Do not treat a prepared workspace as a ready environment.</p></section>';}
    if(version!==renderVersion)return;
    if (!tabs.some(([id]) => id === route.tab)) route.tab = 'workspace';
    $('#main').innerHTML = `<a class="back-link" href="${parentHref}">${icon('back')} ${lab.id.includes('/') ? 'All incidents' : 'All labs'}</a><div class="mission-header"><div class="eyebrow">${lab.id.includes('/') ? 'INCIDENT' : 'LAB'} ${esc(lab.number)} <span>/</span> ${esc(lab.track)}</div><h1>${esc(lab.title)}</h1><p>${esc(lab.summary)}</p><div class="mission-meta"><span>${icon('clock')} ${esc(lab.duration)}</span><span>${icon(trackIcon(lab.track))} ${esc(lab.mode)}</span><span>${icon('terminal')} Run commands in your terminal</span></div></div><div class="detail-grid ${route.tab === 'workspace' ? 'workspace-detail' : ''}"><section class="reader-panel"><nav class="reader-tabs" aria-label="Mission views">${tabs.map(([id,label]) => `<a class="tab-button ${route.tab === id ? 'active' : ''}" ${route.tab === id ? 'aria-current="page"' : ''} href="${esc(C.labRoute(lab.id,id))}">${id === 'answers' ? icon('lock') : ''}${label}${id === 'files' ? `<span>${lab.files.length}</span>` : ''}</a>`).join('')}</nav><div id="reader-content" class="reader-content ${route.tab === 'workspace' ? 'workspace-content' : ''}"><div class="loading-state">Opening source…</div></div></section>${route.tab === 'workspace' ? '' : renderSession(lab)}</div>`;
    if(route.tab !== 'workspace') wireSession(lab);
    if(prerequisites)$('#main').querySelector('.detail-grid').insertAdjacentHTML('beforebegin',prerequisites);
    const panel = $('#reader-content');
    if (route.tab === 'workspace') {
      practiceCleanup=await window.ArcadePractice.mount(panel,lab,{esc,icon,record,updateRecord,notify,copyText,getFile,renderMarkdown,isCurrent:()=>version===renderVersion});
      return;
    }
    if (route.tab === 'notes') { renderNotes(lab,panel); return; }
    if (route.tab === 'files') { await renderFiles(lab,panel,version); return; }
    if (route.tab === 'answers' && !revealed.has(`${lab.id}:answers`)) { renderGate(panel,'answers',lab,version); return; }
    if (route.tab === 'hints' && !revealed.has(`${lab.id}:hints`)) { renderGate(panel,'hints',lab,version); return; }
    const path = route.tab === 'answers' ? lab.answers : route.tab === 'hints' ? lab.hints : lab.readme;
    const data = await getFile(path);
    if (version !== renderVersion) return;
    renderMarkdown(panel,data.content,path);
    if (lab.scenarios.length && route.tab === 'brief') {
      const section = document.createElement('div'); section.className='scenario-links';
      section.innerHTML = `<h2>Choose an incident</h2><div class="scenario-grid">${lab.scenarios.map(s => `<a class="scenario-card" href="${C.labRoute(s.id)}"><span class="eyebrow">INCIDENT ${esc(s.number)}</span><strong>${esc(s.summary)}</strong>${icon('arrow')}</a>`).join('')}</div>`;
      panel.prepend(section);
    }
  }
  function renderGate(panel,type,lab,version,callback) {
    const hint = type === 'hints';
    panel.innerHTML = `<div class="gate-card"><span class="gate-icon">${icon(hint ? 'book' : 'lock')}</span><div class="eyebrow">${hint ? 'A LITTLE DIRECTION' : 'GIVE YOURSELF A SHOT FIRST'}</div><h2>${hint ? 'Need a nudge?' : 'Your hypothesis comes first.'}</h2><p>${hint ? 'Hints open one layer at a time. Start with the first, then return to the problem.' : 'Write down what you observed and the fix you would try. Reveal the reference when you’re ready to compare.'}</p><button class="button primary" id="reveal-content">${hint ? 'Show progressive hints' : type === 'solutions' ? 'Reveal reference files' : 'Reveal solution'} ${icon('arrow')}</button><a class="inline-link" href="${C.labRoute(lab.id,'notes')}">Capture my hypothesis first</a></div>`;
    $('#reveal-content').addEventListener('click', () => {
      if (version !== renderVersion) return;
      revealed.add(`${lab.id}:${type}`);
      if (callback) callback(); else renderRoute();
    });
  }
  async function renderFiles(lab,panel,version) {
    if (!lab.files.length) { panel.innerHTML='<div class="empty-state"><h3>No standalone source files</h3><p>The instructions contain the commands. Pick an incident for its starter and solution files.</p></div>'; return; }
    let selected = lab.files.find(f => f.path === route.file) || lab.files.find(f => f.kind !== 'solution') || lab.files[0];
    panel.innerHTML = `<div class="file-browser"><div class="file-list" aria-label="Source files">${['starter','other','solution'].map(kind => {
      const files = lab.files.filter(f => f.kind === kind);
      return files.length ? `<div class="file-group-label">${kind === 'solution' ? 'REFERENCE · REVEAL TO READ' : kind === 'starter' ? 'START HERE' : 'SUPPORTING FILES'}</div>${files.map(f => `<a class="file-button ${selected.path === f.path ? 'active' : ''}" href="${esc(C.labRoute(lab.id,'files',f.path))}" ${selected.path === f.path ? 'aria-current="page"' : ''}>${icon(f.kind === 'solution' ? 'lock' : 'file')}<span>${esc(f.name)}</span></a>`).join('')}` : '';
    }).join('')}</div><div id="file-content" class="file-content"></div></div>`;
    const content = $('#file-content');
    if (selected.kind === 'solution' && !revealed.has(`${lab.id}:solutions`)) {
      renderGate(content,'solutions',lab,version,() => renderRoute()); return;
    }
    content.innerHTML='<div class="loading-state">Opening source…</div>';
    const data = await getFile(selected.path);
    if (version !== renderVersion) return;
    if (data.language === 'markdown') { renderMarkdown(content,data.content,data.path); return; }
    content.innerHTML=`<div class="file-header"><span>${esc(selected.path)}</span></div><div class="code-frame"><div class="code-toolbar"><span>${esc(data.language)}</span><button class="copy-button">${icon('copy')} Copy file</button></div><pre class="code-content" tabindex="0"><code></code></pre></div>`;
    content.querySelector('code').textContent=data.content;
    content.querySelector('.copy-button').addEventListener('click',event => copyText(data.content,event.currentTarget));
  }
  function renderNotes(lab,panel) {
    panel.innerHTML=`<div class="notes-view"><div class="eyebrow">YOUR INTERVIEW EVIDENCE</div><h2>Think out loud. Keep the proof.</h2><p>Capture the symptom, your hypothesis, the decisive command, and why the fix worked.</p><label class="field-label" for="mission-notes">Notes for ${esc(lab.title)}</label><textarea class="notes-input" id="mission-notes" rows="18" placeholder="Observed symptom:\n\nHypothesis:\n\nEvidence / commands:\n\nFix and verification:\n\nWhat I would change in production:\n\nCleanup proof:"></textarea><div class="note-status" id="note-status">${storageAvailable ? 'Stored only in this browser. Export progress to keep a backup.' : 'Session only — browser storage is unavailable.'}</div><p class="session-fineprint">Keep credentials and secret values out of your notes.</p></div>`;
    $('#mission-notes').value=record(lab.id).notes;
    $('#mission-notes').addEventListener('input',e => {
      updateRecord(lab.id,{notes:e.target.value});
      $('#note-status').textContent=storageAvailable ? 'Saved in this browser just now.' : 'Not saved to disk — export before closing.';
    });
  }
  function routeForFile(path) {
    const guide=catalog.docs.find(doc => doc.path === path);
    if (guide) return `#/guide/${encodeURIComponent(guide.id)}`;
    if (path === 'README.md') return '#/';
    for (const lab of exercises) {
      if (lab.readme === path) return C.labRoute(lab.id,'brief');
      if (lab.hints === path) return C.labRoute(lab.id,'hints');
      if (lab.answers === path) return C.labRoute(lab.id,'answers');
      if (lab.files.some(file => file.path === path)) return C.labRoute(lab.id,'files',path);
    }
    return null;
  }
  function renderMarkdown(target,source,path) {
    target.innerHTML=DOMPurify.sanitize(marked.parse(source), {
      USE_PROFILES:{html:true}, FORBID_TAGS:['img','iframe','form','input','button','style','script'],
      FORBID_ATTR:['style','id','name'], ALLOW_DATA_ATTR:false
    });
    target.classList.add('prose');
    const headings=new Map();
    target.querySelectorAll('h1,h2,h3,h4').forEach(heading => {
      const base=heading.textContent.toLowerCase().replace(/[^\p{L}\p{N}\s-]/gu,'').trim().replace(/\s+/g,'-');
      const count=headings.get(base)||0; headings.set(base,count+1); heading.id=`section-${base}${count ? `-${count}` : ''}`;
    });
    target.querySelectorAll('a').forEach(link => {
      const href=link.getAttribute('href')||'';
      if (/^https?:\/\//i.test(href)) { link.target='_blank'; link.rel='noopener noreferrer'; return; }
      if (href.startsWith('#')) {
        link.href=`#section-${href.slice(1)}`;
        link.addEventListener('click',event => { event.preventDefault(); target.querySelector(`#${CSS.escape(`section-${href.slice(1)}`)}`)?.scrollIntoView({behavior:'smooth'}); }); return;
      }
      const destination=C.resolvePath(path,href);
      const next=destination && routeForFile(destination);
      if (next) link.href=next;
      else { link.removeAttribute('href'); link.title='Open this path in your local project.'; link.classList.add('unresolved-link'); }
    });
    target.querySelectorAll('pre').forEach(pre => {
      const code=pre.querySelector('code'); if (!code) return;
      const text=code.textContent;
      const wrapper=document.createElement('div'); wrapper.className='code-frame';
      const bar=document.createElement('div'); bar.className='code-toolbar';
      const language=code.className.replace('language-','')||'text';
      bar.innerHTML=`<span>${esc(language)}</span><button class="copy-button" aria-label="Copy ${esc(language)} code">${icon('copy')} Copy</button>`;
      pre.before(wrapper); wrapper.append(bar,pre); pre.classList.add('code-content'); pre.tabIndex=0;
      bar.querySelector('button').addEventListener('click',e => copyText(text,e.currentTarget));
    });
    target.querySelectorAll('table').forEach(table => { const wrapper=document.createElement('div'); wrapper.className='table-scroll'; table.before(wrapper); wrapper.append(table); });
  }
  const copyFeedback = new WeakMap();
  async function copyText(text,button) {
    try {
      await navigator.clipboard.writeText(text);
      if (!button.isConnected) return;
      const feedback=copyFeedback.get(button)||{label:button.innerHTML,timer:null};
      clearTimeout(feedback.timer);
      button.innerHTML=`${icon('check')} Copied`;
      feedback.timer=setTimeout(() => {
        if (button.isConnected) button.innerHTML=feedback.label;
        copyFeedback.delete(button);
      },1600);
      copyFeedback.set(button,feedback);
      notify('Copied. Paste and review in your terminal.');
    } catch { notify('Clipboard access was blocked. Select the code and copy it manually.'); }
  }
  async function renderGuide(doc,version) {
    $('#topbar-title').textContent=`Field guides / ${doc.title}`;
    $('#main').innerHTML=`<a class="back-link" href="#/">${icon('back')} Back to labs</a><div class="mission-header"><div class="eyebrow">FIELD GUIDE</div><h1>${esc(doc.title)}</h1></div><section class="reader-panel guide-reader"><div class="reader-content" id="guide-content"><div class="loading-state">Opening guide…</div></div></section>`;
    const file=await getFile(doc.path);
    if (version !== renderVersion) return;
    renderMarkdown($('#guide-content'),file.content,doc.path);
  }
  function closeMenu(restoreFocus = true) {
    const wasOpen = $('#sidebar').classList.contains('is-open');
    $('#sidebar').classList.remove('is-open'); $('#sidebar-overlay').classList.remove('is-open'); $('#menu-toggle').setAttribute('aria-expanded','false');
    $('#sidebar-overlay').tabIndex = -1;
    $('.workspace').inert = false;
    if (wasOpen && restoreFocus) $('#menu-toggle').focus();
    else if (wasOpen) $('#main').focus();
  }
  async function renderRoute() {
    practiceCleanup(); practiceCleanup=()=>{};
    const version=++renderVersion;
    route=C.parseRoute(location.hash);
    renderSidebar();
    window.scrollTo(0,0);
    const main=$('#main'); main.setAttribute('aria-busy','true');
    try {
      if (route.kind === 'home') renderHome();
      else if (route.kind === 'practice' || route.kind === 'drill') {
        $('#topbar-title').textContent='Practice desk / No AWS required';
        const context={esc,icon,notify,isCurrent:()=>version===renderVersion,getState:()=>progress.drills,setState:value=>{progress.drills=value;saveProgress();}};
        if(route.kind==='practice')await window.ArcadeDrills.desk(main,context);
        else practiceCleanup=await window.ArcadeDrills.mount(main,route.id,context)||(()=>{});
      }
      else if (route.kind === 'incidents') renderIncidents();
      else if (route.kind === 'lab') {
        const lab=exercises.find(l => l.id === route.id);
        if (!lab) throw new Error('That mission does not exist. Choose a mission from the directory.');
        document.title=`${lab.title} · AWS Arcade`;
        await renderLab(lab,version);
      } else if (route.kind === 'guide') {
        const doc=catalog.docs.find(d => d.id === route.id);
        if (!doc) throw new Error('That guide does not exist. Open a guide from the sidebar.');
        await renderGuide(doc,version);
      } else throw new Error('That page does not exist. Return to the lab directory.');
      if (route.kind !== 'lab') document.title='AWS Arcade · Terraform + EKS';
    } catch (error) {
      if (version !== renderVersion) return;
      main.innerHTML=`<div class="error-state"><h1>Couldn’t open this page.</h1><p>${esc(error.message)}</p><button class="button primary" id="retry-page">Try again</button><a class="button secondary" href="#/">Lab directory</a></div>`;
      $('#retry-page').addEventListener('click',renderRoute);
    } finally { if (version === renderVersion) main.removeAttribute('aria-busy'); }
  }
  async function boot() {
    loadProgress();
    document.querySelector('a[href="#main"]')?.addEventListener('click', event => { event.preventDefault(); $('#main').focus(); });
    $('#menu-toggle').setAttribute('aria-controls','sidebar'); $('#menu-toggle').setAttribute('aria-expanded','false');
    $('#menu-toggle').addEventListener('click',() => {
      if ($('#sidebar').classList.contains('is-open')) { closeMenu(); return; }
      $('#sidebar').classList.add('is-open'); $('#sidebar-overlay').classList.add('is-open');
      $('#sidebar-overlay').tabIndex = 0;
      $('#menu-toggle').setAttribute('aria-expanded','true'); $('.workspace').inert = true;
      $('#sidebar').querySelector('a,button')?.focus();
    });
    $('#sidebar-overlay').addEventListener('click',() => closeMenu());
    window.addEventListener('resize',() => { if (innerWidth > 900) closeMenu(false); });
    document.addEventListener('keydown',event => {
      if (event.key === 'Escape') closeMenu();
      if (event.key === 'Tab' && $('#sidebar').classList.contains('is-open')) {
        const focusable = [...$('#sidebar').querySelectorAll('a[href],button:not([disabled])'),$('#sidebar-overlay')];
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (!focusable.includes(document.activeElement)) { event.preventDefault(); first.focus(); }
        else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
      if (event.key === '/' && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) { if ($('#lab-search')) { event.preventDefault(); $('#lab-search').focus(); } }
    });
    try {
      const response=await fetch('/api/catalog');
      if (!response.ok) throw new Error('Catalog request failed');
      catalog=await response.json();
      try { const versions=await fetch('/api/toolchain'); if(versions.ok)toolchain=await versions.json(); } catch { /* Guides remain available if the version manifest cannot load. */ }
      exercises=catalog.labs.flatMap(lab => [lab,...lab.scenarios]);
      window.addEventListener('hashchange',renderRoute);
      window.addEventListener('storage', event=>{ if(event.key===KEY && event.newValue) {progress=C.mergeStored(progress,C.readProgress(event.newValue));notify('Progress changed in another tab. Reopen this mission to load its latest details.');renderSidebar();} });
      await renderRoute();
    } catch {
      $('#main').innerHTML='<div class="error-state"><h1>The local server is unavailable.</h1><p>Run <code>python3 web/server.py</code> from the project folder, then reload this page.</p><button class="button primary" id="reload-app">Reload</button></div>';
      $('#reload-app').addEventListener('click',() => location.reload());
    }
  }
  boot();
})();
