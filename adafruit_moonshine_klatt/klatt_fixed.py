# SPDX-FileCopyrightText: 2026 Moonshine AI (original C++), Adafruit port
# SPDX-License-Identifier: MIT
"""Per-frame setup for the fixed-point synth in the native klatt_kernel module.

Runs once per 5 ms frame, in floats: filter coefficients, parameter ramps and on/off flags go
into the int32 array the kernel reads. Deviations from the float port (klatt_synth.py),
each measured by tests/check_fixed.py:

- R1-R3 coefficients computed at both frame ends and stepped per sample; R4/R5 once per
  utterance (the C++ recomputes those constants every sample).
- Nasal branch skipped while fnp/fnz are 0 (the pole and zero cancel there in the C++; in
  fixed point the 0 Hz antiresonator gain of ~19,700 overflows). The frame uses the nonzero
  end's frequencies instead of sweeping to 0 Hz.
- Frication band-pass skipped while fric_cf is 0 (the C++ filter has a double pole at DC there
  and drifts). Noise is still drawn so the random sequence stays in step.
"""

import array
import math

from adafruit_moonshine_klatt import klatt_layout as V

try:
    from micropython import const
except ImportError:
    const = lambda x: x  # noqa: E731

# klatt_layout.py slots used per frame, as const() so they compile to literals instead of a
# module attribute lookup each. Keep in step with klatt_layout.py.
_NPY1 = const(15)
_NPY2 = const(16)
_NZX1 = const(17)
_NZX2 = const(18)
_FX1 = const(19)
_FX2 = const(20)
_FY1 = const(21)
_FY2 = const(22)
_OFF = const(23)
_R1A = const(24)
_R2A = const(27)
_R3A = const(30)
_NPA = const(39)
_NPB = const(40)
_NPC = const(41)
_NZB = const(42)
_NZC = const(43)
_NZG = const(44)
_NASAL_ON = const(45)
_FB0 = const(46)
_FA1 = const(47)
_FA2 = const(48)
_FRIC_ON = const(49)
_INC0 = const(50)
_DINC = const(51)
_AV0 = const(52)
_DAV = const(53)
_AV_FROM = const(54)
_AH0 = const(55)
_DAH = const(56)
_AF0 = const(57)
_DAF = const(58)
_AF_FROM = const(59)
_NAS0 = const(60)
_DNAS = const(61)
_NAS_FROM = const(62)
_R_TO_RD = const(42)  # R1AD - R1A, the same for R2 and R3

_PI = math.pi
_N2PI = -2.0 * _PI  # the constant parts of _resonator's expressions, evaluated left to right
_NPI = -_PI
_P2PI = 2.0 * _PI
_exp = math.exp
_cos = math.cos
Q14 = 16384
Q15 = 32768
PHASE_ONE = 1 << 28


def _resonator(freq, bw, t):
    """Q14 a, b, c of a two-pole resonator. t is 1 / sample rate. round() of a float is
    already an int in MicroPython and CPython, so there is no int() around it."""
    c = -_exp(_N2PI * bw * t)
    b = 2.0 * _exp(_NPI * bw * t) * _cos(_P2PI * freq * t)
    bq = round(b * Q14)
    cq = round(c * Q14)
    return Q14 - bq - cq, bq, cq


def _ramp(x0, x1, n, scale):
    """Start value and per-sample step (Q8) for a linear ramp from x0 to x1 over n samples."""
    if x1 == x0:  # most amplitude tracks sit at 0 or hold for several frames
        if x0 == 0.0:
            return 0, 0
        return round(x0 * scale), 0
    return round(x0 * scale), round((x1 - x0) * scale * 256.0 / n)


def _on_from(x0, x1, n):
    """First sample index where the C++ lerp x0 + (x1 - x0) * s / n is > 0."""
    if x0 > 0.0:
        return 0
    if x1 > 0.0:
        return 1
    return n


def _pick(c0, c1, n0, n1):
    """Frequencies for a gated branch: mid-frame if both ends are on, else the nonzero end."""
    if c0 > 0.0 and c1 > 0.0:
        return 0.5 * (n0 + n1), True
    if c0 > 0.0:
        return n0, True
    if c1 > 0.0:
        return n1, True
    return 0.0, False


def _default_kernel():
    try:
        from adafruit_moonshine_klatt import klatt_kernel  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError(
            "klatt_kernel native module not found; needs CircuitPython 11 or later with "
            "native .mpy loading and a klatt_kernel.<arch>.mpy for this chip"
        ) from e
    return klatt_kernel.render_frame


