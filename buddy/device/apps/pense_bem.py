# SPDX-License-Identifier: Apache-2.0
"""Pense Bem for the M5Stack Cardputer-Adv.

The screen and launcher patterns follow buddy/device/apps/hello_cardputer.py.
Offline play mirrors the 1988 activity-book toy: enter a BBS code, read the
numbered question in the printed book, and answer A-D on the Cardputer.

The answer-generation constants and algorithm are ported from the
Beerware-licensed reverse-engineering work in lpereira/Pense-Bem and
ehabkost/pensebem. The notice below is retained verbatim:

----------------------------------------------------------------------------
"THE BEER-WARE LICENSE" (Revision 42):
<leandro@tia.mat.br> and <juca@members.fsf.org> wrote this file. As long as
you retain this notice you can do whatever you want with this stuff.  If we
meet some day, and you think this stuff is worth it, you can buy us a beer
in return.
----------------------------------------------------------------------------
"""

import time

import M5
import machine
from hardware import MatrixKeyboard

try:
    import esp32
except ImportError:
    esp32 = None


# Formula constants. These values intentionally live in this file only.
_PB_BOOKS = 99
_PB_QUESTIONS = 150
_PB_PER_SECTION = 30
_PB_PAGE = 5
_PB_SECTIONS = 6
_PB_SHIFT_Q = 14

_PB_SEED = (
    "dbaadcbdaadcbbcbdddbdababdacaccbdababdacaccbdbbcdcdddacaabca"
    "abadbbbcdcdddaccbadbadbbddccbadbadbbdcccbadbabbdabbdabdabccddccddaacdbbddbb"
    "cdcbbbdabdddcdc"
)

_PB_OFFSETS = (
    "2222120230102312311033203231330203022121320233203323333220221221"
    "3030333001011310230031222203003122201303322312111332102302332023"
    "1203303320110120102210033011221231101032132131211313212111330313"
    "2312020303201002313130330231212003233301131332001130130102322321"
    "0010102011332020120022303330020020332303233320232301303322112030"
    "3300013122332303222221130321122201022012130321201023122111120300"
    "3121302132012321130130132223013022030130333312012220221103001133"
    "1003113113123021201011022310330032322123132020333001212020032303"
    "1030222122102303301131030301201212012031321213323020123321303210"
    "013020120331"
)

_PB_LCG_DEFAULT = 0x9E3779B97F4A7C15
_PB_LCG_MULT = 6364136223846793005
_PB_LCG_ADD = 1442695040888963407
_PB_U64_MASK = 0xFFFFFFFFFFFFFFFF

_POINTS = (0, 10, 6, 4)
_BANDS = ("OTIMO", "MUITO BEM", "QUASE LA", "TENTE MAIS")

# Match the proven ESP32 feedback cadence: ordinary judgments move on quickly,
# while a third-miss answer reveal stays up long enough to read.
_JUDGE_HOLD_MS = 1200
_REVEAL_HOLD_MS = 2600
_SPEAKER_VOLUME = 100
_SFX_RIGHT = ((1047, 90), (1568, 160))
_SFX_WRONG = ((520, 280),)
_SFX_REVEAL = ((520, 110), (0, 60), (392, 220))
_END_SONGS = (
    ((523, 140), (659, 140), (784, 140), (1047, 320)),
    ((523, 150), (659, 150), (784, 300)),
    ((440, 170), (523, 170), (440, 300)),
    ((392, 200), (330, 200), (262, 380)),
)

# Display geometry and fixed palette.
_W = 240
_H = 135
_HEADER_H = 20
_CONTENT_Y = 22
_HINT_Y = 117
_BLACK = 0x000000
_ORANGE = 0xCC785C
_CREAM = 0xF0EEE6
_DARK = 0x1F1F1F
_GRAY = 0x777777
_GREEN = 0x37D67A
_RED = 0xFF5C5C

_LCD = M5.Lcd


def _answer_key_for_book(book):
    """Return one book's 150 answers as compact integers 0..3."""
    if book < 1 or book > _PB_BOOKS:
        return None

    pat = bytearray(_PB_QUESTIONS)
    for i in range(_PB_QUESTIONS):
        pat[i] = ord(_PB_SEED[i]) - 97

    popped = 0
    for current_book in range(2, book + 1):
        first = pat[0]
        for q in range(_PB_QUESTIONS):
            shift = 0
            if q % _PB_PER_SECTION == _PB_SHIFT_Q or q == _PB_QUESTIONS - 1:
                shift = ord(_PB_OFFSETS[popped]) - 48
                popped += 1
            prev = first if q == _PB_QUESTIONS - 1 else pat[q + 1]
            pat[q] = (prev + shift) % 4

    return pat


