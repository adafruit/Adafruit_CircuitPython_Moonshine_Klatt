# SPDX-FileCopyrightText: 2026 Moonshine AI (original C++), Adafruit port
# SPDX-License-Identifier: MIT
"""Fixed-point Klatt per-sample loop as one @micropython.viper function.

Port of the per-sample body of klatt.cc RenderFrame. Filter coefficients and parameter ramps
are prepared once per frame by klatt_fixed.py and passed in the int32 array `st`, which also
holds the filter state between frames. Viper only speeds up integer code, so everything here
is int:

- samples Q12 (1.0 = 4096), filter coefficients Q14, amplitudes Q15 (Q10 for voicing)
- glottal phase Q28, pulse shape and soft-clip curve from int16 tables in `tab`
- xorshift32 noise, same seed and draw order as the C++

Calls between viper functions go through the runtime, so the filters are written out inline.
Compile with: mpy-cross -march=armv7emsp klatt_viper.py
"""

import micropython
from micropython import const

# Layout of the int32 state/coefficient array `st`, shared with klatt_fixed.py.
PHASE = const(0)
PREV_G = const(1)
JIT = const(2)
SHIM = const(3)
RNG = const(4)
R1Y1 = const(5)
R1Y2 = const(6)
R2Y1 = const(7)
R2Y2 = const(8)
R3Y1 = const(9)
R3Y2 = const(10)
R4Y1 = const(11)
R4Y2 = const(12)
R5Y1 = const(13)
R5Y2 = const(14)
NPY1 = const(15)
NPY2 = const(16)
NZX1 = const(17)
NZX2 = const(18)
FX1 = const(19)
FX2 = const(20)
FY1 = const(21)
FY2 = const(22)
OFF = const(23)
R1A = const(24)
R1B = const(25)
R1C = const(26)
R2A = const(27)
R2B = const(28)
R2C = const(29)
R3A = const(30)
R3B = const(31)
R3C = const(32)
R4A = const(33)
R4B = const(34)
R4C = const(35)
R5A = const(36)
R5B = const(37)
R5C = const(38)
NPA = const(39)
NPB = const(40)
NPC = const(41)
NZB = const(42)
NZC = const(43)
NZG = const(44)
NASAL_ON = const(45)
FB0 = const(46)
FA1 = const(47)
FA2 = const(48)
FRIC_ON = const(49)
INC0 = const(50)
DINC = const(51)
AV0 = const(52)
DAV = const(53)
AV_FROM = const(54)
AH0 = const(55)
DAH = const(56)
AF0 = const(57)
DAF = const(58)
AF_FROM = const(59)
NAS0 = const(60)
DNAS = const(61)
NAS_FROM = const(62)
JIT_K = const(63)
SHIM_K = const(64)
OUT_G = const(65)
# Per-sample steps for the R1-R3 coefficients, Q22. Holding coefficients constant across a 5 ms
# frame puts a buzz at the 200 Hz frame rate, 32 dB under the voice on every vowel; stepping them
# removes it and recovers 12.9 dB. a = Q14 - b - c stays true at every sample, so the DC gain of
# each resonator is still exactly 1.
R1AD = const(66)
R1BD = const(67)
R1CD = const(68)
R2AD = const(69)
R2BD = const(70)
R2CD = const(71)
R3AD = const(72)
R3BD = const(73)
R3CD = const(74)
# One-zero pre-emphasis on the output, y - k*y[n-1], Q14. Our fricatives measured 11 dB below
# where natural speech puts them relative to vowels, and the voice source has no spectral tilt
# (Klatt and Klatt measured 8 dB for a normal male voice, we had 0).
PREEMPH = const(75)
PE_Y1 = const(76)
NSLOTS = const(77)

# Layout of the int16 table array `tab`.
PULSE_LEN = const(4096)  # pulse shape, PULSE_LEN + 1 entries, Q14
TANH_BASE = const(4097)  # soft-clip curve above the knee, 257 entries


