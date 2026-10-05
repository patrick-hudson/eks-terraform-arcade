const { test } = require('node:test');
const assert = require('node:assert/strict');
const core = require('../core.js');

test('nested incident routes and encoded file names survive a round trip', () => {
  const hash = core.labRoute('11-incident-gauntlet/scenario-01', 'files', 'labs/a file.tf');
  assert.deepEqual(core.parseRoute(hash), { kind: 'lab', id: '11-incident-gauntlet/scenario-01', tab: 'files', file: 'labs/a file.tf' });
  assert.equal(core.parseRoute('#/unknown').kind, 'missing');
  assert.equal(core.parseRoute('#/lab/%XX').kind, 'missing');
});

test('relative Markdown paths resolve across labs, without escaping the kit', () => {
  assert.equal(core.resolvePath('labs/11-incident-gauntlet/scenario-01/README.md', '../../07-eks-foundation/README.md'), 'labs/07-eks-foundation/README.md');
  assert.equal(core.resolvePath('README.md', '../../etc/passwd'), null);
  assert.equal(core.resolvePath('labs/a/README.md', 'HINTS.md'), 'labs/a/HINTS.md');
});

test('corrupt progress is recoverable and completion requires all checkpoints', () => {
  assert.deepEqual(core.readProgress('{broken').labs, {});
  assert.equal(core.readProgress('{"schemaVersion":1,"labs":[]}').schemaVersion, 3);
  const value = core.readProgress(JSON.stringify({ schemaVersion: 1, labs: { a: {status:'done', checks:{cleanup:false}, notes:'my notes'}, b:{status:'done', checks:{reproduce:true,diagnose:true,verify:true,cleanup:true}} } }));
  assert.equal(value.labs.a.status, 'active');
  assert.equal(value.labs.a.notes, 'my notes');
  assert.equal(value.labs.b.status, 'done');
  assert.equal(core.isComplete(value.labs.a), false);
});

test('search and track filters use public metadata, never answers', () => {
  const labs=[{title:'Private S3',summary:'Object storage',tags:['IAM'],track:'AWS',answers:'secret'}, {title:'Terraform',summary:'Collections',tags:[],track:'Terraform'}];
  assert.equal(core.filterLabs(labs, 'iam', 'AWS').length,1);
  assert.equal(core.filterLabs(labs, 'secret', 'All').length,0);
  assert.equal(core.filterLabs(labs, '', 'Terraform').length,1);
});

test('environment session links retain their route after reload',()=>{
  assert.equal(core.parseRoute(core.labRoute('00-terraform-contracts','session')).tab,'session');
});
