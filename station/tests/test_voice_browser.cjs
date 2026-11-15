// Run from the workspace root:
// .junction-setup/node/bin/node station/tests/test_voice_browser.cjs
// This harness executes the actual lab voice code with fake media, sockets,
// timers, and API responses. It does not open a browser or access a microphone.
'use strict';

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const stationRoot = path.resolve(__dirname, '..');
const sourcePath = path.join(stationRoot, 'morph_station/lab.html');
const resultPath = path.join(stationRoot, 'verification/voice-browser-tests.json');
const source = fs.readFileSync(sourcePath, 'utf8');
const start = source.indexOf('function pcm16(');
const end = source.lastIndexOf('refresh().catch(e=>feedback(e.message));');
assert(start >= 0 && end > start, 'The lab voice block must be present.');
const voiceCode = source.slice(start, end);
const inlineScript = source.match(/<script>([\s\S]*)<\/script>/)?.[1];
assert(inlineScript, 'The lab inline script must be present.');
new vm.Script(inlineScript.replace('__LOCAL_API_TOKEN__', '"test-placeholder"'));

class FakeSocket {
  constructor() { this.readyState = 1; this.sent = []; this.closeCount = 0; }
  send(value) { this.sent.push(JSON.parse(value)); }
  close() { this.readyState = 3; this.closeCount++; }
}

function fakeStream() {
  const track = { stopped: 0, stop() { this.stopped++; } };
  return { track, getTracks() { return [track]; } };
}

class FakeAudioContext {
  constructor() { this.state = 'running'; this.sampleRate = 48000; this.destination = {}; }
  async resume() {}
  async close() { this.state = 'closed'; }
  createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
  createScriptProcessor() { return { connect() {}, disconnect() {} }; }
}

function makeCapture(id) {
  return {
    id, stream: fakeStream(), socket: new FakeSocket(), recording: true,
    ready: true, started: true, released: false, closed: false,
    segments: [], sentSamples: 400, queue: Promise.resolve(),
  };
}

function providerEvent(messageType, text = 'speech') {
  return { data: JSON.stringify({ message_type: messageType, text }) };
}

function harness() {
  const elements = new Map(), timers = new Map(), pageEvents = new Map(), calls = [];
  let sequence = 0;
  let apiHandler = async () => { throw Error('Unexpected fake API call.'); };
  function element(id) {
    if (!elements.has(id)) {
      elements.set(id, { textContent: '', disabled: false, classList: { add() {}, remove() {} } });
    }
    return elements.get(id);
  }
  const sandbox = {
    Uint8Array, Int16Array, URL, Set, Promise, JSON, Math, Number, Error,
    clearTimeout: id => timers.delete(id),
    setTimeout: fn => { const id = ++sequence; timers.set(id, fn); return id; },
    btoa: text => Buffer.from(text, 'binary').toString('base64'),
    $: element, uid: () => String(++sequence),
    feedback: text => { element('feedback').textContent = text; },
    show: (id, value) => { element(id).textContent = value; },
    download() {}, refresh: async () => {},
    api: async (requestPath, body) => {
      calls.push({ path: requestPath, body });
      return apiHandler(requestPath, body);
    },
    navigator: { mediaDevices: { getUserMedia: async () => fakeStream() } },
    AudioContext: FakeAudioContext, WebSocket: FakeSocket,
    window: { addEventListener: (name, fn) => pageEvents.set(name, fn) },
    fixture: { session: 'simulation-session', cycle: 'simulation-cycle' },
    vpath: '/voice', capture: null,
  };
  vm.runInContext(voiceCode, vm.createContext(sandbox), { filename: sourcePath });
  return { sandbox, element, timers, pageEvents, calls, setApi(fn) { apiHandler = fn; } };
}