@micropython.viper
def render_frame(st: ptr32, tab: ptr16, out: ptr16, n: int) -> int:
    phase = int(st[PHASE])
    prev_g = int(st[PREV_G])
    jit = int(st[JIT])
    shim = int(st[SHIM])
    r = int(st[RNG])
    r1y1 = int(st[R1Y1])
    r1y2 = int(st[R1Y2])
    r2y1 = int(st[R2Y1])
    r2y2 = int(st[R2Y2])
    r3y1 = int(st[R3Y1])
    r3y2 = int(st[R3Y2])
    r4y1 = int(st[R4Y1])
    r4y2 = int(st[R4Y2])
    r5y1 = int(st[R5Y1])
    r5y2 = int(st[R5Y2])
    npy1 = int(st[NPY1])
    npy2 = int(st[NPY2])
    nzx1 = int(st[NZX1])
    nzx2 = int(st[NZX2])
    fx1 = int(st[FX1])
    fx2 = int(st[FX2])
    fy1 = int(st[FY1])
    fy2 = int(st[FY2])
    off = int(st[OFF])
    r1a = int(st[R1A])
    r1b = int(st[R1B])
    r1c = int(st[R1C])
    r2a = int(st[R2A])
    r2b = int(st[R2B])
    r2c = int(st[R2C])
    r3a = int(st[R3A])
    r3b = int(st[R3B])
    r3c = int(st[R3C])
    r4a = int(st[R4A])
    r4b = int(st[R4B])
    r4c = int(st[R4C])
    r5a = int(st[R5A])
    r5b = int(st[R5B])
    r5c = int(st[R5C])
    r1ad = int(st[R1AD])
    r1bd = int(st[R1BD])
    r1cd = int(st[R1CD])
    r2ad = int(st[R2AD])
    r2bd = int(st[R2BD])
    r2cd = int(st[R2CD])
    r3ad = int(st[R3AD])
    r3bd = int(st[R3BD])
    r3cd = int(st[R3CD])
    npa = int(st[NPA])
    npb = int(st[NPB])
    npc = int(st[NPC])
    nzb = int(st[NZB])
    nzc = int(st[NZC])
    nzg = int(st[NZG])
    nasal_on = int(st[NASAL_ON])
    fb0 = int(st[FB0])
    fa1 = int(st[FA1])
    fa2 = int(st[FA2])
    fric_on = int(st[FRIC_ON])
    inc0 = int(st[INC0])
    dinc = int(st[DINC])
    av0 = int(st[AV0])
    dav = int(st[DAV])
    av_from = int(st[AV_FROM])
    ah0 = int(st[AH0])
    dah = int(st[DAH])
    af0 = int(st[AF0])
    daf = int(st[DAF])
    af_from = int(st[AF_FROM])
    nas0 = int(st[NAS0])
    dnas = int(st[DNAS])
    nas_from = int(st[NAS_FROM])
    jit_k = int(st[JIT_K])
    shim_k = int(st[SHIM_K])
    out_g = int(st[OUT_G])
    preemph = int(st[PREEMPH])
    pe_y1 = int(st[PE_Y1])

    s = 0
    while s < n:
        # Glottal source: Rosenberg pulse from the table, differentiated.
        voiced = 0
        if s >= av_from:
            inc = inc0 + ((dinc * s) >> 8)
            phase += inc + (((inc >> 4) * jit) >> 12)
            if phase >= 268435456:
                phase -= 268435456
                if jit_k != 0:
                    r = r ^ (r << 13)
                    r = r ^ int(uint(r) >> 17)
                    r = r ^ (r << 5)
                    jit = (jit_k * (int(uint(r) >> 19) - 4096)) >> 12
                if shim_k != 0:
                    r = r ^ (r << 13)
                    r = r ^ int(uint(r) >> 17)
                    r = r ^ (r << 5)
                    shim = 4096 + ((shim_k * (int(uint(r) >> 19) - 4096)) >> 12)
            i = phase >> 16
            g0 = int(tab[i])
            g = g0 + (((int(tab[i + 1]) - g0) * ((phase >> 6) & 1023)) >> 10)
            exc = g - prev_g
            prev_g = g
            voiced = (((exc * (av0 + ((dav * s) >> 8))) >> 12) * shim) >> 12
        else:
            prev_g = 0

        # Aspiration: one noise draw every sample, as in the C++.
        r = r ^ (r << 13)
        r = r ^ int(uint(r) >> 17)
        r = r ^ (r << 5)
        casc = voiced + (((int(uint(r) >> 19) - 4096) * (ah0 + ((dah * s) >> 8))) >> 15)

        # Nasal branch: antiresonator (Q12 numerator, Q10 gain) then pole, blended by nasal.
        if s >= nas_from:
            if nasal_on != 0:
                nz = (((casc << 14) - nzb * nzx1 - nzc * nzx2 + 8192) >> 14) * nzg >> 10
                nzx2 = nzx1
                nzx1 = casc
                nq = (npa * nz + npb * npy1 + npc * npy2 + 8192) >> 14
                npy2 = npy1
                npy1 = nq
                casc = casc + (((nas0 + ((dnas * s) >> 8)) * (nq - casc)) >> 15)

        # Cascade R1-R5.
        y = ((r1a >> 8) * casc + (r1b >> 8) * r1y1 + (r1c >> 8) * r1y2 + 8192) >> 14
        r1y2 = r1y1
        r1y1 = y
        r1a += r1ad
        r1b += r1bd
        r1c += r1cd
        y = ((r2a >> 8) * y + (r2b >> 8) * r2y1 + (r2c >> 8) * r2y2 + 8192) >> 14
        r2y2 = r2y1
        r2y1 = y
        r2a += r2ad
        r2b += r2bd
        r2c += r2cd
        y = ((r3a >> 8) * y + (r3b >> 8) * r3y1 + (r3c >> 8) * r3y2 + 8192) >> 14
        r3y2 = r3y1
        r3y1 = y
        r3a += r3ad
        r3b += r3bd
        r3c += r3cd
        y = (r4a * y + r4b * r4y1 + r4c * r4y2 + 8192) >> 14
        r4y2 = r4y1
        r4y1 = y
        y = (r5a * y + r5b * r5y1 + r5c * r5y2 + 8192) >> 14
        r5y2 = r5y1
        r5y1 = y

        # Frication: band-passed noise, one draw per sample while af > 0.
        if s >= af_from:
            r = r ^ (r << 13)
            r = r ^ int(uint(r) >> 17)
            r = r ^ (r << 5)
            if fric_on != 0:
                fx = int(uint(r) >> 19) - 4096
                fy = (fb0 * (fx - fx2) - fa1 * fy1 - fa2 * fy2 + 8192) >> 14
                fx2 = fx1
                fx1 = fx
                fy2 = fy1
                fy1 = fy
                y += (fy * (af0 + ((daf * s) >> 8))) >> 15

        # Pre-emphasis, then the stream stage: output gain to int16, soft clip above the 0.8 knee.
        if preemph != 0:
            pe = y - ((preemph * pe_y1) >> 14)
            pe_y1 = y
            y = pe
        v = (y * out_g) >> 12
        a = v
        if v < 0:
            a = 0 - v
        if a > 26214:
            e = a - 26214
            k = e >> 7
            if k >= 256:
                a = 32767
            else:
                t0 = int(tab[TANH_BASE + k])
                a = 26214 + t0 + (((int(tab[TANH_BASE + k + 1]) - t0) * (e & 127)) >> 7)
            if v < 0:
                v = 0 - a
            else:
                v = a
        out[off + s] = v
        s += 1

    st[PHASE] = phase
    st[PREV_G] = prev_g
    st[JIT] = jit
    st[SHIM] = shim
    st[RNG] = r
    st[R1Y1] = r1y1
    st[R1Y2] = r1y2
    st[R2Y1] = r2y1
    st[R2Y2] = r2y2
    st[R3Y1] = r3y1
    st[R3Y2] = r3y2
    st[R4Y1] = r4y1
    st[R4Y2] = r4y2
    st[R5Y1] = r5y1
    st[R5Y2] = r5y2
    st[NPY1] = npy1
    st[NPY2] = npy2
    st[NZX1] = nzx1
    st[NZX2] = nzx2
    st[FX1] = fx1
    st[FX2] = fx2
    st[FY1] = fy1
    st[FY2] = fy2
    st[PE_Y1] = pe_y1
    return n
