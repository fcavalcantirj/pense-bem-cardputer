// SPDX-License-Identifier: GPL-3.0-only
// Pense Bem Online for Bruce firmware on the M5Stack Cardputer-Adv.
// Install on SD as /BruceJS/Games/PenseBem.js.

var display = require('display');
var keyboard = require('keyboard');
var wifi = require('wifi');
var audio = require('audio');

var API_BASE = 'http://148.230.73.44:18081';
var PROTOCOL = 1;
var CLIENT = 'atari8'; // Wire-protocol name; correctness and scoring stay server-owned.
var WIDTH = display.width();
var HEIGHT = display.height();
var record = 0;

var BLACK = display.color(0, 0, 0);
var DARK = display.color(24, 29, 43);
var CYAN = display.color(82, 199, 245);
var BLUE = display.color(31, 111, 173);
var CREAM = display.color(240, 238, 230);
var GRAY = display.color(125, 132, 145);
var GREEN = display.color(57, 208, 122);
var RED = display.color(244, 80, 80);
var ORANGE = display.color(230, 151, 72);

var JUDGE_HOLD_MS = 1200;
var REVEAL_HOLD_MS = 2600;
var EXPLANATION_HOLD_MS = 2600;

function textWidth(text, size) {
  return String(text).length * 6 * size;
}

function center(text, y, color, size) {
  var value = String(text);
  display.setTextSize(size);
  display.setTextColor(color, BLACK);
  display.drawString(value, Math.max(0, Math.floor((WIDTH - textWidth(value, size)) / 2)), y);
}

function chrome(title, footer) {
  display.fill(BLACK);
  display.drawFillRect(0, 0, WIDTH, 19, CYAN);
  display.setTextSize(1);
  display.setTextColor(CREAM, CYAN);
  display.drawString(title, 4, 5);
  display.drawFillRect(0, HEIGHT - 14, WIDTH, 14, CYAN);
  display.setTextColor(CREAM, CYAN);
  display.drawString(footer, Math.max(3, Math.floor((WIDTH - textWidth(footer, 1)) / 2)), HEIGHT - 11);
}

function truncate(text, limit) {
  var value = String(text || '');
  if (value.length <= limit) return value;
  if (limit < 2) return value.substring(0, limit);
  return value.substring(0, limit - 1) + '~';
}

function wrapText(text, width, maxLines) {
  var words = String(text || '').split(' ');
  var lines = [];
  var line = '';
  for (var i = 0; i < words.length; i++) {
    var word = words[i];
    if (!word) continue;
    if (!line) {
      line = word;
    } else if ((line + ' ' + word).length <= width) {
      line += ' ' + word;
    } else {
      lines.push(truncate(line, width));
      line = word;
      if (lines.length >= maxLines) break;
    }
  }
  if (lines.length < maxLines && line) lines.push(truncate(line, width));
  if (lines.length === 0) lines.push('');
  return lines;
}

function showStatus(title, detail, color) {
  chrome('PENSE BEM  ONLINE', 'ESC cancelar');
  center(title, 43, color, 2);
  center(truncate(detail, 36), 82, CREAM, 1);
}

function showError(title, detail) {
  chrome('PENSE BEM  ONLINE', 'Enter continuar');
  center(title, 39, RED, 2);
  var lines = wrapText(detail, 36, 3);
  for (var i = 0; i < lines.length; i++) center(lines[i], 72 + i * 11, CREAM, 1);
}

function keyWords() {
  var value = keyboard.getKeysPressed();
  return value && value.length ? value : [];
}

function isEnter(words) {
  for (var i = 0; i < words.length; i++) {
    if (words[i] === 'Enter' || words[i] === '\n' || words[i] === '\r') return true;
  }
  return false;
}

function hasLetter(words, letter) {
  var wanted = String(letter).toLowerCase();
  for (var i = 0; i < words.length; i++) {
    if (String(words[i]).toLowerCase() === wanted) return true;
  }
  return false;
}

function wantsExit(words) {
  return keyboard.getEscPress() || hasLetter(words, 'q');
}

function waitEnterOrExit() {
  while (true) {
    var words = keyWords();
    if (wantsExit(words)) return false;
    if (keyboard.getSelPress() || isEnter(words)) return true;
    delay(35);
  }
}

