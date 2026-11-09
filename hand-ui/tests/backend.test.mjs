// Offline tests: every test starts with network access disabled.
import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { Readable } from 'node:stream';

process.env.TZ = 'America/Los_Angeles';
const root = new URL('../../../planner.io/src/server/', import.meta.url);
const { createApiHandler } = await import(new URL('app.mjs', root));
const { createRoutes } = await import(new URL('routes.mjs', root));
const { readAllEvents } = await import(new URL('events.mjs', root));
const { readGroups } = await import(new URL('groups.mjs', root));
const { readDeadlines } = await import(new URL('deadlines.mjs', root));
const { buildEventProposal, checkEventProposal } = await import(new URL('eventProposal.mjs', root));
const { buildDeadlineProposal } = await import(new URL('deadlineProposal.mjs', root));
const { writeConfirmedEvent } = await import(new URL('eventWriter.mjs', root));
const { writeConfirmedDeadline } = await import(new URL('deadlineWriter.mjs', root));
const { rememberProposal, confirmProposal, cancelProposal } = await import(new URL('pendingProposals.mjs', root));
const { readSchedule } = await import(new URL('schedule.mjs', root));
const { readAvailability } = await import(new URL('availability.mjs', root));
const { readReminders } = await import(new URL('reminders.mjs', root));

let oldFetch;
beforeEach(() => {
  oldFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error('Network forbidden in regression tests'); };
});
afterEach(() => { globalThis.fetch = oldFetch; });

function jsonResponse(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => structuredClone(body) };
}
function document(id, fields) { return { name: `users/test/events/${id}`, fields }; }
const input = { title: 'Study', date: '2026-11-09', startTime: '16:00', durationMinutes: 30,
  location: 'Powell', importance: 'very', notes: 'Original notes', color: '#7B5EDB' };
function eventDocument() {
  return document('lecture', {
    name: { stringValue: 'Lecture' }, startTime: { timestampValue: '2026-11-02T18:00:00Z' },
    duration: { integerValue: '60' }, importance: { stringValue: 'very' },
    recurrence: { mapValue: { fields: { type: { stringValue: 'weekly' },
      days: { arrayValue: { values: [{ stringValue: 'monday' }] } } } } },
  });
}
async function request(handler, method, path, body, authorized = true) {
  const req = Readable.from(body === undefined ? [] : [JSON.stringify(body)]);
  req.method = method; req.url = path;
  req.headers = { 'content-type': 'application/json',
    ...(authorized ? { authorization: 'Bearer fake-token' } : {}) };
  const res = { writeHead(status) { this.status = status; }, end(text) { this.body = JSON.parse(text); } };
  await handler(req, res);
  return res;
}
function handler(services = {}, verifyIdToken = async () => ({ uid: 'verified-user' })) {
  return createApiHandler({ verifyIdToken, services });
}

test('every registered route except health requires a bearer token', async () => {
  let verifications = 0;
  const api = handler({}, async () => { verifications++; return { uid: 'test' }; });
  for (const key of createRoutes().keys()) {
    const [method, path] = key.split(' ');
    const res = await request(api, method, path, {}, false);
    assert.equal(res.status, path === '/health' ? 200 : 401, key);
  }
  assert.equal(verifications, 0);
});

test('deadline route stores a draft using the verified UID', async () => {
  let stored;
  const api = handler({
    buildDeadlineProposal: async (token, uid, body) => {
      assert.equal(token, 'fake-token'); assert.equal(uid, 'verified-user');
      return { status: 'needs_confirmation', saved: false, deadline: { name: body.title } };
    },
    rememberProposal: (uid, draft) => { stored = { uid, draft }; return { ...draft, proposalId: 'id' }; },
  });
  const res = await request(api, 'POST', '/deadline-proposals', { title: 'Report', uid: 'attacker-choice' });
  assert.equal(res.status, 200); assert.equal(res.body.proposalId, 'id');
  assert.equal(stored.uid, 'verified-user');
});

test('unknown route stays 404 and missing proposal IDs stay 400', async () => {
  assert.equal((await request(handler(), 'GET', '/unknown')).status, 404);
  assert.equal((await request(handler(), 'POST', '/event-proposals/confirm', {})).status, 400);
  assert.equal((await request(handler(), 'POST', '/event-proposals/cancel', {})).status, 400);
});