const groups = [
  ['stale_audio_cleanup_send_error_isolation', async () => {
    const h = harness(), old = makeCapture('old'), current = makeCapture('current');
    h.sandbox.capture = current;
    h.element('release').disabled = false;
    await h.sandbox.cleanupAudio(old);
    assert.equal(old.stream.track.stopped, 1);
    assert.equal(current.stream.track.stopped, 0);
    assert.equal(h.element('release').disabled, false);
    assert.equal(h.sandbox.audioSend(old, new Uint8Array(2)), false);
    assert.equal(current.socket.sent.length, 0);
    await h.sandbox.abortCapture(old, 'Stale failure');
    assert.equal(h.sandbox.capture, current);
    assert.equal(current.socket.closeCount, 0);
    assert.equal(h.element('feedback').textContent, '');
  }],
  ['late_enrichment_preserves_original_capture', async () => {
    const h = harness(), old = makeCapture('old-final'), current = makeCapture('current');
    h.sandbox.capture = current;
    h.element('transcript').textContent = 'Current capture';
    old.final = { status: 'finalized', text: 'speech' };
    old.segments = [{ index: 0, text: 'speech' }];
    h.setApi(async () => ({ status: 'finalized', text: 'speech' }));
    await h.sandbox.handleMessage(old, providerEvent('committed_transcript_with_timestamps'), true);
    assert.equal(h.calls[0].path, '/voice/old-final/events');
    assert.equal(h.element('transcript').textContent, 'Current capture');
    assert.equal(h.calls.length, 1);
    assert.equal(old.segments.length, 1);
    assert.equal(old.final.text, 'speech');
  }],
  ['release_commit_boundary_and_single_finalization', async () => {
    const h = harness(), own = makeCapture('commit');
    own.released = true;
    h.sandbox.capture = own;
    h.setApi(async requestPath => requestPath.endsWith('/finalize')
      ? { status: 'finalized', text: 'first second', provider: 'elevenlabs', modelId: 'scribe_v3_live' }
      : { status: 'finalizing', text: 'first', partialText: '' });
    await h.sandbox.handleMessage(own, providerEvent('committed_transcript', 'first'), false);
    assert.equal(h.calls.filter(call => call.path.endsWith('/finalize')).length, 0);
    await h.sandbox.handleMessage(own, providerEvent('committed_transcript', 'second'), true);
    assert.equal(h.calls.filter(call => call.path.endsWith('/finalize')).length, 1);
    assert.equal(h.sandbox.capture, own);
    assert.equal(own.final.status, 'finalized');
    await h.sandbox.handleMessage(own, providerEvent('committed_transcript_with_timestamps', 'second'), true);
    assert.equal(h.calls.filter(call => call.path.endsWith('/finalize')).length, 1);
  }],
  ['release_idempotency_bounded_silence_stale_timeout', async () => {
    const h = harness(), own = makeCapture('release');
    h.sandbox.capture = own;
    h.setApi(async () => ({ status: 'finalizing' }));
    await Promise.all([h.sandbox.finishCapture(own), h.sandbox.finishCapture(own)]);
    assert.equal(h.calls.filter(call => call.path.endsWith('/release')).length, 1);
    assert.equal(own.socket.sent.filter(message => message.commit).length, 1);
    assert.equal(own.sentSamples, 32000);
    assert(own.socket.sent.every(message => Buffer.from(message.audio_base_64, 'base64').length <= 32000));
    assert.equal(own.stream.track.stopped, 1);
    assert.equal(own.recording, false);
    assert.equal(own.commitSent, true);
    const next = makeCapture('next');
    h.sandbox.capture = next;
    await h.timers.get(own.timeout)();
    assert.equal(h.sandbox.capture, next);
    assert.equal(next.stream.track.stopped, 0);
    assert.equal(next.socket.closeCount, 0);
  }],
  ['late_finalize_response_cannot_revive_timeout', async () => {
    const h = harness(), own = makeCapture('slow-final');
    own.released = true;
    h.sandbox.capture = own;
    let resolveFinal;
    h.setApi(async requestPath => requestPath.endsWith('/finalize')
      ? new Promise(resolve => { resolveFinal = resolve; })
      : { status: 'finalizing', text: 'speech' });
    const pending = h.sandbox.handleMessage(own, providerEvent('committed_transcript'), true);
    await new Promise(setImmediate);
    assert.equal(typeof resolveFinal, 'function');
    await h.sandbox.abortCapture(own, 'Timed out');
    const next = makeCapture('next');
    h.sandbox.capture = next;
    resolveFinal({ status: 'finalized', text: 'speech' });
    await pending;
    assert.equal(h.sandbox.capture, next);
    assert.equal(own.final, undefined);
  }],
  ['pending_permission_lock_and_pagehide_cleanup', async () => {
    const h = harness();
    let resolveMedia, mediaRequests = 0;
    h.sandbox.navigator.mediaDevices.getUserMedia = () => {
      mediaRequests++;
      return new Promise(resolve => { resolveMedia = resolve; });
    };
    const waiting = h.sandbox.startCapture();
    await assert.rejects(h.sandbox.startCapture(), /already active/);
    assert.equal(mediaRequests, 1);
    h.pageEvents.get('pagehide')();
    const lateStream = fakeStream();
    resolveMedia(lateStream);
    await waiting;
    assert.equal(lateStream.track.stopped, 1);
    assert.equal(h.calls.length, 0);
  }],
  ['stale_socket_handlers_cannot_stop_next_capture', async () => {
    const h = harness();
    h.setApi(async requestPath => requestPath.endsWith('/token')
      ? { endpoint: 'wss://example.invalid', params: {}, token: 'fake-test-token' }
      : { status: 'capturing' });
    await h.sandbox.startCapture();
    const old = h.sandbox.capture;
    old.final = { status: 'finalized' };
    await h.sandbox.cleanupAudio(old);
    await h.sandbox.startCapture();
    const current = h.sandbox.capture;
    const transcript = h.element('transcript').textContent;
    old.socket.onerror();
    old.socket.onclose();
    await new Promise(setImmediate);
    assert.equal(h.sandbox.capture, current);
    assert.equal(current.stream.track.stopped, 0);
    assert.equal(h.element('transcript').textContent, transcript);
    assert.equal(current.recording, true);
    h.pageEvents.get('pagehide')();
  }],
];

