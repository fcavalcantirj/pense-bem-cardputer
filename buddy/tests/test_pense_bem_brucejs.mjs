#!/usr/bin/env node

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(here, '../brucejs/Games/PenseBem.js');
const source = fs.readFileSync(sourcePath, 'utf8');

const noop = () => {};
let currentTextSize = 1;
const drawnStrings = [];
const display = {
  width: () => 240,
  height: () => 135,
  color: (r, g, b) => (r << 16) | (g << 8) | b,
  fill: noop,
  drawFillRect: noop,
  setTextSize: (size) => { currentTextSize = size; },
  setTextColor: noop,
  drawString: (value, x, y) => drawnStrings.push({value, x, y, size: currentTextSize}),
};
const numKeyboardCalls = [];
const keyboard = {
  getKeysPressed: () => [],
  getEscPress: () => false,
  getSelPress: () => false,
  getPrevPress: () => false,
  getNextPress: () => false,
  numKeyboard: (...args) => {
    numKeyboardCalls.push(args);
    return '991';
  },
};
const wifi = {
  connected: () => true,
  connectDialog: () => true,
  httpFetch: () => ({ok: true, status: 200, body: {}}),
};
const audio = {tone: noop};
const storage = {read: () => '{"record":0}', write: () => true};

const sandbox = {
  __PENSE_BEM_TEST__: true,
  __dirpath: '/BruceJS/Games',
  console,
  delay: noop,
  require(name) {
    return {display, keyboard, wifi, audio, storage}[name];
  },
};
vm.createContext(sandbox);
new vm.Script(source, {filename: sourcePath}).runInContext(sandbox);

assert.equal(sandbox.normalizeCode('991'), '991');
assert.equal(sandbox.normalizeCode('011'), '011');
for (const invalid of ['', '99', '990', '997', '000', 'abc', '1 1']) {
  assert.equal(sandbox.normalizeCode(invalid), null, `invalid code accepted: ${invalid}`);
}

// Bruce passes the first numKeyboard argument straight through as the initial
// text. It must be empty or a 3-character field starts over capacity and the
// physical Cardputer keyboard cannot add a digit.
keyboard.getSelPress = () => true;
assert.equal(sandbox.readCode(), '991');
assert.deepEqual(numKeyboardCalls[0], ['', 3, 'CODIGO BBS - Exemplo: 991', false]);
keyboard.getSelPress = () => false;

assert.deepEqual(
  JSON.parse(JSON.stringify(sandbox.makeStartPayload('991'))),
  {code: '991', client: 'atari8', protocol: 1},
);
assert.deepEqual(
  JSON.parse(JSON.stringify(sandbox.makeAnswerPayload('session-1', 7, 'C'))),
  {session_id: 'session-1', request_id: 7, answer: 'C'},
);

const question = sandbox.parseQuestion({
  number: 1,
  position: 1,
  total: 30,
  attempt: 2,
  text: 'Quanto e 2 + 2?',
  options: ['3', '4', '5', '6'],
});
assert.equal(question.attempt, 2);
assert.equal(question.options[1], '4');
assert.throws(() => sandbox.parseQuestion({text: 'x', options: ['a']}));

// Short textbook prompts and answers use the readable 2x font. The compact
// status counters remain at 1x, and long content still has a bounded fallback.
drawnStrings.length = 0;
sandbox.drawQuestion(question, 0, 0);
assert.ok(drawnStrings.some((item) => item.value === 'Quanto e 2 + 2?' && item.size === 2));
assert.ok(drawnStrings.some((item) => item.value === 'A 3' && item.size === 2));

drawnStrings.length = 0;
sandbox.drawQuestion({...question, text: 'x'.repeat(39), options: ['x'.repeat(17), '4', '5', '6']}, 0, 0);
assert.ok(drawnStrings.some((item) => item.value.includes('~') && item.size === 1));

assert.equal(sandbox.normalizedScore(300, 30), 100);
assert.equal(sandbox.normalizedScore(296, 30), 99);
assert.equal(sandbox.normalizedScore(0, 30), 0);

// A transient network failure retries the exact same immutable payload object.
const sent = [];
const payload = sandbox.makeAnswerPayload('session-1', 12, 'D');
let attempts = 0;
let retryPrompts = 0;
sandbox.postJSON = (_url, value) => {
  sent.push(value);
  attempts += 1;
  if (attempts === 1) throw {kind: 'network', message: 'link down'};
  return {ok: true};
};
sandbox.waitRetry = () => {
  retryPrompts += 1;
  return true;
};
assert.deepEqual(JSON.parse(JSON.stringify(sandbox.postWithRetry('/answer', payload))), {ok: true});
assert.equal(sent.length, 2);
assert.equal(sent[0], payload);
assert.equal(sent[1], payload);
assert.equal(sent[1].request_id, 12);
assert.equal(retryPrompts, 0, 'one transient failure should recover without another click');

// After two automatic attempts, the explicit retry screen remains available.
attempts = 0;
retryPrompts = 0;
sandbox.postJSON = (_url, value) => {
  assert.equal(value, payload);
  attempts += 1;
  if (attempts <= 3) throw {kind: 'network', message: 'link down'};
  return {ok: true};
};
assert.deepEqual(JSON.parse(JSON.stringify(sandbox.postWithRetry('/answer', payload))), {ok: true});
assert.equal(attempts, 4);
assert.equal(retryPrompts, 1);

// Server/protocol failures are shown once and must not be retried as network errors.
let serverAttempts = 0;
sandbox.postJSON = () => {
  serverAttempts += 1;
  throw {kind: 'server', message: 'content_unavailable'};
};
sandbox.showError = noop;
assert.equal(sandbox.postWithRetry('/start', sandbox.makeStartPayload('011')), null);
assert.equal(serverAttempts, 1);

assert.match(source, /response\.explanation/);
assert.match(source, /var answerPayload = makeAnswerPayload[\s\S]*postWithRetry/);
assert.match(source, /http:\/\/148\.230\.73\.44:18081/);
assert.doesNotMatch(source, /wifi\.connectDialog/);
assert.doesNotMatch(source, /wifi_pass|wifi_ssid|Idalina0609|IDALINA&FILIPE/);
assert.doesNotMatch(source, /_PB_SEED|_PB_OFFSETS|dbaadcb/);

console.log('BruceJS Pense Bem protocol/retry/secrets contract: ok');
