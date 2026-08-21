# Pense Bem for Bruce

`Games/PenseBem.js` is the readable source for the Cardputer-Adv online client.
Its minified device filename is `PenseBemOnline.js`. It runs inside the full Bruce
JavaScript interpreter, so Bruce remains the installed firmware and the game
lives on removable storage.

## Install

Use Bruce 1.16.1 or newer (the full `Bruce-m5stack-cardputer.bin`, not a
`LAUNCHER_`/lite build), then copy:

```text
/BruceJS/Games/PenseBemOnline.js
```

Bruce discovers the file under **Others → JS Interpreter → Games**. The same
file can be installed to LittleFS for development with:

```bash
python buddy/scripts/install_brucejs.py \
  --port /dev/cu.usbmodem1101 \
  --source buddy/brucejs/Games/PenseBem.js \
  --dest /BruceJS/Games/PenseBemOnline.js \
  --run
```

The serial installer paces 128-byte chunks and verifies the remote byte count.
Bruce 1.16.1 can additionally verify MD5 for files up to 4,096 bytes; larger
files use the exact remote size because Bruce's own `storage md5` path cannot
read them.

## Cardputer-Adv startup and memory

The Cardputer-Adv has no PSRAM. Use this order after a cold boot:

1. Connect the saved network from Bruce (`wifi on`).
2. Wait for `Connected to: ...`.
3. Launch `PenseBemOnline.js`.

Starting JavaScript first leaves too little contiguous memory for Bruce's Wi-Fi
scan. The physically accepted build is 7,466 bytes on device and created its
JavaScript context with 49,856 bytes free internal RAM and a 31,732-byte largest
block. A 7,914-byte experiment crossed the practical parser/runtime threshold
and failed with Bruce's native `out of memory` screen.

Build the compact, MicroQuickJS-compatible file with:

```bash
npx terser buddy/brucejs/Games/PenseBem.js \
  --ecma 5 --compress passes=3,ecma=5 \
  --mangle "toplevel,safari10" \
  --format "ecma=5,safari10" --comments false \
  --output /tmp/PenseBemOnline.js
```

The `safari10` catch-variable handling is required: default Terser mangling can
produce catch scopes rejected by MicroQuickJS.

## Runtime contract

- Wi-Fi is selected through Bruce; credentials are never embedded in the app.
- Correctness, attempts, progression, and 10/6/4 scoring are server-owned.
- A failed answer submission retries the same object and `request_id`.
- The public client contains no historical catalog data or answer constants.
- Portuguese explanations are optional server fields and appear only after a
  correct answer or third-attempt reveal.
- Two automatic transport retries reuse the exact immutable answer payload.
- The large question screen uses 2x text for bounded short content and a 1x
  fallback for longer prompts/options.

BruceJS cannot establish the deployed TLS connection inside this RAM envelope.
The accepted hardware proof uses the dedicated plain-HTTP gameplay port. This
contains no credentials or personal data, but it is vulnerable to interception
and modification and should be replaced if a viable low-memory TLS path is
found.

The production demo activity is code `991`.

## Known follow-up

- The current `991` catalog is public-safe arithmetic scaffolding, not the final
  desired question set.
- The current BruceJS tones were rejected in physical testing and need a
  dedicated sound pass.
- The online record is in-memory only to preserve the working heap margin.
- `PenseBemOffline.js` is not built yet. When it is accepted, the device should
  contain exactly `PenseBemOffline.js` and `PenseBemOnline.js`; diagnostic and
  numbered experiment files do not belong in the final Games menu.