function waitRetry(title, detail) {
  chrome('PENSE BEM  ONLINE', 'Enter repetir  ESC sair');
  center(title, 39, RED, 2);
  var lines = wrapText(detail, 36, 3);
  for (var i = 0; i < lines.length; i++) center(lines[i], 72 + i * 11, CREAM, 1);
  return waitEnterOrExit();
}

function safeTone(freq, duration) {
  try {
    audio.tone(freq, duration, false);
  } catch (error) {
    console.log('pensebem tone: ' + String(error));
  }
}

function playRight() {
  safeTone(1047, 80);
  delay(25);
  safeTone(1568, 140);
}

function playWrong() {
  safeTone(392, 190);
}

function playReveal() {
  safeTone(520, 90);
  delay(45);
  safeTone(392, 180);
}

function playEnding(normalized) {
  if (normalized >= 76) {
    safeTone(784, 90); safeTone(988, 90); safeTone(1175, 110); safeTone(1568, 200);
  } else if (normalized >= 51) {
    safeTone(659, 100); safeTone(784, 100); safeTone(988, 190);
  } else {
    safeTone(523, 110); safeTone(440, 110); safeTone(392, 200);
  }
}

function normalizeCode(value) {
  var code = String(value || '').trim();
  if (code.length !== 3) return null;
  for (var i = 0; i < code.length; i++) {
    var n = code.charCodeAt(i);
    if (n < 48 || n > 57) return null;
  }
  var book = Number(code.substring(0, 2));
  var section = Number(code.substring(2, 3));
  if (book < 1 || book > 99 || section < 1 || section > 6) return null;
  return code;
}

function readCode() {
  while (true) {
    chrome('PENSE BEM  ONLINE', 'Codigo do livro + secao');
    center('CODIGO BBS', 34, CREAM, 2);
    center('Demo online: 991', 72, CYAN, 1);
    center('Enter para digitar', 91, GRAY, 1);
    if (!waitEnterOrExit()) return null;
    var entered = keyboard.numKeyboard('', 3, 'CODIGO BBS - Exemplo: 991', false);
    if (!entered) return null;
    var code = normalizeCode(entered);
    if (code) return code;
    showError('CODIGO INVALIDO', 'Use livro 01-99 e secao 1-6');
    delay(1600);
  }
}

function connectWifi() {
  if (wifi.connected()) return true;
  // Cardputer has no PSRAM. Starting Wi-Fi after the BruceJS interpreter
  // consumes the remaining contiguous DMA block and Bruce refuses the scan.
  // Connect from Bruce first; the saved network can auto-connect on boot.
  showError('SEM WIFI', 'Conecte no menu WiFi do Bruce antes de abrir o jogo');
  delay(3000);
  return false;
}

function makeStartPayload(code) {
  return {code: code, client: CLIENT, protocol: PROTOCOL};
}

function makeAnswerPayload(sessionId, requestId, answer) {
  return {session_id: sessionId, request_id: requestId, answer: answer};
}

function errorDetail(error) {
  if (error && error.message) return String(error.message);
  return String(error || 'erro desconhecido');
}

function serverDetail(response) {
  var body = response ? response.body : null;
  if (body && body.error) {
    if (body.error.message) return String(body.error.message);
    if (body.error.code) return String(body.error.code);
  }
  return 'HTTP ' + String(response ? response.status : '?');
}

function postJSON(url, payload) {
  var response;
  try {
    response = wifi.httpFetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
      responseType: 'json'
    });
  } catch (error) {
    throw {kind: 'network', message: errorDetail(error)};
  }
  if (!response || !response.ok) {
    throw {kind: 'server', message: serverDetail(response)};
  }
  if (!response.body || typeof response.body !== 'object') {
    throw {kind: 'protocol', message: 'Resposta JSON invalida'};
  }
  return response.body;
}

function postWithRetry(url, payload) {
  // Load-bearing: payload is constructed once by the caller and never mutated.
  // Every retry therefore carries the exact same request_id and answer.
  var automaticRetries = 2;
  while (true) {
    try {
      return postJSON(url, payload);
    } catch (error) {
      var kind = error && error.kind ? error.kind : 'network';
      var detail = errorDetail(error);
      if (kind === 'server' || kind === 'protocol') {
        showError(kind === 'server' ? 'ERRO DO SERVIDOR' : 'PROTOCOLO', detail);
        delay(2400);
        return null;
      }
      // Bruce/ESP32 occasionally reports "send payload failed" after the
      // server has already accepted the tiny POST. Retrying the immutable
      // request is safe because the API caches responses by request_id.
      if (automaticRetries > 0) {
        automaticRetries -= 1;
        delay(250);
        continue;
      }
      if (!waitRetry('FALHA DE REDE', detail)) return null;
      automaticRetries = 2;
    }
  }
}

