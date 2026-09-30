# SPDX-FileCopyrightText: 2026 Moonshine AI (original C++), Adafruit port
# SPDX-License-Identifier: MIT
"""Phone tokens -> per-frame synth parameters.

Ported from moonshine micro/klatt-tts synth_internal.cc: BuildSegments, AppendStop,
CountFrames, FillParamTracks, FrameAt. Runs once per word. Tracks are array("f") sized up
front from count_frames: 4 bytes a value instead of a boxed float plus a list slot, so a 2 s
word needs about 26 KB instead of about 120 KB, which matters on 192-264 KB boards.
"""

import array
import math

from adafruit_moonshine_klatt import klatt_phonemes as P

FRAME_MS = 5.0
PHRASE_BREAK_MS = 120.0
PRIMARY_STRESS = "ˈ"
SECONDARY_STRESS = "ˌ"

# Segment field indexes
(
    S_DUR,
    S_F1,
    S_F2,
    S_F3,
    S_B1,
    S_B2,
    S_B3,
    S_AV,
    S_AF,
    S_AH,
    S_NASAL,
    S_FNP,
    S_FNZ,
    S_FRIC_CF,
    S_IS_VOWEL,
    S_IS_SILENCE,
    S_MAJOR,
    S_ACCENT,
) = range(18)


