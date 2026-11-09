import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
const root = new URL('../../../planner.io/src/', import.meta.url);
const { saveNote, searchNotes, getNote } = await import(new URL('server/notes.mjs', root));
const { remember, searchMemory, updateMemory, forgetMemory } = await import(new URL('server/memory.mjs', root));
const { encodeFields } = await import(new URL('server/firestore.mjs', root));
const { mergeNoteEntries } = await import(new URL('utils/mergeNoteEntries.ts', root));
const ID = '11111111-1111-4111-8111-111111111111';
const SECOND = '22222222-2222-4222-8222-222222222222';
let originalFetch;
beforeEach(() => { originalFetch = globalThis.fetch; globalThis.fetch = async () => { throw new Error('Real network forbidden'); }; });
afterEach(() => { globalThis.fetch = originalFetch; });
function response(body = {}, status = 200) { return { ok: status >= 200 && status < 300, status, json: async () => structuredClone(body) }; }
function database() {
  const documents = new Map(); let version = 0; let writes = 0; let intercept;
  function put(path, fields) {
    documents.set(path, { name: `projects/mock/databases/(default)/documents/${path}`, fields: structuredClone(fields), updateTime: `version-${++version}` });
  }
  globalThis.fetch = async (raw, options = {}) => {
    const url = new URL(raw); const path = decodeURIComponent(url.pathname.split('/documents/')[1]);
    const method = options.method ?? 'GET';
    assert.match(options.headers.Authorization, /^Bearer /);
    if (method === 'GET') {
      if (path.split('/').length === 3) {
        return response({ documents: [...documents.entries()].filter(([key]) => key.startsWith(path + '/')).map(([, value]) => value) });
      }
      return documents.has(path) ? response(documents.get(path)) : response({}, 404);
    }
    if (method === 'DELETE') { documents.delete(path); return response(); }
    assert.equal(method, 'PATCH');
    if (intercept) { const hook = intercept; intercept = null; hook(path); }
    const current = documents.get(path);
    if (url.searchParams.get('currentDocument.exists') === 'false' && current) return response({}, 409);
    if (url.searchParams.has('currentDocument.updateTime') && current?.updateTime !== url.searchParams.get('currentDocument.updateTime')) return response({}, 412);
    writes++; put(path, JSON.parse(options.body).fields); return response(documents.get(path));
  };
  return { documents, put, writes: () => writes, intercept: hook => { intercept = hook; } };
}

test('voice note appends without changing old content or categorization; retries do not duplicate', async () => {
  const db = database();
  db.put('users/a/notes/2026-11-09', encodeFields({ date: '2026-11-09', entries: [{ id: 'old', content: 'Original', createdAt: new Date(), topic: 'Classes' }], updatedAt: new Date() }));
  const input = { content: 'Chemistry: equilibrium is confusing.\nKeep this wording.', date: '2026-11-09', requestId: ID };
  const result = await saveNote('fake', 'a', input);
  await saveNote('fake', 'a', input);
  assert.equal(db.writes(), 1); assert.equal(result.entryId, `uni-${ID}`);
  const entries = db.documents.get('users/a/notes/2026-11-09').fields.entries.arrayValue.values;
  assert.equal(entries.length, 2); assert.equal(entries[0].mapValue.fields.topic.stringValue, 'Classes');
  assert.equal(entries[1].mapValue.fields.content.stringValue, input.content);
  assert.deepEqual(entries[1].mapValue.fields.topic, { nullValue: null });
  await assert.rejects(saveNote('fake', 'a', { ...input, content: 'Different' }), error => error.httpStatus === 409);
});

test('concurrent website change survives note retry', async () => {
  const db = database();
  db.intercept(path => db.put(path, encodeFields({ date: '2026-11-09', entries: [{ id: 'website', content: 'Website thought', createdAt: new Date(), topic: null }], updatedAt: new Date() })));
  await saveNote('fake', 'a', { content: 'Voice thought', date: '2026-11-09', requestId: ID });
  const entries = db.documents.get('users/a/notes/2026-11-09').fields.entries.arrayValue.values;
  assert.equal(entries.length, 2); assert.equal(entries[0].mapValue.fields.id.stringValue, 'website');
});

