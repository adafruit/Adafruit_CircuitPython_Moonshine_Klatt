# SPDX-FileCopyrightText: 2026 Moonshine AI (original C++), Adafruit port
# SPDX-License-Identifier: MIT
"""English phone table, ported from moonshine micro/klatt-tts phonemes.cc.

Adult-male reference values from standard phonetics tables (Peterson-Barney vowels,
Klatt locus theory), tuned by ear upstream. Keyed by IPA base-phone token.
"""

# Phone classes
VOWEL = 0
NASAL = 1
STOP = 2
FRICATIVE = 3
APPROXIMANT = 4
LATERAL = 5
SILENCE = 6

# Sources
VOICED = 0
VOICELESS = 1
MIXED = 2
QUIET = 3

# Field indexes into a phone tuple
CLS, SRC, F1, F2, F3, B1, B2, B3, DUR, FNP, FNZ, FRIC_CF, AV, AF, AH = range(15)

_BV1, _BV2, _BV3 = 60.0, 90.0, 150.0  # vowels
_BN1, _BN3 = 120.0, 300.0  # nasals (b2 is per place)
_BC1, _BC2, _BC3 = 100.0, 150.0, 220.0  # consonants

# ipa: (cls, src, f1, f2, f3, b1, b2, b3, dur_ms, fnp, fnz, fric_cf, av, af, ah)
PHONES = {
    # Vowels
    "i": (VOWEL, VOICED, 270, 2290, 3010, _BV1, _BV2, _BV3, 130, 0, 0, 0, 1.0, 0, 0),
    "ɪ": (VOWEL, VOICED, 383, 2140, 2550, _BV1, _BV2, _BV3, 90, 0, 0, 0, 1.0, 0, 0),  # ɪ
    "e": (VOWEL, VOICED, 460, 1990, 2530, _BV1, _BV2, _BV3, 120, 0, 0, 0, 1.0, 0, 0),
    "ɛ": (VOWEL, VOICED, 528, 1784, 2480, _BV1, _BV2, _BV3, 110, 0, 0, 0, 1.0, 0, 0),  # ɛ
    "æ": (VOWEL, VOICED, 722, 1822, 2410, _BV1, _BV2, _BV3, 150, 0, 0, 0, 1.0, 0, 0),  # æ
    "ɑ": (VOWEL, VOICED, 747, 994, 2440, _BV1, _BV2, _BV3, 150, 0, 0, 0, 1.0, 0, 0),  # ɑ
    "ɔ": (VOWEL, VOICED, 482, 834, 2410, _BV1, _BV2, _BV3, 140, 0, 0, 0, 1.0, 0, 0),  # ɔ
    "o": (VOWEL, VOICED, 450, 900, 2300, _BV1, _BV2, _BV3, 120, 0, 0, 0, 1.0, 0, 0),
    "ʊ": (VOWEL, VOICED, 440, 1020, 2240, _BV1, _BV2, _BV3, 90, 0, 0, 0, 1.0, 0, 0),  # ʊ
    "u": (VOWEL, VOICED, 300, 870, 2240, _BV1, _BV2, _BV3, 130, 0, 0, 0, 1.0, 0, 0),
    "ʌ": (VOWEL, VOICED, 582, 1247, 2390, _BV1, _BV2, _BV3, 110, 0, 0, 0, 1.0, 0, 0),  # ʌ
    "ɝ": (VOWEL, VOICED, 490, 1350, 1690, _BV1, _BV2, _BV3, 150, 0, 0, 0, 1.0, 0, 0),  # ɝ
    "ə": (VOWEL, VOICED, 426, 1498, 2500, _BV1, _BV2, _BV3, 70, 0, 0, 0, 1.0, 0, 0),  # ə
    # Stops (loci + burst centre; expanded into closure/burst at synth)
    "p": (STOP, VOICELESS, 300, 720, 2200, _BC1, _BC2, _BC3, 90, 0, 0, 1200, 0.0, 0.5, 0.4),
    "b": (STOP, VOICED, 300, 720, 2200, _BC1, _BC2, _BC3, 80, 0, 0, 1200, 0.4, 0.4, 0.0),
    "t": (STOP, VOICELESS, 300, 1750, 2600, _BC1, _BC2, _BC3, 90, 0, 0, 3800, 0.0, 0.6, 0.4),
    "d": (STOP, VOICED, 300, 1750, 2600, _BC1, _BC2, _BC3, 80, 0, 0, 3800, 0.4, 0.5, 0.0),
    "k": (STOP, VOICELESS, 300, 1900, 2400, _BC1, _BC2, _BC3, 90, 0, 0, 2200, 0.0, 0.5, 0.5),
    "g": (STOP, VOICED, 300, 1900, 2400, _BC1, _BC2, _BC3, 80, 0, 0, 2200, 0.4, 0.45, 0.0),
    # Nasals: fnz is the place cue (low /m/, mid /n/, high /ŋ/)
    "m": (NASAL, VOICED, 220, 1000, 2200, _BN1, 330, _BN3, 80, 250, 1033, 0, 1.0, 0, 0),
    "n": (NASAL, VOICED, 220, 1600, 2700, _BN1, 197, _BN3, 80, 250, 1308, 0, 1.0, 0, 0),
    "ŋ": (NASAL, VOICED, 220, 2000, 2600, _BN1, 259, _BN3, 80, 250, 2415, 0, 1.0, 0, 0),  # ŋ
    # Fricatives
    "f": (FRICATIVE, VOICELESS, 300, 1100, 2200, _BC1, _BC2, _BC3, 110, 0, 0, 1827, 0.0, 0.18, 0),
    "v": (FRICATIVE, MIXED, 300, 1100, 2200, _BC1, _BC2, _BC3, 80, 0, 0, 1827, 0.25, 0.16, 0),
    "θ": (
        FRICATIVE,
        VOICELESS,
        300,
        1400,
        2400,
        _BC1,
        _BC2,
        _BC3,
        100,
        0,
        0,
        2770,
        0.0,
        0.16,
        0,
    ),  # θ
    "ð": (FRICATIVE, MIXED, 300, 1400, 2400, _BC1, _BC2, _BC3, 70, 0, 0, 2770, 0.25, 0.14, 0),  # ð
    "s": (FRICATIVE, VOICELESS, 300, 1700, 2600, _BC1, _BC2, _BC3, 120, 0, 0, 5344, 0.0, 0.7, 0),
    "z": (FRICATIVE, MIXED, 300, 1700, 2600, _BC1, _BC2, _BC3, 90, 0, 0, 5344, 0.3, 0.5, 0),
    "ʃ": (
        FRICATIVE,
        VOICELESS,
        300,
        1800,
        2500,
        _BC1,
        _BC2,
        _BC3,
        120,
        0,
        0,
        2939,
        0.0,
        0.75,
        0,
    ),  # ʃ
    "ʒ": (FRICATIVE, MIXED, 300, 1800, 2500, _BC1, _BC2, _BC3, 90, 0, 0, 2939, 0.3, 0.55, 0),  # ʒ
    "h": (FRICATIVE, VOICELESS, 500, 1500, 2500, _BC1, _BC2, _BC3, 70, 0, 0, 0, 0.0, 0.0, 0.5),
    # Approximants and lateral
    "ɹ": (APPROXIMANT, VOICED, 330, 1100, 1600, _BV1, _BV2, _BV3, 80, 0, 0, 0, 1.0, 0, 0),  # ɹ
    "j": (APPROXIMANT, VOICED, 250, 2300, 3000, _BV1, _BV2, _BV3, 70, 0, 0, 0, 1.0, 0, 0),
    "w": (APPROXIMANT, VOICED, 290, 610, 2150, _BV1, _BV2, _BV3, 80, 0, 0, 0, 1.0, 0, 0),
    "l": (LATERAL, VOICED, 360, 1300, 2700, _BV1, _BV2, _BV3, 80, 0, 0, 0, 1.0, 0, 0),
    # Silence
    " ": (SILENCE, QUIET, 500, 1500, 2500, _BV1, _BV2, _BV3, 60, 0, 0, 0, 0.0, 0, 0),
    ".": (SILENCE, QUIET, 500, 1500, 2500, _BV1, _BV2, _BV3, 220, 0, 0, 0, 0.0, 0, 0),
}