(async () => {
  const results = [];
  for (const [name, run] of groups) {
    try {
      await run();
      results.push({ name, passed: true });
      console.log('PASS ' + name);
    } catch (error) {
      results.push({ name, passed: false, error: error.message });
      console.error('FAIL ' + name + ': ' + error.message);
    }
  }
  const sha256 = text => crypto.createHash('sha256').update(text).digest('hex');
  const passed = results.every(result => result.passed);
  const evidence = {
    schemaVersion: 1,
    checkedAt: new Date().toISOString(),
    runnerCommand: '.junction-setup/node/bin/node station/tests/test_voice_browser.cjs',
    testSource: 'station/tests/test_voice_browser.cjs',
    implementationSource: 'station/morph_station/lab.html',
    implementationSha256: sha256(source),
    voiceBlockSha256: sha256(voiceCode),
    runtime: { node: process.version, platform: process.platform, architecture: process.arch },
    scope: 'offline_browser_logic',
    limitation: 'Fake media, WebSocket, timers, and API responses; no real browser, microphone, provider, or physical robot verification.',
    providerCalls: 0,
    microphoneAccessed: false,
    physicalActionSent: false,
    inlineJavaScriptSyntaxPassed: true,
    passed,
    passedGroups: results.filter(result => result.passed).length,
    totalGroups: results.length,
    groups: results,
  };
  fs.mkdirSync(path.dirname(resultPath), { recursive: true });
  fs.writeFileSync(resultPath, JSON.stringify(evidence, null, 2) + '\n');
  console.log(`${evidence.passedGroups}/${evidence.totalGroups} offline voice browser test groups passed.`);
  console.log('Evidence: station/verification/voice-browser-tests.json');
  if (!passed) process.exitCode = 1;
})().catch(error => { console.error(error); process.exitCode = 1; });
