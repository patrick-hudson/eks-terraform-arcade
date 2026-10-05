const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const P = require('../practice-core.js');
const C = require('../core.js');

// A small DOM for the markup and handlers rendered by practice.js. Requests stay
// pending until the test settles them, so no real server or timing delays are used.
class Element {
  constructor(tag = 'div', attributes = {}, parent = null) {
    this.tag = tag;
    this.attributes = attributes;
    this.parent = parent;
    this.children = [];
    this.dataset = Object.fromEntries(Object.entries(attributes)
      .filter(([key]) => key.startsWith('data-'))
      .map(([key, value]) => [key.slice(5), value]));
    this.disabled = 'disabled' in attributes;
    this.listeners = {};
    this.classList = {toggle() {}};
  }
  get isConnected() { return this.parent ? this.parent.isConnected : this.root === true; }
  set innerHTML(html) {
    for (const child of this.children) child.parent = null;
    this.children = [];
    this.html = html;
    const stack = [this];
    for (const token of html.matchAll(/<\/?([a-z][\w-]*)\b([^>]*)>/gi)) {
      const [whole, tag, raw] = token;
      if (whole.startsWith('</')) {
        if (stack.at(-1).tag === tag) stack.pop();
        continue;
      }
      const attributes = Object.fromEntries([...raw.matchAll(/([\w-]+)(?:="([^"]*)"|='([^']*)'|=([^\s>]+))?/g)]
        .map(([, key, double, single, bare]) => [key, double ?? single ?? bare ?? '']));
      const parent = stack.at(-1), element = new Element(tag, attributes, parent);
      parent.children.push(element);
      if (!['input', 'br', 'hr', 'img'].includes(tag)) stack.push(element);
    }
  }
  get innerHTML() { return this.html || ''; }
  matches(selector) {
    if (selector.startsWith('#')) return this.attributes.id === selector.slice(1);
    if (selector.startsWith('.')) return (this.attributes.class || '').split(' ').includes(selector.slice(1));
    const data = selector.match(/^\[([\w-]+)(?:=["']?([^"'\]]+)["']?)?\]$/);
    if (data) return data[1] in this.attributes && (data[2] === undefined || this.attributes[data[1]] === data[2]);
    return this.tag === selector;
  }
  querySelectorAll(selector) {
    return this.children.flatMap(child => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  addEventListener(event, handler) { this.listeners[event] = handler; }
  setAttribute(key, value) { this.attributes[key] = value; }
  focus() {}
  scrollIntoView() {}
  click() {
    if (this.disabled) return;
    return (this.onclick || this.listeners.click)?.({currentTarget: this});
  }
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}
function createPractice({savedHints = 0} = {}) {
  const lesson = {
    objective: 'Find the fault', skills: [], prerequisites: [], questions: [], debriefPrompts: [],
    stages: P.stages.map(id => ({id, title: id, summary: '', checkpoint: '', commands: [], tasks: [], hintCount: id === 'investigate' ? 3 : 0}))
  };
  let record = {...C.blankRecord(), status: 'done', practice: P.normalize({stage: 'investigate', hintCounts: {investigate: savedHints}})};
  const panel = new Element(); panel.root = true;
  const hints = [], notifications = [], writes = [];
  const window = {ArcadePracticeCore: P, ArcadeCore: C, ArcadeLauncher: {mount() {}}, ArcadeVerification: {mount() {}}};
  const sandbox = {
    window, URLSearchParams, CSS: {escape: value => value}, setInterval: () => 1, clearInterval() {},
    fetch: async url => {
      if (url.startsWith('/api/lesson?')) return {ok: true, json: async () => lesson};
      assert.ok(url.startsWith('/api/hint?'));
      const pending = deferred(); hints.push(pending);
      return {ok: true, json: () => pending.promise};
    }
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../practice.js'), 'utf8'), sandbox);
  const ready = window.ArcadePractice.mount(panel, {id: 'test', title: 'Test', cost: '$0'}, {
    esc: value => String(value), icon: () => '', record: () => record,
    updateRecord: (id, change) => { record = {...record, ...change}; writes.push(change); },
    notify: message => notifications.push(message), copyText() {}, isCurrent: () => true
  });
  return {panel, hints, notifications, writes, ready, record: () => record,
    click: selector => { const element = panel.querySelector(selector); assert.ok(element, selector); return element.click(); },
    coach: () => panel.querySelector('#coach-body').innerHTML};
}
const hint = title => ({title, body: `${title} body`});
const settle = () => new Promise(resolve => setImmediate(resolve));

test('a pending hint does not count or appear after starting a new attempt', async () => {
  const app = createPractice(); await app.ready;
  const reveal = app.click('#next-hint');
  app.click('#new-attempt');
  app.hints[0].resolve(hint('OLD ATTEMPT')); await reveal;
  assert.equal(app.record().practice.hintCounts.investigate, 0);
  assert.doesNotMatch(app.coach(), /OLD ATTEMPT/);
});

test('new attempt ignores the old reveal and keeps a newer request busy', async () => {
  const app = createPractice(); await app.ready;
  const oldReveal = app.click('#next-hint');
  app.click('#new-attempt');
  const newReveal = app.click('#next-hint');
  assert.equal(app.hints.length, 2);
  app.hints[0].resolve(hint('OLD ATTEMPT'));
  await oldReveal;
  assert.equal(app.record().practice.hintCounts.investigate, 0);
  assert.equal(app.panel.querySelector('#next-hint').disabled, true);
  assert.doesNotMatch(app.coach(), /OLD ATTEMPT/);
  app.hints[1].resolve(hint('Fresh hint'));
  await newReveal;
  assert.equal(app.record().practice.hintCounts.investigate, 1);
  assert.equal(app.panel.querySelector('#next-hint').disabled, false);
  assert.match(app.coach(), /Fresh hint/);
  assert.doesNotMatch(app.coach(), /OLD ATTEMPT/);
});

test('new attempt suppresses an old reveal error', async () => {
  const app = createPractice(); await app.ready;
  const oldReveal = app.click('#next-hint');
  app.click('#new-attempt');
  app.hints[0].reject(new Error('Old request failed'));
  await oldReveal;
  assert.equal(app.record().practice.hintCounts.investigate, 0);
  assert.deepEqual(app.notifications, ['New attempt started. Previous evidence and notes are retained.']);
});

test('saved-hint retry cannot overwrite a hint revealed in a new attempt', async () => {
  const app = createPractice({savedHints: 1});
  await settle(); app.hints[0].reject(new Error('Temporary failure')); await app.ready;
  const oldRetry = app.click('#retry-hints');
  app.click('#new-attempt');
  const newReveal = app.click('#next-hint');
  app.hints[2].resolve(hint('Fresh content')); await newReveal;
  app.hints[1].resolve(hint('OLD SAVED CONTENT')); await oldRetry;
  assert.equal(app.record().practice.hintCounts.investigate, 1);
  assert.match(app.coach(), /Fresh content/);
  assert.doesNotMatch(app.coach(), /OLD SAVED CONTENT/);
});

test('saved hints can still be retried in the same attempt', async () => {
  const app = createPractice({savedHints: 1});
  await settle(); app.hints[0].reject(new Error('Temporary failure')); await app.ready;
  assert.match(app.coach(), /Saved hint unavailable/);
  const retry = app.click('#retry-hints');
  app.hints[1].resolve(hint('Recovered hint')); await retry;
  assert.match(app.coach(), /Recovered hint/);
  assert.equal(app.record().practice.hintCounts.investigate, 1);
  assert.equal(app.panel.querySelector('#retry-hints'), null);
});

test('stage navigation keeps an in-flight hint within the same attempt', async () => {
  const app = createPractice(); await app.ready;
  const reveal = app.click('#next-hint');
  app.click('[data-stage="build"]');
  app.hints[0].resolve(hint('Still relevant')); await reveal;
  assert.equal(app.record().practice.stage, 'build');
  assert.equal(app.record().practice.hintCounts.investigate, 1);
  assert.match(app.coach(), /Still relevant/);
});

test('disposing the workspace suppresses pending hint errors and state writes', async () => {
  const app = createPractice(); const dispose = await app.ready;
  const reveal = app.click('#next-hint'); dispose();
  app.hints[0].reject(new Error('Request from closed workspace')); await reveal;
  assert.equal(app.writes.length, 0);
  assert.deepEqual(app.notifications, []);
});