test('search returns dated original sources and respects user scope', async () => {
  database();
  await saveNote('fake', 'a', { content: 'Chemistry equilibrium revision', date: '2026-11-09', requestId: ID });
  await saveNote('fake', 'b', { content: 'Chemistry private', date: '2026-11-09', requestId: SECOND });
  const result = await searchNotes('fake', 'a', new URLSearchParams({ query: 'chemistry' }));
  assert.equal(result.total, 1); assert.equal(result.results[0].date, '2026-11-09');
  const full = await getNote('fake', 'a', new URLSearchParams({ date: '2026-11-09', entryId: result.results[0].entryId }));
  assert.equal(full.note.content, 'Chemistry equilibrium revision');
  assert.equal((await searchNotes('fake', 'a', new URLSearchParams({ query: 'biology' }))).total, 0);
});

test('memory persists through new reads, is distinct from notes, and supports correction and forgetting', async () => {
  const db = database();
  const saved = await remember('fake', 'a', { content: 'Prefers evening study', type: 'preference', sourceText: 'Remember that I prefer evening study.', requestId: ID });
  assert.equal(db.documents.size, 1);
  const found = await searchMemory('fake', 'a', new URLSearchParams({ query: 'study' }));
  assert.equal(found.results[0].memoryId, saved.memoryId);
  assert.match(found.results[0].sourceText, /^Remember/);
  assert.equal((await searchNotes('fake', 'a', new URLSearchParams({ query: '' }))).total, 0);
  assert.equal((await searchMemory('fake', 'b', new URLSearchParams({ query: '' }))).total, 0);
  await updateMemory('fake', 'a', { memoryId: saved.memoryId, content: 'Prefers morning study', sourceText: 'Actually remember mornings instead.' });
  assert.equal((await searchMemory('fake', 'a', new URLSearchParams({ query: 'morning' }))).total, 1);
  await forgetMemory('fake', 'a', { memoryId: saved.memoryId });
  assert.equal((await searchMemory('fake', 'a', new URLSearchParams({ query: '' }))).total, 0);
});

test('notes reject invalid dates and memory rejects invalid identifiers', async () => {
  database();
  await assert.rejects(saveNote('fake', 'a', { content: 'Test', date: '2026-02-30', requestId: ID }), error => error.httpStatus === 400);
  await assert.rejects(remember('fake', 'a', { content: 'Test', requestId: 'wrong', sourceText: 'Remember test' }), error => error.httpStatus === 400);
  await assert.rejects(forgetMemory('fake', 'a', { memoryId: '../other-user' }), error => error.httpStatus === 400);
});

function entry(id, content, topic = null) { return { id, content, topic, createdAt: new Date('2026-11-09T12:00:00Z') }; }
test('website merge preserves concurrent voice append and explicit local edits/deletions', () => {
  const base = [entry('old', 'Old thought')];
  const remote = [...base, entry('voice', 'Voice thought')];
  assert.deepEqual(mergeNoteEntries(base, [entry('old', 'Edited thought')], remote).map(e => e.content), ['Edited thought', 'Voice thought']);
  assert.deepEqual(mergeNoteEntries(base, [], remote).map(e => e.id), ['voice']);
});
test('website merge detects conflicting edits and preserves remote categorization', () => {
  const base = [entry('old', 'Thought')];
  assert.throws(() => mergeNoteEntries(base, [entry('old', 'Local edit')], [entry('old', 'Remote edit')]), /changed/);
  assert.equal(mergeNoteEntries(base, base, [entry('old', 'Thought', 'Chemistry')])[0].topic, 'Chemistry');
});

test('Firestore FAILED_PRECONDITION retries with the same note ID', async () => {
  const db = database(); const transport = globalThis.fetch; let rejected = false;
  globalThis.fetch = async (url, options = {}) => {
    if (options.method === 'PATCH' && !rejected) {
      rejected = true;
      return response({ error: { status: 'FAILED_PRECONDITION' } }, 400);
    }
    return transport(url, options);
  };
  const result = await saveNote('fake', 'a', { content: 'Retry safely', date: '2026-11-09', requestId: ID });
  assert.equal(result.entryId, `uni-${ID}`); assert.equal(db.writes(), 1);
});