test('invalid tokens stay 401', async () => {
  const api = handler({}, async () => { throw Object.assign(new Error('expired'), { code: 'auth/id-token-expired' }); });
  assert.equal((await request(api, 'GET', '/me')).status, 401);
});

test('collection pagination combines pages and rejects repeated tokens', async () => {
  const calls = [];
  const events = await readAllEvents('fake', 'test', async (_token, _uid, page) => {
    calls.push(page);
    return page ? { events: [{ id: 'b' }] } : { events: [{ id: 'a' }], nextPageToken: 'next' };
  });
  assert.deepEqual(calls, [null, 'next']); assert.deepEqual(events.map(e => e.id), ['a', 'b']);
  await assert.rejects(readAllEvents('fake', 'test', async () => ({ events: [], nextPageToken: 'same' })), /pagination/);
});

test('group and deadline readers keep existing field formats', async () => {
  globalThis.fetch = async url => jsonResponse({ documents: [
    document('item', String(url).includes('/groups') ? {
      name: { stringValue: 'Classes' }, color: { stringValue: '#008f51' },
    } : {
      name: { stringValue: 'Report' }, dueTime: { timestampValue: '2026-11-10T23:00:00Z' },
      importance: { stringValue: 'very' }, completed: { booleanValue: false },
    }),
  ] });
  assert.equal((await readGroups('fake', 'test'))[0].color, '#008f51');
  assert.equal((await readDeadlines('fake', 'test'))[0].completed, false);
});

test('weekly schedule and availability use actual occurrences', async () => {
  globalThis.fetch = async () => jsonResponse({ documents: [eventDocument()] });
  const params = new URLSearchParams({ start: '2026-11-09', end: '2026-11-10', timezone: 'America/Los_Angeles' });
  const schedule = await readSchedule('fake', 'test', params);
  assert.equal(schedule.events.length, 1);
  assert.equal(schedule.events[0].start, '2026-11-09T18:00:00.000Z');
  const availability = await readAvailability('fake', 'test', new URLSearchParams({
    date: '2026-11-09', timezone: 'America/Los_Angeles' }));
  assert.deepEqual(availability.slots.map(slot => slot.durationMinutes), [180, 660]);
});

test('reminders preserve importance and exclude completed deadlines', async () => {
  globalThis.fetch = async url => {
    if (String(url).includes('/groups')) return jsonResponse({});
    if (String(url).includes('/events')) return jsonResponse({ documents: [eventDocument()] });
    return jsonResponse({ documents: [false, true].map((completed, i) => document(`deadline-${i}`, {
      name: { stringValue: 'Report' }, dueTime: { timestampValue: '2026-11-10T23:00:00Z' },
      importance: { stringValue: 'very' }, completed: { booleanValue: completed },
    })) });
  };
  const result = await readReminders('fake', 'test', new URLSearchParams({ view: 'importance' }));
  assert.equal(result.total, 2); assert.equal(result.items.filter(i => i.kind === 'deadline').length, 1);
});

test('group assignment keeps event color independent', async () => {
  globalThis.fetch = async () => jsonResponse({ documents: [document('classes', {
    name: { stringValue: 'Classes' }, color: { stringValue: '#008f51' },
  })] });
  const result = await checkEventProposal('fake', 'test', { ...input, groupName: 'Classes' }, async () => ({ events: [] }));
  assert.equal(result.event.color, '#7B5EDB'); assert.equal(result.event.groupId, 'classes');
});

test('deadline validation asks for missing data and keeps deadline semantics', async () => {
  assert.deepEqual((await buildDeadlineProposal('fake', 'test', { title: 'Report' })).missing, ['date', 'dueTime']);
  const result = await buildDeadlineProposal('fake', 'test', { title: 'Report', date: '2026-11-09', dueTime: '23:59' });
  assert.equal(result.kind, 'deadline'); assert.equal(result.deadline.completed, false);
  assert.equal(result.deadline.dueTime, '2026-11-10T07:59:00.000Z');
});