def make_tables(voice, tab=None):
    """Pulse shape and soft-clip tables. Fills tab in place when given."""
    if tab is None:
        tab = array.array("h", bytes(2 * (V.TANH_BASE + 257)))
    op = voice.glottal_open
    cl = voice.glottal_close
    for i in range(V.PULSE_LEN + 1):
        p = i / V.PULSE_LEN
        if p < op:
            g = 0.5 * (1.0 - math.cos(_PI * p / op))
        elif p < op + cl:
            g = math.cos(_PI * (p - op) / (2.0 * cl))
        else:
            g = 0.0
        tab[i] = int(round(g * Q14))
    head = 0.2 * 32767
    for k in range(257):
        e = math.exp(-2.0 * k * 128 / head)  # tanh from exp: no math.tanh on the Fruit Jam
        tab[V.TANH_BASE + k] = int(round(head * (1.0 - e) / (1.0 + e)))
    return tab


class FixedSynth:
    def __init__(self, sample_rate, voice, kernel=None):
        # kernel: a render_frame(st, tab, out, n) with the klatt_layout.py layout. Defaults to
        # the native klatt_kernel module.
        self.kernel = kernel or _default_kernel()
        self.sr = sample_rate
        self.t = 1.0 / sample_rate
        self.tab = None
        self.st = None
        self.set_voice(voice)

    def set_voice(self, voice):
        """Switch to another voice, as if newly created, reusing the table and state arrays.
        A voice change then allocates nothing large, which matters once the caller has taken
        most of the heap."""
        self.voice = voice
        self.tab = make_tables(voice, self.tab)
        st = self.st
        if st is None:
            st = array.array("i", bytes(4 * V.NSLOTS))
        else:
            for k in range(V.NSLOTS):
                st[k] = 0
        st[V.SHIM] = 4096
        st[V.RNG] = 0x1234567
        t = self.t
        st[V.R4A], st[V.R4B], st[V.R4C] = _resonator(voice.f4 * voice.formant_scale, voice.b4, t)
        st[V.R5A], st[V.R5B], st[V.R5C] = _resonator(voice.f5 * voice.formant_scale, voice.b5, t)
        if voice.jitter > 0.0:
            st[V.JIT_K] = max(1, int(round(voice.jitter * 65536)))
        if voice.shimmer > 0.0:
            st[V.SHIM_K] = max(1, int(round(voice.shimmer * 4096)))
        st[V.OUT_G] = int(round(voice.output_gain * 32767))
        st[V.PREEMPH] = int(round(getattr(voice, "preemph", 0.0) * Q14))
        self.st = st
        # R1-R3: freq, bw and a, b, c of the last frame end computed, for render_at to reuse
        self._rc = [[-1.0, -1.0, 0, 0, 0], [-1.0, -1.0, 0, 0, 0], [-1.0, -1.0, 0, 0, 0]]

    def render_frame(self, cur, nxt, n, out, offset):
        """Render one frame from two frame tuples (see _FRAME_FIELDS order in __init__.py)."""
        self.render_at([(c, x) for c, x in zip(cur, nxt)], 0, 1, n, out, offset)

    def render_at(self, tracks, i, j, n, out, offset):
        """Render one frame from frames i (start) and j (end) of per-field tracks, so the hot
        path indexes the array("f") tracks instead of building a list per frame."""
        st = self.st
        t = self.t
        v = self.voice

        # R1-R3 coefficients at both ends of the frame; the loop steps between them per sample
        # (Q22). Frozen per-frame coefficients put a buzz at the 200 Hz frame rate on every vowel.
        # This frame's start is usually the last frame's end, and steady frames have equal ends,
        # so each end reuses coefficients already computed for the same freq and bw.
        rc = self._rc
        for k, fi, bi, ca in ((0, 1, 4, _R1A), (1, 2, 5, _R2A), (2, 3, 6, _R3A)):
            last = rc[k]
            ft = tracks[fi]
            bt = tracks[bi]
            f0 = ft[i]
            w0 = bt[i]
            if f0 == last[0] and w0 == last[1]:
                a0 = last[2]
                b0 = last[3]
                c0 = last[4]
            else:
                a0, b0, c0 = _resonator(f0, w0, t)
            f1 = ft[j]
            w1 = bt[j]
            if f1 == f0 and w1 == w0:
                a1 = a0
                b1 = b0
                c1 = c0
            else:
                a1, b1, c1 = _resonator(f1, w1, t)
            last[0] = f1
            last[1] = w1
            last[2] = a1
            last[3] = b1
            last[4] = c1
            st[ca] = a0 << 8
            st[ca + 1] = b0 << 8
            st[ca + 2] = c0 << 8
            cd = ca + _R_TO_RD
            st[cd] = ((a1 - a0) << 8) // n
            st[cd + 1] = ((b1 - b0) << 8) // n
            st[cd + 2] = ((c1 - c0) << 8) // n

        # Glottal phase increment (Q28 per sample) ramp.
        sr = self.sr
        x = tracks[0]
        st[_INC0], st[_DINC] = _ramp(x[i] / sr, x[j] / sr, n, PHASE_ONE)

        x = tracks[7]
        x0 = x[i]
        x1 = x[j]
        g = v.voice_gain
        st[_AV0], st[_DAV] = _ramp(x0 * g, x1 * g, n, 1024)
        st[_AV_FROM] = _on_from(x0, x1, n)
        x = tracks[9]
        g = v.asp_gain
        st[_AH0], st[_DAH] = _ramp(x[i] * g, x[j] * g, n, Q15)
        x = tracks[8]
        x0 = x[i]
        x1 = x[j]
        g = v.fric_gain
        st[_AF0], st[_DAF] = _ramp(x0 * g, x1 * g, n, Q15)
        st[_AF_FROM] = _on_from(x0, x1, n)
        # On a frame where the nasal pole/zero switch on or off, ramp the blend from or to zero
        # instead of following the amplitude track. The branch's coefficients jump on those frames,
        # and ramping the blend hides the step: measured +2.3 dB worst case above 100 Hz.
        x = tracks[10]
        nas0 = x[i]
        nas1 = x[j]
        x = tracks[12]
        z0 = x[i]
        z1 = x[j]
        if z0 > 0.0 and z1 == 0.0:
            nas1 = 0.0
        elif z0 == 0.0 and z1 > 0.0:
            nas0 = 0.0
        st[_NAS0], st[_DNAS] = _ramp(nas0, nas1, n, Q15)
        st[_NAS_FROM] = _on_from(nas0, nas1, n)

        # Nasal pole/zero, skipped while fnz is 0 at both ends.
        fnz, on = _pick(z0, z1, z0, z1)
        if on:
            x = tracks[11]
            fnp, _ = _pick(z0, z1, x[i], x[j])
            st[_NPA], st[_NPB], st[_NPC] = _resonator(fnp, 100.0, t)
            _, rbq, rcq = _resonator(fnz, 100.0, t)
            st[_NZB] = rbq
            st[_NZC] = rcq
            st[_NZG] = round(1024.0 * Q14 / (Q14 - rbq - rcq))
            st[_NASAL_ON] = 1
        else:
            if st[_NASAL_ON]:
                st[_NPY1] = st[_NPY2] = st[_NZX1] = st[_NZX2] = 0
            st[_NASAL_ON] = 0

        # Frication band-pass (RBJ, constant 0 dB peak), skipped while fric_cf is 0.
        x = tracks[13]
        x0 = x[i]
        x1 = x[j]
        fcf, on = _pick(x0, x1, x0, x1)
        if on:
            w0 = 2.0 * _PI * fcf / sr
            alpha = math.sin(w0) / (2.0 * max(v.fric_q, 0.1))
            a0 = 1.0 + alpha
            st[_FB0] = round(alpha / a0 * Q14)
            st[_FA1] = round(-2.0 * math.cos(w0) / a0 * Q14)
            st[_FA2] = round((1.0 - alpha) / a0 * Q14)
            st[_FRIC_ON] = 1
        else:
            if st[_FRIC_ON]:
                st[_FX1] = st[_FX2] = st[_FY1] = st[_FY2] = 0
            st[_FRIC_ON] = 0

        st[_OFF] = offset
        self.kernel(st, self.tab, out, n)


def render(frames, voice, sample_rate, kernel=None):
    """Frames -> int16 array, with the stream stage's 5 ms fades."""
    spf = max(1, round(sample_rate * 5 / 1000))
    nframes = len(frames)
    total = nframes * spf
    out = array.array("h", bytes(2 * total))
    synth = FixedSynth(sample_rate, voice, kernel)
    for i in range(nframes):
        nxt = frames[i + 1] if i + 1 < nframes else frames[i]
        synth.render_frame(frames[i], nxt, spf, out, i * spf)
    fade = min(total // 2, int(sample_rate * 0.005))
    if fade > 0:
        for gi in range(fade):
            out[gi] = out[gi] * gi // fade
        for gi in range(total - fade, total):
            out[gi] = out[gi] * (total - 1 - gi) // fade
    return out
