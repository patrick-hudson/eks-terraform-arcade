const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function harness() {
  const source = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
  const start = source.indexOf('  async function copyText(');
  const end = source.indexOf('  async function renderGuide(', start);
  assert.ok(start >= 0 && end > start, 'load the actual copyText function');
  const state = source.match(/^  const copyFeedback = new WeakMap\(\);$/m)?.[0] || '';
  const requests = [], messages = [], timers = new Map();
  let now = 0, nextTimer = 0;
  const copy = vm.runInNewContext(`${state}\n${source.slice(start, end)}\ncopyText`, {
    navigator: {clipboard: {writeText(text) {
      return new Promise((resolve, reject) => requests.push({text, resolve, reject}));
    }}},
    icon: name => `<svg data-icon="${name}"></svg>`,
    notify: message => messages.push(message),
    setTimeout(callback, delay) {
      const id = ++nextTimer;
      timers.set(id, {callback, at: now + delay});
      return id;
    },
    clearTimeout: id => timers.delete(id),
  }, {filename: 'web/app.js'});
  function advance(milliseconds) {
    const target = now + milliseconds;
    for (;;) {
      const next = [...timers].filter(([, timer]) => timer.at <= target)
        .sort((a, b) => a[1].at - b[1].at)[0];
      if (!next) break;
      now = next[1].at;
      timers.delete(next[0]);
      next[1].callback();
    }
    now = target;
  }
  return {copy, requests, messages, timers, advance};
}

const original = '<svg data-icon="copy"></svg> Copy command';
const copied = '<svg data-icon="check"></svg> Copied';
const button = (label = original) => ({innerHTML: label, isConnected: true});

test('repeated successful copy restores the original icon and custom label once', async () => {
  const h = harness(), target = button();
  const first = h.copy('first command', target);
  h.requests[0].resolve(); await first;
  assert.equal(target.innerHTML, copied);
  h.advance(800);
  const second = h.copy('second command', target);
  h.requests[1].resolve(); await second;
  assert.deepEqual(h.requests.map(request => request.text), ['first command', 'second command']);
  assert.equal(h.timers.size, 1);
  h.advance(800);
  assert.equal(target.innerHTML, copied, 'the earlier timer cannot reset the latest feedback');
  h.advance(799);
  assert.equal(target.innerHTML, copied);
  h.advance(1);
  assert.equal(target.innerHTML, original);
  assert.equal(h.timers.size, 0);
});

test('different buttons restore their own labels on independent timers', async () => {
  const h = harness(), firstButton = button(), secondButton = button('Copy path');
  const first = h.copy('command', firstButton);
  h.requests[0].resolve(); await first;
  h.advance(300);
  const second = h.copy('/tmp/file', secondButton);
  h.requests[1].resolve(); await second;
  assert.equal(h.timers.size, 2);
  h.advance(1300);
  assert.equal(firstButton.innerHTML, original);
  assert.equal(secondButton.innerHTML, copied);
  h.advance(300);
  assert.equal(secondButton.innerHTML, 'Copy path');
});

test('clipboard rejection leaves the label and an earlier successful reset intact', async () => {
  const h = harness(), target = button();
  const rejected = h.copy('blocked', target);
  h.requests[0].reject(new Error('blocked')); await rejected;
  assert.equal(target.innerHTML, original);
  assert.equal(h.timers.size, 0);
  const success = h.copy('allowed', target);
  h.requests[1].resolve(); await success;
  h.advance(400);
  const retry = h.copy('blocked again', target);
  h.requests[2].reject(new Error('blocked')); await retry;
  assert.equal(target.innerHTML, copied);
  assert.equal(h.timers.size, 1);
  h.advance(1200);
  assert.equal(target.innerHTML, original);
  assert.match(h.messages.at(-1), /Clipboard access was blocked/);
});

test('out-of-order clipboard completions retain the original label', async () => {
  const h = harness(), target = button();
  const first = h.copy('first', target), second = h.copy('second', target);
  h.requests[1].resolve(); await second;
  h.advance(900);
  h.requests[0].resolve(); await first;
  h.advance(1600);
  assert.equal(target.innerHTML, original);
  assert.equal(h.timers.size, 0);
});

test('late clipboard completion and timeout do not update detached buttons', async () => {
  const h = harness(), beforeCompletion = button(), beforeReset = button();
  const pending = h.copy('late', beforeCompletion);
  beforeCompletion.isConnected = false;
  h.requests[0].resolve(); await pending;
  assert.equal(beforeCompletion.innerHTML, original);
  assert.equal(h.timers.size, 0);
  const success = h.copy('copied', beforeReset);
  h.requests[1].resolve(); await success;
  beforeReset.isConnected = false;
  h.advance(1600);
  assert.equal(beforeReset.innerHTML, copied);
  assert.equal(h.timers.size, 0);
});