test('event and deadline writers retain fields and fixed IDs on retry', async () => {
  let savedFields; let posts = 0;
  globalThis.fetch = async (url, options) => {
    assert.equal(options.headers.Authorization, 'Bearer fake');
    if (options.method === 'POST') {
      posts++;
      const fields = JSON.parse(options.body).fields;
      if (posts === 1) { savedFields = fields; return jsonResponse({}); }
      assert.deepEqual(fields, savedFields);
      return jsonResponse({ error: { status: 'ALREADY_EXISTS' } }, 409);
    }
    return jsonResponse({ fields: savedFields });
  };
  const event = buildEventProposal({ ...input, recurrence: { type: 'weekly', days: ['monday'] } }).event;
  assert.equal((await writeConfirmedEvent('fake', 'test', 'fixed', event)).eventId, 'uni-fixed');
  assert.equal((await writeConfirmedEvent('fake', 'test', 'fixed', event)).eventId, 'uni-fixed');
  assert.equal(savedFields.location.stringValue, 'Powell');
  posts = 0;
  const deadline = (await buildDeadlineProposal('fake', 'test', { title: 'Report', date: '2026-11-09', dueTime: '23:59' })).deadline;
  assert.equal((await writeConfirmedDeadline('fake', 'test', 'deadline-fixed', deadline)).deadlineId, 'uni-deadline-fixed');
  assert.equal((await writeConfirmedDeadline('fake', 'test', 'deadline-fixed', deadline)).deadlineId, 'uni-deadline-fixed');
  assert.equal(savedFields.completed.booleanValue, false);
});

test('ownership, cancellation, expiry, and concurrent confirmations', async () => {
  const draft = { ...buildEventProposal(input), status: 'needs_confirmation', conflicts: [] };
  const pending = rememberProposal('user-a', draft);
  let writes = 0;
  const checker = async () => structuredClone(draft);
  const writer = async () => { writes++; return { eventId: 'mock' }; };
  assert.equal((await confirmProposal('fake', 'user-b', pending.proposalId, checker, writer)).status, 'draft_unavailable');
  const results = await Promise.all([
    confirmProposal('fake', 'user-a', pending.proposalId, checker, writer),
    confirmProposal('fake', 'user-a', pending.proposalId, checker, writer),
  ]);
  assert.equal(writes, 1); assert.ok(results.every(result => result.status === 'saved'));
  const cancelled = rememberProposal('cancel-user', draft);
  assert.equal(cancelProposal('cancel-user', cancelled.proposalId), true);
  assert.equal(cancelProposal('cancel-user', cancelled.proposalId), false);
  const expired = rememberProposal('expire-user', draft);
  const now = Date.now;
  try {
    Date.now = () => now() + 301000;
    assert.equal((await confirmProposal('fake', 'expire-user', expired.proposalId, checker, writer)).status, 'draft_unavailable');
  } finally { Date.now = now; }
});

test('changed conflicts replace approval instead of saving', async () => {
  const draft = { ...buildEventProposal(input), status: 'needs_confirmation', conflicts: [] };
  const pending = rememberProposal('conflict-user', draft);
  let writes = 0;
  const result = await confirmProposal('fake', 'conflict-user', pending.proposalId,
    async () => ({ ...draft, conflicts: [{ id: 'busy', name: 'Lecture', start: 'a', end: 'b' }] }),
    async () => { writes++; return { eventId: 'unexpected' }; });
  assert.equal(result.status, 'needs_confirmation');
  assert.notEqual(result.proposalId, pending.proposalId); assert.equal(writes, 0);
});

test('deadline confirmation uses the stored deadline and deduplicates writes', async () => {
  const draft = await buildDeadlineProposal('fake', 'test', { title: 'Report', date: '2026-11-09', dueTime: '23:59' });
  const pending = rememberProposal('deadline-user', draft); let posts = 0;
  globalThis.fetch = async (_url, options) => { assert.equal(options.method, 'POST'); posts++; return jsonResponse({}); };
  const results = await Promise.all([
    confirmProposal('fake', 'deadline-user', pending.proposalId),
    confirmProposal('fake', 'deadline-user', pending.proposalId),
  ]);
  assert.equal(posts, 1); assert.ok(results.every(r => r.kind === 'deadline' && r.saved));
});
