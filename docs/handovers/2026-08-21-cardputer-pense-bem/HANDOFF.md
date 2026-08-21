---
date: 2026-08-21
status: online-preview-physically-verified
canonical_repo: https://github.com/fcavalcantirj/pense-bem-cardputer
canonical_branch: main
implementation_commit: 24ec57f98db586aabf556f47e72832353f63a796
---

# Cardputer Pense Bem — complete session handoff

This is the restart document. It records the final state after the UIFlow2
offline build, the move back to official Bruce, the BruceJS online proof, API
deployment/debugging, repository cleanup, commits, and physical testing.

## Where the work lives

| Purpose | GitHub | Local checkout |
|---|---|---|
| Cardputer product, flashing tools, UIFlow2 app, BruceJS app | `fcavalcantirj/pense-bem-cardputer` (public fork of `moremas/build-with-claude`) | `/Users/fcavalcanti/dev/felipe/build-with-claude` |
| Go API, content store, sessions, explanations | `fcavalcantirj/pense-bem-samuca` (private) | `/Users/fcavalcanti/dev/felipe/pense-bem-samuca` |
| Atari 8-bit/FujiNet client | `fcavalcantirj/pense-bem-atari` (private) | `/Users/fcavalcanti/dev/felipe/pense-bem-atari` |
| Formula evidence and prior hardware lessons | existing ESP32 repository | `/Users/fcavalcanti/dev/felipe/pense-bem-esp32` (reference-only) |

The Cardputer local directory still has its historical name
`build-with-claude`; only its GitHub repository and `origin` were renamed. Do
not reclone unless desired—the checkout is current and tracks
`https://github.com/fcavalcantirj/pense-bem-cardputer.git`.

## What physically works

### Offline UIFlow2

- A full 30-question section completed at 296/300, normalized to 98/100 and
  displayed `OTIMO`.
- Formula verification passed all 1,020 fixture rows before device delivery.
- Correct and wrong cues were physically accepted at speaker volume 100.
- The result photo is `docs/images/pense-bem-cardputer-result.jpeg`.

### Online BruceJS preview

- Official Bruce 1.16.1 is installed and must remain available.
- The accepted file is `/BruceJS/Games/PenseBemOnline.js`, 7,466 bytes including
  its final newline.
- Code `991` starts a server session, displays a large question and four large
  options, accepts arrows/Enter, submits a correct answer, and advances.
- Samuca logs showed both `POST /api/v2/atari/sessions` and
  `POST /api/v2/atari/sessions/answer` during the accepted run.
- The answer payload is immutable across retries. Every retry reuses the same
  `request_id`; the server caches that response, preventing duplicate score or
  local advancement.

The current `991` questions are public-safe arithmetic transport scaffolding,
not the desired final question set.

## Device menu state

The device was deliberately cleaned after acceptance:

```text
/BruceJS/Games/PenseBemOnline.js
```

All numbered builds (`V2/V3/V4`), `Large*` builds, the original 15 KB build,
and the three Pense Bem network probes were removed. The diagnostics directory
contains no Pense Bem files.

The intended final Games menu contains exactly:

```text
PenseBemOffline.js
PenseBemOnline.js
```

`PenseBemOffline.js` does not exist yet. The accepted offline implementation is
still the UIFlow2 Python app. Do not rename an old online experiment to fill the
slot; build and physically verify a real BruceJS offline port first.

## Mandatory Bruce startup order

The Cardputer-Adv has no PSRAM. After a cold boot:

1. Start/connect Wi-Fi from Bruce and wait for confirmation.
2. Only then open the JS Interpreter and launch `PenseBemOnline.js`.

Starting JavaScript first consumes the contiguous block Bruce needs for its
Wi-Fi scan. Starting Wi-Fi first leaves a tight but workable interpreter budget.
The accepted launch measured:

```text
after JS context: 49,856 bytes internal RAM free
largest allocatable block: 31,732 bytes
```

A 7,914-byte V2 crossed the practical limit and displayed Bruce's native
`out of memory` page before the first session POST. The working V3 reduced the
installed code to 7,466 bytes and released duplicate response/question trees
between requests.

## Build and install the accepted online source

Readable source:

```text
buddy/brucejs/Games/PenseBem.js
```

Host test:

```bash
node buddy/tests/test_pense_bem_brucejs.mjs
```

Minify with the MicroQuickJS-safe catch-scope settings:

```bash
npx terser buddy/brucejs/Games/PenseBem.js \
  --ecma 5 --compress passes=3,ecma=5 \
  --mangle "toplevel,safari10" \
  --format "ecma=5,safari10" --comments false \
  --output /tmp/PenseBemOnline.js
```

Install while Bruce is at its menu, not while the interpreter is running:

```bash
python buddy/scripts/install_brucejs.py \
  --port /dev/cu.usbmodem1101 \
  --source /tmp/PenseBemOnline.js \
  --dest /BruceJS/Games/PenseBemOnline.js
```

The installer paces 128-byte chunks and verifies the remote byte count. Bruce
1.16.1 cannot MD5 files over 4,096 bytes because its command uses
`readSmallFile`; do not interpret that limitation as an upload failure.

