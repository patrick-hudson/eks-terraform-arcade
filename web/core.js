(function (root) {
  'use strict';
  const P = typeof module !== 'undefined' && module.exports ? require('./practice-core.js') : root.ArcadePracticeCore;
  const V = typeof module !== 'undefined' && module.exports ? require('./verification-core.js') : root.ArcadeVerificationCore;
  const D = typeof module !== 'undefined' && module.exports ? require('./drills-core.js') : root.ArcadeDrillsCore;
  const checkpointIds = ['reproduce', 'diagnose', 'verify', 'cleanup'];
  const blankRecord = () => ({ status: 'new', checks: {}, notes: '', updatedAt: null, practice: P.normalize(null), receipts: [] });
  const isComplete = record => checkpointIds.every(key => record?.checks?.[key] === true);
  function readProgress(raw) {
    const empty = { schemaVersion: 3, labs: {}, lastLab: null, drills: D.normalize(null) };
    try {
      const parsed = JSON.parse(raw);
      if (!parsed || ![1,2,3].includes(parsed.schemaVersion) || !parsed.labs || Array.isArray(parsed.labs) || typeof parsed.labs !== 'object') return empty;
      empty.drills = D.normalize(parsed.drills);
      for (const [id, record] of Object.entries(parsed.labs)) {
        if (!record || typeof record !== 'object' || ['__proto__', 'constructor', 'prototype'].includes(id)) continue;
        const clean = blankRecord();
        clean.receipts = V.normalizeHistory(record.receipts,id);
        clean.practice = P.normalize(record.practice);
        clean.notes = typeof record.notes === 'string' ? record.notes : '';
        clean.updatedAt = typeof record.updatedAt === 'string' ? record.updatedAt : null;
        clean.checks = Object.fromEntries(checkpointIds.map(key => [key, record.checks?.[key] === true]));
        clean.status = ['new', 'active', 'done'].includes(record.status) ? record.status : 'new';
        if (clean.status === 'done' && !isComplete(clean)) clean.status = 'active';
        empty.labs[id] = clean;
      }
      empty.lastLab = typeof parsed.lastLab === 'string' ? parsed.lastLab : null;
    } catch { /* An unreadable browser record is not a reason to hide the labs. */ }
    return empty;
  }
  function mergeStored(current, incoming) {
    const merged = readProgress(JSON.stringify(current));
    const timestamp = value => Number.isFinite(Date.parse(value)) ? Date.parse(value) : 0;
    for (const [id, record] of Object.entries(incoming.labs)) {
      if (!merged.labs[id] || timestamp(record.updatedAt) > timestamp(merged.labs[id].updatedAt)) merged.labs[id] = record;
    }
    merged.drills = D.merge(merged.drills, incoming.drills);
    return merged;
  }
  function snapshotProgress(progress, now=Date.now()) {
    const snapshot=readProgress(JSON.stringify(progress));
    snapshot.exportedAt=new Date(now).toISOString();
    snapshot.drills=D.snapshot(snapshot.drills,now);
    for(const record of Object.values(snapshot.labs)) record.practice.timer={elapsedMs:P.elapsed(record.practice,now),runningSince:null};
    return snapshot;
  }
  function resetPractice(record) {
    return {...record,status:'active',checks:{},practice:P.normalize({evidence:record.practice?.evidence,mode:record.practice?.mode})};
  }
  function mergeProgress(current, raw, knownIds) {
    let parsed;
    try { parsed = JSON.parse(raw); } catch { throw new Error('This is not a valid progress backup.'); }
    if (!parsed || ![1,2,3].includes(parsed.schemaVersion) || !parsed.labs || Array.isArray(parsed.labs) || typeof parsed.labs !== 'object') throw new Error('This backup has an unsupported format.');
    const incoming = readProgress(raw), progress = readProgress(JSON.stringify(current));
    const known = new Set(knownIds);
    let imported = 0, skipped = 0;
    for (const [id, record] of Object.entries(incoming.labs)) {
      if (!known.has(id)) { skipped++; continue; }
      const old = progress.labs[id];
      const time = value => Number.isFinite(Date.parse(value)) ? Date.parse(value) : 0;
      if (old && time(old.updatedAt) >= time(record.updatedAt)) { skipped++; continue; }
      const cutoff = Date.parse(parsed.exportedAt || record.updatedAt);
      record.practice.timer = {elapsedMs:P.elapsed(record.practice,Number.isFinite(cutoff) ? cutoff : record.practice.timer.runningSince || 0),runningSince:null};
      progress.labs[id] = record; imported++;
    }
    if (!progress.lastLab && known.has(incoming.lastLab)) progress.lastLab = incoming.lastLab;
    const cutoff=Date.parse(parsed.exportedAt);
    const frozen=D.snapshot(incoming.drills,Number.isFinite(cutoff)?cutoff:0);
    progress.drills=D.merge(progress.drills,frozen);
    return {progress, imported, skipped, drillAttempts:incoming.drills.history.length};
  }
  function labRoute(id, tab = 'workspace', file = '') {
    const query = new URLSearchParams({ tab });
    if (file) query.set('file', file);
    return `#/lab/${encodeURIComponent(id)}?${query}`;
  }
  function parseRoute(hash) {
    try {
      const [path, query] = hash.replace(/^#/, '').split('?');
      if (!path || path === '/') return { kind: 'home' };
      if (path === '/incidents') return { kind: 'incidents' };
      if (path === '/practice') return { kind: 'practice' };
      if (path.startsWith('/drill/')) return { kind: 'drill', id: decodeURIComponent(path.slice(7)) };
      if (path.startsWith('/guide/')) return { kind: 'guide', id: decodeURIComponent(path.slice(7)) };
      if (path.startsWith('/lab/')) {
        const params = new URLSearchParams(query);
        const tab = params.get('tab') || 'workspace';
        return { kind: 'lab', id: decodeURIComponent(path.slice(5)), tab: ['workspace','session','brief','files','hints','answers','notes'].includes(tab) ? tab : 'brief', file: params.get('file') || '' };
      }
    } catch { return { kind: 'missing' }; }
    return { kind: 'missing' };
  }
  function resolvePath(source, target) {
    if (/^[a-z][a-z0-9+.-]*:/i.test(target) || target.startsWith('//')) return null;
    const pieces = target.startsWith('/') ? [] : source.split('/').slice(0, -1);
    for (const part of target.split('#')[0].split('?')[0].split('/')) {
      if (!part || part === '.') continue;
      if (part === '..') { if (!pieces.length) return null; pieces.pop(); }
      else pieces.push(part);
    }
    return pieces.join('/');
  }
  function filterLabs(labs, query, track) {
    const words = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
    return labs.filter(lab => (track === 'All' || lab.track === track) && words.every(word => [lab.title,lab.summary,lab.number,lab.mode,...(lab.tags || [])].join(' ').toLowerCase().includes(word)));
  }
  const api = { checkpointIds, blankRecord, isComplete, readProgress, mergeProgress, mergeStored, snapshotProgress, resetPractice, labRoute, parseRoute, resolvePath, filterLabs };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ArcadeCore = api;
})(globalThis);
