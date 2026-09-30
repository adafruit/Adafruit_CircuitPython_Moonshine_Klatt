# SPDX-FileCopyrightText: 2026 Moonshine AI (original C++), Adafruit port
# SPDX-License-Identifier: MIT
"""Layout of the int32 state array `st` and the int16 table `tab` shared by klatt_fixed.py
and the native render_frame kernel. Copied from src/klatt_viper.py; plain ints so it
imports without the micropython module."""

# Layout of the int32 state/coefficient array `st`, shared with klatt_fixed.py.
PHASE = 0
PREV_G = 1
JIT = 2
SHIM = 3
RNG = 4
R1Y1 = 5
R1Y2 = 6
R2Y1 = 7
R2Y2 = 8
R3Y1 = 9
R3Y2 = 10
R4Y1 = 11
R4Y2 = 12
R5Y1 = 13
R5Y2 = 14
NPY1 = 15
NPY2 = 16
NZX1 = 17
NZX2 = 18
FX1 = 19
FX2 = 20
FY1 = 21
FY2 = 22
OFF = 23
R1A = 24
R1B = 25
R1C = 26
R2A = 27
R2B = 28
R2C = 29
R3A = 30
R3B = 31
R3C = 32
R4A = 33
R4B = 34
R4C = 35
R5A = 36
R5B = 37
R5C = 38
NPA = 39
NPB = 40
NPC = 41
NZB = 42
NZC = 43
NZG = 44
NASAL_ON = 45
FB0 = 46
FA1 = 47
FA2 = 48
FRIC_ON = 49
INC0 = 50
DINC = 51
AV0 = 52
DAV = 53
AV_FROM = 54
AH0 = 55
DAH = 56
AF0 = 57
DAF = 58
AF_FROM = 59
NAS0 = 60
DNAS = 61
NAS_FROM = 62
JIT_K = 63
SHIM_K = 64
OUT_G = 65
# Per-sample steps for the R1-R3 coefficients, Q22. Holding coefficients constant across a 5 ms
# frame puts a buzz at the 200 Hz frame rate, 32 dB under the voice on every vowel; stepping them
# removes it and recovers 12.9 dB. a = Q14 - b - c stays true at every sample, so the DC gain of
# each resonator is still exactly 1.
R1AD = 66
R1BD = 67
R1CD = 68
R2AD = 69
R2BD = 70
R2CD = 71
R3AD = 72
R3BD = 73
R3CD = 74
# One-zero pre-emphasis on the output, y - k*y[n-1], Q14. Our fricatives measured 11 dB below
# where natural speech puts them relative to vowels, and the voice source has no spectral tilt
# (Klatt and Klatt measured 8 dB for a normal male voice, we had 0).
PREEMPH = 75
PE_Y1 = 76
NSLOTS = 77

# Layout of the int16 table array `tab`.
PULSE_LEN = 4096  # pulse shape, PULSE_LEN + 1 entries, Q14
TANH_BASE = 4097  # soft-clip curve above the knee, 257 entries