function parseQuestion(value) {
  if (!value || typeof value !== 'object') throw new Error('Pergunta ausente');
  if (!value.options || value.options.length !== 4) throw new Error('Opcoes invalidas');
  if (typeof value.text !== 'string' || !value.text) throw new Error('Texto invalido');
  return {
    number: Number(value.number),
    position: Number(value.position),
    total: Number(value.total),
    attempt: Number(value.attempt),
    text: value.text,
    options: [String(value.options[0]), String(value.options[1]), String(value.options[2]), String(value.options[3])]
  };
}

function drawQuestion(question, score, selected) {
  // The question is the game: use the full 240x135 screen here instead of
  // spending 14 scarce pixels on a persistent help footer.
  display.fill(BLACK);
  display.drawFillRect(0, 0, WIDTH, 19, CYAN);
  display.setTextSize(1);
  display.setTextColor(CREAM, CYAN);
  display.drawString('PENSE BEM  ONLINE', 4, 5);
  display.setTextColor(CREAM, BLACK);
  display.drawString('#' + question.position + '/' + question.total, 4, 22);
  display.setTextColor(ORANGE, BLACK);
  display.drawString('T' + question.attempt, 92, 22);
  display.setTextColor(GREEN, BLACK);
  display.drawString('P' + score, 188, 22);

  var promptSize = question.text.length <= 38 ? 2 : 1;
  var prompt = wrapText(question.text, promptSize === 2 ? 19 : 38, promptSize === 2 ? 2 : 3);
  display.setTextSize(promptSize);
  display.setTextColor(CREAM, BLACK);
  for (var p = 0; p < prompt.length; p++) {
    display.drawString(prompt[p], 5, 31 + p * (promptSize === 2 ? 16 : 10));
  }

  var optionSize = 2;
  for (var o = 0; o < 4; o++) {
    if (question.options[o].length > 16) optionSize = 1;
  }
  var y = 67;
  for (var i = 0; i < 4; i++) {
    var active = i === selected;
    var rowY = y + i * 17;
    display.drawFillRect(4, rowY, WIDTH - 8, 16, active ? BLUE : DARK);
    display.setTextSize(optionSize);
    display.setTextColor(active ? CREAM : GRAY, active ? BLUE : DARK);
    display.drawString(
      String.fromCharCode(65 + i) + ' ' + truncate(question.options[i], optionSize === 2 ? 16 : 32),
      8,
      rowY + (optionSize === 2 ? 0 : 4)
    );
  }
}

function readAnswer(question, score) {
  var selected = 0;
  drawQuestion(question, score, selected);
  while (true) {
    var words = keyWords();
    if (wantsExit(words)) return null;
    for (var i = 0; i < words.length; i++) {
      var key = String(words[i]).toLowerCase();
      if (key === 'a' || key === 'b' || key === 'c' || key === 'd') return key.toUpperCase();
      if (key === ';' || key === ',') {
        selected = (selected + 3) % 4;
        drawQuestion(question, score, selected);
      } else if (key === '.' || key === '/') {
        selected = (selected + 1) % 4;
        drawQuestion(question, score, selected);
      }
    }
    if (keyboard.getPrevPress()) {
      selected = (selected + 3) % 4;
      drawQuestion(question, score, selected);
    } else if (keyboard.getNextPress()) {
      selected = (selected + 1) % 4;
      drawQuestion(question, score, selected);
    } else if (keyboard.getSelPress() || isEnter(words)) {
      return String.fromCharCode(65 + selected);
    }
    delay(35);
  }
}

function showJudgment(title, detail, color) {
  chrome('PENSE BEM  RESPOSTA', 'Proxima pergunta automatica');
  center(title, 38, color, 2);
  var lines = wrapText(detail, 36, 3);
  for (var i = 0; i < lines.length; i++) center(lines[i], 75 + i * 10, CREAM, 1);
}