## API and transport state

The online app is a presentation client. Samuca owns question content,
correctness, attempts, 10/6/4 scoring, progression, and optional Portuguese
explanations. The client intentionally sends wire name `client: "atari8"`.

BruceJS could not establish the deployed TLS connection within this heap. With
explicit user approval, the EasyPanel Docker Swarm service currently publishes
plain HTTP host port 18081 to container port 8080. HTTPS remains active for
capable clients. The HTTP port carries public gameplay and opaque session IDs,
not credentials or personal data, but interception/tampering is possible.

The port was added directly to the Swarm service and may be lost if EasyPanel
reconciles the service. Make it durable in deployment configuration or replace
it with a viable low-memory secure transport.

The Samuca feature branch adds a bounded optional `explanation` field (maximum
320 UTF-8 bytes) to SQLite questions and correct/revealed answer responses. Its
Go tests pass, but the production response inspected during the hardware run
did not yet contain `explanation`; deploy and smoke-test before claiming it live.

Never publish the ignored Samuca `data/` directory, historical PDFs, OCR crops,
credentials, tokens, Wi-Fi settings, or private catalog content.

## Incorrect paths—do not repeat

1. UIFlow boot option `2` performs network setup before the custom launcher and
   reproduced dead keyboard input. The launcher requires boot option `0`.
2. A retained LCD framebuffer is not evidence that the launcher loop is alive.
3. Repeated Ctrl-C, DTR/RTS, and esptool probes disturbed USB/runtime state and
   created symptoms instead of diagnosing them.
4. Resetting in an app `finally` block hid exceptions as instant menu returns.
5. UIFlow had initialized NimBLE for Claude Buddy. `BLE.active(False)` did not
   return the ESP-IDF heap needed by `requests2` TLS. Wi-Fi could associate while
   every session POST still failed before reaching Samuca.
6. Re-entering Wi-Fi credentials, improvised sockets, reset loops, and reflashes
   did not address that heap root cause.
7. BruceJS `numKeyboard` uses its first argument as initial text, not a title.
   Pre-filling `CODIGO BBS` overflowed a three-character field and looked like a
   dead keyboard.
8. Bruce serial writes can truncate one-line JavaScript while still printing
   `File written`; use pacing and remote-size verification.
9. Default Terser catch-variable mangling produced syntax MicroQuickJS rejected.
   Preserve both `safari10` flags shown above.
10. Starting Wi-Fi from inside an already-running JS app fails the no-PSRAM
    guard. Connect from Bruce before launching the app.
11. BruceJS HTTPS failed from memory pressure even when GET/health tests on the
    host succeeded. Server logs with no POST proved a pre-server failure.
12. A correct-answer POST can reach Samuca before Bruce reports a transient send
    error. Retrying the same request ID is the correct recovery; creating a new
    ID or advancing locally is a scoring bug.

## Repository state at handoff

- Public Cardputer implementation commit before this handoff document:
  `24ec57f98db586aabf556f47e72832353f63a796`.
- Public tag: `cardputer-pense-bem-online-preview-v1`.
- Private Atari `main` and `feat/online-atari-client`:
  `4e65b4ea48075bfd6c0acc63045cae58e65f2e5a`.
- Private Samuca `main` and `feat/online-atari-cardputer-api`:
  `103640c4e828a090ae34427b30f847baf8795510`.
- Samuca still has unrelated local changes in `frontend/styles.css` and
  `frontend/test/styles.test.js`; they were intentionally not staged or altered.

Verification completed before publication:

```text
UIFlow boot/protocol tests: pass
formula fixtures: 1020/1020
BruceJS protocol/retry/secrets test: pass
Samuca go test ./... -cover: pass
Atari make test: pass
Atari make mock: pass
Atari make online: pass
```

The Atari online build originally failed because a 256-byte automatic query
buffer exceeded cc65's 6502 stack-frame limit and the `PB_API_BASE` macro was
over-escaped. The buffer is now fixed-capacity static scratch storage and the
Makefile passes a valid quoted string macro.

## Solvr record

The public problem and approach were updated with the full failure tree and
marked succeeded:

```text
problem: 83656c92-b68a-4f57-a9fd-fab4447e5385
approach: 79958257-0313-4ae5-a2c8-705effd82748
```

## Resume priorities

1. Replace arithmetic `991` scaffolding with the intended legally
   distributable, Atari-ready questions. This is the user's top content request.
2. Deploy and verify Portuguese explanations in production.
3. Redesign BruceJS correct/wrong/end audio on physical hardware; the current
   Bruce cues were rejected as sounding horrible. UIFlow's accepted sound is a
   reference, but Bruce follows its own global volume/tone path.
4. Implement and physically validate `PenseBemOffline.js`; then place exactly
   the offline and online files on the purchased SD card while keeping Bruce OS.
5. Complete a 30-question online run and disconnect during one answer POST to
   prove retry without duplicate score or skipped questions.
6. Make the Cardputer HTTP ingress durable or replace it with secure transport.

Do not start tomorrow by reflashing, re-entering Wi-Fi credentials, or reviving
the discarded experimental files. Begin from the accepted online source,
server content, and the six priorities above.