def lround(x):
    """C lround: nearest integer, halves away from zero."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def _seg_from_phone(p):
    return [
        float(p[P.DUR]),
        float(p[P.F1]),
        float(p[P.F2]),
        float(p[P.F3]),
        float(p[P.B1]),
        float(p[P.B2]),
        float(p[P.B3]),
        float(p[P.AV]),
        float(p[P.AF]),
        float(p[P.AH]),
        1.0 if p[P.CLS] == P.NASAL else 0.0,
        float(p[P.FNP]),
        float(p[P.FNZ]),
        float(p[P.FRIC_CF]),
        p[P.CLS] == P.VOWEL,
        p[P.CLS] == P.SILENCE,
        False,
        0.0,
    ]


def _append_stop(p, voice, out):
    voiced = p[P.SRC] == P.VOICED

    closure = _seg_from_phone(p)
    closure[S_DUR] = voice.stop_closure_voiced_ms if voiced else voice.stop_closure_voiceless_ms
    closure[S_AF] = 0.0
    closure[S_AH] = 0.0
    closure[S_AV] = voice.stop_closure_av if voiced else 0.0
    closure[S_F1] = voice.stop_closure_f1
    out.append(closure)

    burst = _seg_from_phone(p)
    burst[S_DUR] = voice.stop_burst_ms
    burst[S_AV] = voice.stop_burst_av if voiced else 0.0
    burst[S_AH] = 0.0
    out.append(burst)

    if not voiced:
        asp = _seg_from_phone(p)
        asp[S_DUR] = voice.stop_asp_ms
        asp[S_AV] = 0.0
        asp[S_AF] = 0.0
        asp[S_AH] = float(p[P.AH])
        out.append(asp)


def build_segments(phones, voice):
    """Phone tokens -> list of segments (stop expansion, lead/tail silence, accents)."""
    sil = P.PHONES[" "]
    out = []
    lead = _seg_from_phone(sil)
    lead[S_DUR] = voice.lead_ms
    out.append(lead)

    has_explicit_stress = PRIMARY_STRESS in phones or SECONDARY_STRESS in phones

    pending_accent = 0.0
    word_needs_accent = True
    accents_in_phrase = 0
    for tok in phones:
        if tok == PRIMARY_STRESS:
            pending_accent = 1.0
            continue
        if tok == SECONDARY_STRESS:
            pending_accent = 0.5
            continue
        p = P.PHONES.get(tok)
        if p is None:
            continue

        if p[P.CLS] == P.SILENCE:
            word_needs_accent = True
            s = _seg_from_phone(p)
            s[S_MAJOR] = p[P.DUR] >= PHRASE_BREAK_MS
            if s[S_MAJOR]:
                accents_in_phrase = 0
            out.append(s)
            continue

        accent = 0.0
        if p[P.CLS] == P.VOWEL:
            if has_explicit_stress:
                accent = pending_accent
            elif word_needs_accent:
                accent = 1.0
                word_needs_accent = False
            if accent > 0.0:
                accent *= voice.f0_downstep**accents_in_phrase
                accents_in_phrase += 1
        pending_accent = 0.0

        if p[P.CLS] == P.STOP:
            _append_stop(p, voice, out)
        else:
            s = _seg_from_phone(p)
            s[S_ACCENT] = accent
            out.append(s)

    tail = _seg_from_phone(sil)
    tail[S_DUR] = voice.tail_ms
    out.append(tail)

    for s in out:
        if s[S_IS_VOWEL]:
            s[S_DUR] *= voice.stress_len_scale if s[S_ACCENT] > 0.0 else voice.unstressed_len_scale
    n = len(out)
    for i in range(n):
        if out[i][S_IS_SILENCE]:
            continue
        if i + 1 >= n or out[i + 1][S_IS_SILENCE]:
            out[i][S_DUR] *= voice.prepausal_len_scale
    return out


def _frames_for(seg, dur_scale):
    nf = lround(seg[S_DUR] * dur_scale / FRAME_MS)
    return nf if nf >= 1 else 1


def count_frames(segs, dur_scale):
    return sum(_frames_for(s, dur_scale) for s in segs)


def smooth_bidir(v, tau_ms, n=None):
    if n is None:
        n = len(v)
    if n == 0:
        return
    alpha = math.exp(-FRAME_MS / tau_ms)
    beta = 1.0 - alpha
    # The running value stays in a local instead of being read back from v each step.
    y = v[0]
    for i in range(1, n):
        y = alpha * y + beta * v[i]
        v[i] = y
    for i in range(n - 2, -1, -1):
        y = alpha * y + beta * v[i]
        v[i] = y


def smooth_fwd(v, tau_ms, n=None):
    if n is None:
        n = len(v)
    if n == 0:
        return
    alpha = math.exp(-FRAME_MS / tau_ms)
    beta = 1.0 - alpha
    y = v[0]
    for i in range(1, n):
        y = alpha * y + beta * v[i]
        v[i] = y


def smooth_asym(v, attack_ms, release_ms, n=None):
    if n is None:
        n = len(v)
    if n == 0:
        return
    a_att = math.exp(-FRAME_MS / attack_ms)
    a_rel = math.exp(-FRAME_MS / release_ms)
    y = v[0]
    for i in range(1, n):
        target = v[i]
        a = a_att if target > y else a_rel
        y = a * y + (1.0 - a) * target
        v[i] = y


def new_tracks(nframes):
    """A set of tracks for fill_tracks(out=...) with room for nframes frames."""
    t = {k: array.array("f", [0.0]) * nframes for k in _TRACK_NAMES}
    t["major"] = bytearray(nframes)
    return t


_FLUTTER_FRAMES = 256  # 1.28 s, longer than most words; later frames are computed


def _flutter_at(i, hz):
    """F0 flutter at frame i of a word: three slow sines, Klatt's jitter-free vibrato."""
    if hz <= 0.0:
        return 0.0
    ts = i * (FRAME_MS / 1000.0)
    pi = 3.14159265
    fl = (
        math.sin(2.0 * pi * 12.7 * ts)
        + math.sin(2.0 * pi * 7.1 * ts)
        + math.sin(2.0 * pi * 4.7 * ts)
    )
    return hz * (fl / 3.0)


def _flutter_table(t, hz):
    """_flutter_at for the first _FLUTTER_FRAMES frames, kept in the tracks dict and rebuilt
    only when hz changes. Three sines per frame were a sixth of fill_tracks."""
    if t.get("flutter_hz") != hz:
        tab = t.get("flutter") or array.array("f", [0.0]) * _FLUTTER_FRAMES
        for i in range(len(tab)):
            tab[i] = _flutter_at(i, hz)
        t["flutter"] = tab
        t["flutter_hz"] = hz
    return t["flutter"]


_TRACK_NAMES = (
    "f0",
    "f1",
    "f2",
    "f3",
    "b1",
    "b2",
    "b3",
    "av",
    "af",
    "ah",
    "nasal",
    "fnp",
    "fnz",
    "fric_cf",
    "accent",
)