function showExplanation(response) {
  if (!response || typeof response.explanation !== 'string' || !response.explanation) return;
  chrome('POR QUE?', 'Proxima pergunta automatica');
  var lines = wrapText(response.explanation, 38, 8);
  display.setTextSize(1);
  display.setTextColor(CREAM, BLACK);
  for (var i = 0; i < lines.length && i < 8; i++) display.drawString(lines[i], 5, 24 + i * 11);
  delay(EXPLANATION_HOLD_MS);
}

function normalizedScore(score, total) {
  if (!total || total < 1) return 0;
  return Math.round((score * 100) / (total * 10));
}

function scoreBand(normalized) {
  if (normalized >= 76) return 'OTIMO';
  if (normalized >= 51) return 'MUITO BEM';
  if (normalized >= 26) return 'QUASE LA';
  return 'TENTE MAIS';
}

function showFinal(score, total) {
  var normalized = normalizedScore(score, total);
  if (normalized > record) record = normalized;
  chrome('PENSE BEM  RESULTADO', 'Enter novo jogo  ESC sair');
  center(scoreBand(normalized), 30, CREAM, 2);
  center('PONTOS ' + score + '/' + (total * 10), 65, CREAM, 1);
  center('NOTA   ' + normalized + '/100', 80, CREAM, 1);
  center('RECORDE ' + record, 95, CREAM, 1);
  playEnding(normalized);
  return waitEnterOrExit();
}

function playSession(code) {
  if (!connectWifi()) return false;
  showStatus('CARREGANDO', 'Abrindo livro ' + code, CYAN);
  var startPayload = makeStartPayload(code);
  var started = postWithRetry(API_BASE + '/api/v2/atari/sessions', startPayload);
  if (!started) return false;

  var sessionId = String(started.session_id || '');
  var score = Number(started.score || 0);
  var question = parseQuestion(started.question);
  var total = question.total;
  var requestId = 1;
  // Do not retain a second copy of the first question during later fetches.
  startPayload = null;
  started = null;

  while (true) {
    var answer = readAnswer(question, score);
    if (!answer) return false;
    showStatus('ENVIANDO', 'Conferindo resposta', CYAN);

    // Construct once. A network retry must reuse this exact object/request ID.
    var answerPayload = makeAnswerPayload(sessionId, requestId, answer);
    var response = postWithRetry(API_BASE + '/api/v2/atari/sessions/answer', answerPayload);
    if (!response) return false;
    if (Number(response.request_id) !== requestId || String(response.session_id) !== sessionId) {
      showError('PROTOCOLO', 'Resposta fora de ordem');
      delay(2400);
      return false;
    }
    requestId += 1;
    score = Number(response.score || 0);

    if (response.complete) {
      if (Number(response.points_awarded || 0) > 0) playRight();
      else playReveal();
      showExplanation(response);
      return showFinal(score, total);
    }

    if (response.result === 'correct') {
      playRight();
      showJudgment('CORRETO!', '+' + response.points_awarded + ' pontos', GREEN);
      delay(JUDGE_HOLD_MS);
    } else if (response.result === 'retry') {
      playWrong();
      showJudgment('TENTE DE NOVO', response.message || 'Outra alternativa', RED);
      delay(JUDGE_HOLD_MS);
    } else if (response.result === 'revealed') {
      playReveal();
      showJudgment('RESPOSTA', response.message || 'Confira a resposta', ORANGE);
      delay(REVEAL_HOLD_MS);
    } else {
      showError('PROTOCOLO', 'Resultado desconhecido');
      delay(2400);
      return false;
    }

    showExplanation(response);
    var nextQuestion;
    try {
      nextQuestion = parseQuestion(response.question);
    } catch (error) {
      showError('PROTOCOLO', errorDetail(error));
      delay(2400);
      return false;
    }
    // The response embeds the same question copied above. Release the larger
    // response tree before the next httpFetch on this no-PSRAM target.
    answerPayload = null;
    response = null;
    question = nextQuestion;
  }
}

function main() {
  while (true) {
    var code = readCode();
    if (!code) return;
    var newGame = false;
    try {
      newGame = playSession(code);
    } catch (error) {
      console.log('pensebem fatal: ' + errorDetail(error));
      showError('ERRO INTERNO', errorDetail(error));
      delay(3000);
    }
    if (!newGame) return;
  }
}

if (typeof __PENSE_BEM_TEST__ === 'undefined') main();