def _questions_for(section, seed):
    if section < 1 or section > _PB_SECTIONS:
        return None
    if section < _PB_SECTIONS:
        first = (section - 1) * _PB_PER_SECTION + 1
        return [first + i for i in range(_PB_PER_SECTION)]

    state = seed & _PB_U64_MASK
    if state == 0:
        state = _PB_LCG_DEFAULT
    questions = []
    for page in range(_PB_QUESTIONS // _PB_PAGE):
        state = (state * _PB_LCG_MULT + _PB_LCG_ADD) & _PB_U64_MASK
        questions.append(page * _PB_PAGE + ((state >> 33) % _PB_PAGE) + 1)
    return questions


def _points_for_attempt(attempt):
    if 1 <= attempt <= 3:
        return _POINTS[attempt]
    return 0


def _normalized_score(raw, count):
    if count <= 0:
        return 0
    if raw < 0:
        raw = 0
    return (raw * 100) // (count * 10)


def _score_band(normalized):
    if normalized >= 76:
        return 0
    if normalized >= 51:
        return 1
    if normalized >= 26:
        return 2
    return 3


def _parse_code(code):
    if len(code) != 3:
        return None
    for ch in code:
        if ch < "0" or ch > "9":
            return None
    book = int(code[:2])
    section = int(code[2])
    if book < 1 or book > _PB_BOOKS:
        return None
    if section < 1 or section > _PB_SECTIONS:
        return None
    return book, section


def _key_char(key):
    if key is None:
        return None
    if isinstance(key, int):
        if key in (0x0A, 0x0D):
            return "\n"
        if key == 0x1B:
            return "\x1b"
        if key in (0x08, 0x7F):
            return "\b"
        if 0x20 <= key <= 0x7E:
            return chr(key)
        return None
    if isinstance(key, str) and key:
        ch = key[0]
        if ch == "\r":
            return "\n"
        return ch
    return None


def _is_exit(ch):
    return ch == "\x1b" or (ch is not None and ch.lower() == "q")


def _set_font():
    try:
        _LCD.setFont(_LCD.FONTS.DejaVu9)
    except Exception as exc:
        print("pense_bem: setFont fallback:", exc)


def _center(text, y, color=_CREAM, size=1, background=_BLACK):
    _LCD.setTextSize(size)
    _LCD.setTextColor(color, background)
    width = _LCD.textWidth(text)
    x = (_W - width) // 2
    if x < 2:
        x = 2
    _LCD.drawString(text, x, y)


def _chrome(title, hint):
    _LCD.fillScreen(_BLACK)
    _LCD.fillRect(0, 0, _W, _HEADER_H, _DARK)
    _LCD.fillRect(0, _HEADER_H, _W, 1, _ORANGE)
    _LCD.setTextSize(1)
    _LCD.setTextColor(_ORANGE, _DARK)
    _LCD.drawString(title, 6, 5)
    _LCD.fillRect(0, _HINT_Y, _W, _H - _HINT_Y, _DARK)
    _center(hint, _HINT_Y + 4, _GRAY, 1, _DARK)


def _next_key(kb):
    kb.tick()
    ch = _key_char(kb.get_key())
    time.sleep_ms(40)
    return ch


def _draw_code(code, error):
    _chrome("PENSE BEM  OFFLINE", "0-9 codigo  Enter iniciar")
    _center("CODIGO DO LIVRO", 34, _GRAY)
    shown = code + "_" * (3 - len(code))
    _center(shown, 55, _ORANGE, 2)
    if error:
        _center(error, 91, _RED)
    else:
        _center("BBS: livro + secao", 91, _CREAM)


def _read_code(kb):
    code = ""
    error = ""
    _draw_code(code, error)
    while True:
        ch = _next_key(kb)
        if ch is None:
            continue
        if _is_exit(ch):
            return None
        if ch == "\b":
            code = code[:-1]
            error = ""
            _draw_code(code, error)
        elif "0" <= ch <= "9":
            if len(code) < 3:
                code += ch
                error = ""
                _draw_code(code, error)
        elif ch == "\n":
            parsed = _parse_code(code)
            if parsed is not None:
                return code, parsed[0], parsed[1]
            error = "CODIGO INVALIDO"
            code = ""
            _draw_code(code, error)


def _draw_question(code, index, question, attempt, raw):
    title = "PENSE BEM  {:02d}/30".format(index + 1)
    _chrome(title, "A B C D responder  Q sair")
    _center("CODIGO {}   PONTOS {}".format(code, raw), 29, _GRAY)
    _center("QUESTAO", 50, _CREAM)
    _center("{:03d}".format(question), 65, _ORANGE, 2)
    _center(
        "TENT {}/3".format(attempt),
        96,
        _GRAY if attempt == 1 else _ORANGE,
    )


def _draw_feedback(message, detail, good):
    _chrome("PENSE BEM", "Proxima automaticamente")
    _center(message, 48, _GREEN if good else _RED, 2)
    _center(detail, 82, _CREAM)


def _play_sfx(notes):
    """Play a short cue; a speaker problem must never stop the game."""
    try:
        for frequency, duration in notes:
            if frequency:
                M5.Speaker.tone(frequency, duration)
            time.sleep_ms(duration)
    except Exception as exc:
        print("pense_bem: sound warning:", exc)


def _hold_feedback(started_ms, hold_ms):
    """Keep feedback visible for a fixed total time, including its sound."""
    elapsed = time.ticks_diff(time.ticks_ms(), started_ms)
    remaining = hold_ms - elapsed
    if remaining > 0:
        time.sleep_ms(remaining)


def _show_feedback(message, detail, good, notes, hold_ms):
    started_ms = time.ticks_ms()
    _draw_feedback(message, detail, good)
    _play_sfx(notes)
    _hold_feedback(started_ms, hold_ms)


def _wait_continue(kb):
    while True:
        ch = _next_key(kb)
        if _is_exit(ch):
            return False
        if ch == "\n":
            return True


def _load_high_score():
    if esp32 is None:
        return 0
    try:
        return esp32.NVS("pensebem").get_i32("high")
    except Exception:
        return 0


def _save_high_score(score):
    if esp32 is None:
        return
    try:
        nvs = esp32.NVS("pensebem")
        nvs.set_i32("high", score)
        nvs.commit()
    except Exception as exc:
        print("pense_bem: high score warning:", exc)


def _draw_score(raw, normalized, high):
    band = _score_band(normalized)
    _chrome("PENSE BEM  RESULTADO", "Enter novo jogo  Q sair")
    _center(_BANDS[band], 31, _ORANGE, 2)
    _center("PONTOS {:03d}/300".format(raw), 65, _CREAM, 2)
    _center("NOTA    {:03d}/100".format(normalized), 91, _CREAM)
    _center("RECORDE {:03d}".format(high), 104, _GRAY)


def _play_offline(kb, code, book, section):
    answers = _answer_key_for_book(book)
    questions = _questions_for(section, time.ticks_ms())
    if answers is None or questions is None:
        return None

    raw = 0
    index = 0
    attempt = 1
    while index < _PB_PER_SECTION:
        question = questions[index]
        _draw_question(code, index, question, attempt, raw)

        while True:
            ch = _next_key(kb)
            if _is_exit(ch):
                return None
            if ch is None:
                continue
            choice = ch.upper()
            if choice < "A" or choice > "D":
                continue
            break

        correct = chr(65 + answers[question - 1])
        if choice == correct:
            points = _points_for_attempt(attempt)
            raw += points
            _show_feedback(
                "CERTO",
                "+{} PONTOS".format(points),
                True,
                _SFX_RIGHT,
                _JUDGE_HOLD_MS,
            )
            index += 1
            attempt = 1
        elif attempt < 3:
            attempt += 1
            _show_feedback(
                "ERRADO",
                "TENTATIVA {} DE 3".format(attempt),
                False,
                _SFX_WRONG,
                _JUDGE_HOLD_MS,
            )
        else:
            _show_feedback(
                "RESPOSTA {}".format(correct),
                "0 PONTOS",
                False,
                _SFX_REVEAL,
                _REVEAL_HOLD_MS,
            )
            index += 1
            attempt = 1

    normalized = _normalized_score(raw, _PB_PER_SECTION)
    high = _load_high_score()
    if normalized > high:
        high = normalized
        _save_high_score(high)
    _draw_score(raw, normalized, high)
    _play_sfx(_END_SONGS[_score_band(normalized)])
    return _wait_continue(kb)


def run():
    try:
        M5.begin()
    except Exception as exc:
        print("pense_bem: M5.begin warning:", exc)
    _set_font()
    try:
        M5.Speaker.setVolume(_SPEAKER_VOLUME)
    except Exception as exc:
        print("pense_bem: speaker volume warning:", exc)

    # The launcher has already allowed the cold-boot settle period. Keep this
    # app-specific delay before constructing MatrixKeyboard; earlier creation
    # can leave get_key() returning None for the process lifetime.
    time.sleep_ms(400)
    kb = MatrixKeyboard()

    try:
        while True:
            selected = _read_code(kb)
            if selected is None:
                return
            again = _play_offline(kb, selected[0], selected[1], selected[2])
            if not again:
                return
    finally:
        try:
            _LCD.fillScreen(_BLACK)
        except Exception as exc:
            print("pense_bem: clear warning:", exc)
        time.sleep_ms(200)
        machine.reset()


run()