def fill_tracks(segs, voice, dur_scale, question=False, out=None):
    """Rasterize, smooth, lay down F0 and apply voice scaling.

    Returns a dict of per-frame array("f") tracks: f0 f1 f2 f3 b1 b2 b3 av af ah nasal fnp fnz
    fric_cf accent, and major as a bytearray of 0/1.

    out: tracks from new_tracks() to fill in place instead of allocating, so a caller that
    renders word after word allocates nothing per word. Only the first count_frames() entries
    are meaningful; if out is too small, new tracks are allocated.
    """
    names = (
        "f1",
        "f2",
        "f3",
        "b1",
        "b2",
        "b3",
        "av",
        "af",
        "ah",
        "nasal",
        "fnp",
        "fnz",
        "fric_cf",
        "accent",
    )
    idx = (
        S_F1,
        S_F2,
        S_F3,
        S_B1,
        S_B2,
        S_B3,
        S_AV,
        S_AF,
        S_AH,
        S_NASAL,
        S_FNP,
        S_FNZ,
        S_FRIC_CF,
        S_ACCENT,
    )
    nframes = count_frames(segs, dur_scale)
    t = out if out is not None and len(out["major"]) >= nframes else new_tracks(nframes)
    major = t["major"]
    pos = 0
    for s in segs:
        end = pos + _frames_for(s, dur_scale)
        for k, j in zip(names, idx):
            a = t[k]
            x = s[j]
            for i in range(pos, end):
                a[i] = x
        m = 1 if s[S_MAJOR] else 0
        for i in range(pos, end):
            major[i] = m
        pos = end
    if nframes == 0:
        return t

    n = nframes
    smooth_bidir(t["f1"], voice.formant_smooth_ms, n)
    smooth_bidir(t["f2"], voice.formant_smooth_ms, n)
    smooth_bidir(t["f3"], voice.formant_smooth_ms, n)
    smooth_fwd(t["av"], voice.av_smooth_ms, n)
    smooth_asym(t["af"], voice.af_attack_ms, voice.af_release_ms, n)
    smooth_fwd(t["ah"], voice.ah_smooth_ms, n)
    smooth_bidir(t["nasal"], voice.nasal_smooth_ms, n)
    smooth_bidir(t["accent"], 45.0, n)

    av = t["av"]
    accent = t["accent"]
    f0 = t["f0"]
    denom = float(nframes - 1 if nframes - 1 else 1)
    flutter = _flutter_table(t, voice.f0_flutter_hz)
    nfl = len(flutter)
    f0_start = voice.f0_start
    f0_span = voice.f0_end - voice.f0_start
    f0_end = voice.f0_end
    declination = voice.f0_declination_hz
    rise = voice.f0_question_rise_hz
    fall = voice.final_fall_hz
    accent_hz = voice.f0_accent_hz

    i = 0
    while i < nframes:
        if major[i]:
            f0[i] = f0_end + (flutter[i] if i < nfl else _flutter_at(i, voice.f0_flutter_hz))
            i += 1
            continue
        start = i
        while i < nframes and not major[i]:
            i += 1
        end = i
        length = end - start
        is_last = True
        for m in range(end, nframes):
            if not major[m] and av[m] > 0.0:
                is_last = False
                break
        rising = question and is_last
        for j in range(start, end):
            gfrac = j / denom
            lf = (j - start) / (length - 1) if length > 1 else 0.0
            v = f0_start + f0_span * gfrac
            v -= lf * declination
            if lf > 0.8:
                e = (lf - 0.8) / 0.2
                v += e * rise if rising else -e * fall
            v += flutter[j] if j < nfl else _flutter_at(j, voice.f0_flutter_hz)
            v += accent_hz * accent[j]
            f0[j] = v

    fs = voice.formant_scale
    if fs != 1.0:
        for k in ("f1", "f2", "f3", "fnp", "fnz", "fric_cf"):
            a = t[k]
            for i in range(nframes):
                a[i] *= fs
    if voice.f0_scale != 1.0:
        for i in range(nframes):
            f0[i] *= voice.f0_scale
    return t


def frames_from_tracks(t):
    """List of 14-float frames in klatt_synth.FRAME_FIELDS order."""
    return list(
        zip(
            t["f0"],
            t["f1"],
            t["f2"],
            t["f3"],
            t["b1"],
            t["b2"],
            t["b3"],
            t["av"],
            t["af"],
            t["ah"],
            t["nasal"],
            t["fnp"],
            t["fnz"],
            t["fric_cf"],
        )
    )


def phones_to_frames(phones, voice, speed=1.0, question=False):
    dur_scale = voice.duration_scale * ((1.0 / speed) if speed > 0.01 else 1.0)
    segs = build_segments(phones, voice)
    return frames_from_tracks(fill_tracks(segs, voice, dur_scale, question))
