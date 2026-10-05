/* Local receipt reader. Importing a JSON file never executes a command. */
(() => {
  'use strict';
  const V=window.ArcadeVerificationCore;
  function mount(target,labId,phase,context) {
    const {esc,icon,record,updateRecord,notify,copyText}=context;
    if(!V.supported.has(labId)) {
      target.innerHTML='<div class="verification-note"><strong>Live evidence</strong><p>Follow the runbook’s acceptance commands and save the output in Evidence. Automated snapshot checks currently cover the EKS foundation, Kubernetes release, and eight incidents.</p><a class="inline-link" href="#/guide/aws-testing">Set up a bounded AWS test →</a></div>';
      return;
    }
    let selected=0;
    const slug=labId.replaceAll('/','-');
    const command=[
      '(', '  set -euo pipefail',
      '  : "${LAB_ROOT:?Set LAB_ROOT to the kit root}"',
      '  : "${AWS_PROFILE:?Choose your sandbox profile}"',
      '  : "${TF_VAR_expected_account_id:?Set the expected AWS account ID}"',
      '  : "${AWS_REGION:?Choose your lab region}"',
      '  : "${CLUSTER_NAME:?Set the lab cluster name}"',
      '  : "${LAB_KUBE_CONTEXT:?Set the lab kubeconfig context}"',
      '  python3 "$LAB_ROOT/scripts/verify-lab.py" \\',
      `    --lab '${labId}' --phase '${phase}' \\`,
      '    --profile "$AWS_PROFILE" --expected-account "$TF_VAR_expected_account_id" \\',
      '    --region "$AWS_REGION" --cluster "$CLUSTER_NAME" --context "$LAB_KUBE_CONTEXT" \\',
      `    --output "$LAB_ROOT/run/${slug}-${phase}-$(date -u +%Y%m%dT%H%M%SZ)-receipt.json"`,
      ')'
    ].join('\n');
    function render() {
      if(!target.isConnected)return;
      const receipts=(record(labId).receipts||[]).filter(item=>item.phase===phase), receipt=receipts[selected]||receipts[0];
      const previous=receipt && receipts.find(item=>Date.parse(item.generatedAt)<Date.parse(receipt.generatedAt)&&['account','region','cluster','context'].every(key=>receipt.environment[key]===item.environment[key]));
      const changes=V.compare(receipt,previous);
      target.innerHTML=`<section class="verification-panel" aria-label="Imported cluster checks"><div class="verification-heading"><div><span class="eyebrow">EXPERIMENTAL · REAL COMMAND OBSERVATIONS</span><h3>${phase==='cleanup'?'Check the named resources are gone':'Put the result to a real check.'}</h3></div><span class="verification-badge">${receipt?'Receipt loaded':'No receipt yet'}</span></div><p class="verification-intro">Run the read-only verifier in your terminal, then bring its JSON report here. It checks account, region and cluster before inspecting the exercise.</p>
      <details class="verification-command"><summary>1. Generate a ${phase==='cleanup'?'cleanup':'verification'} receipt</summary><div class="code-frame"><div class="code-toolbar"><span>Bash · read-only AWS / Kubernetes calls</span><button class="copy-button" id="copy-verifier">${icon('copy')} Copy</button></div><pre class="code-content" tabindex="0"><code>${esc(command)}</code></pre></div><p class="field-note">Uses your existing authenticated terminal profile. Exit 0 means all selected checks passed; 1 means a failed check; 2 means an execution/setup error. The runbook still defines the full acceptance contract.</p></details>
      <div class="receipt-controls"><label class="button secondary receipt-picker">${icon('file')} 2. Import receipt<input class="visually-hidden" type="file" accept="application/json,.json" id="receipt-file" aria-label="Import verification receipt"></label><a class="inline-link" href="#/guide/live-verification">What these checks prove ${icon('arrow')}</a></div>
      ${receipts.length?`<div class="receipt-history" aria-label="Receipt history">${receipts.map((item,i)=>`<button class="receipt-history-item ${item===receipt?'is-selected':''}" data-receipt-index="${i}" aria-pressed="${item===receipt}"><span class="receipt-dot ${V.outcome(item)}"></span><span>${esc(new Date(item.generatedAt).toLocaleString())}</span><strong>${item.summary.passed}/${item.checks.length} passed</strong></button>`).join('')}</div>`:''}
      ${receipt?`<div class="receipt-result ${V.outcome(receipt)}"><div><span class="eyebrow">IMPORTED ${phase.toUpperCase()} SNAPSHOT</span><h4>${receipt.summary.passed} passed · ${receipt.summary.failed} failed · ${receipt.summary.errors} errors</h4></div><p>${esc(receipt.environment.cluster)} · ${esc(receipt.environment.region)} · account ${esc(receipt.environment.account)}</p><time datetime="${esc(receipt.generatedAt)}">Observed ${esc(new Date(receipt.generatedAt).toLocaleString())}</time></div>
      ${changes.length?`<div class="receipt-diff"><strong>Changed since the previous snapshot</strong><ul>${changes.map(item=>`<li><span>${esc(item.label)}</span><span class="check-transition">${item.from} → ${item.to}</span></li>`).join('')}</ul></div>`:''}
      <div class="receipt-checks">${receipt.checks.map(check=>`<details class="receipt-check ${check.status}" ${check.status!=='pass'?'open':''}><summary><span class="check-status">${check.status==='pass'?'PASS':check.status==='fail'?'FAIL':'ERROR'}</span><strong>${esc(check.label)}</strong></summary><dl><dt>Expected</dt><dd>${esc(check.expected)}</dd><dt>Observed</dt><dd>${esc(check.observed)}</dd></dl></details>`).join('')}</div><div class="receipt-scope"><strong>What remains unproven</strong><p>${esc(receipt.scope)}</p></div>`:'<div class="receipt-empty"><span>Evidence beats a green checkbox.</span><p>A failed baseline and a passing follow-up give you a useful interview story. The latest three reports for each phase are retained.</p></div>'}
      <p class="field-note">Receipts are editable local files, not signed attestations. They describe one point in time, do not update your task checkboxes, and cannot certify whole-account cleanup.</p></section>`;
      target.querySelector('#copy-verifier').onclick=event=>copyText(command,event.currentTarget);
      target.querySelector('#receipt-file').onchange=async event=>{
        const input=event.currentTarget,file=input.files[0];if(!file)return;
        try {
          if(file.size>262144)throw new Error('Choose a verifier JSON receipt smaller than 256 KB.');
          const imported=V.parse(await file.text(),labId);
          if(!target.isConnected)return;
          const result=V.importHistory(record(labId).receipts||[],imported);
          updateRecord(labId,{receipts:result.history});
          selected=imported.phase===phase?result.selected:0;render();notify(imported.phase===phase?'Receipt imported. Your task checks remain unchanged.':`Receipt stored. Open the ${imported.phase==='cleanup'?'Cleanup':'Verify'} stage to inspect it.`);
        }catch(error){notify(error.message);input.value='';}
      };
      target.querySelectorAll('[data-receipt-index]').forEach(button=>button.onclick=()=>{selected=Number(button.dataset.receiptIndex);render();});
    }
    render();
  }
  window.ArcadeVerification={mount};
})();
