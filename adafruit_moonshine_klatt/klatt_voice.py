# SPDX-FileCopyrightText: 2026 Moonshine AI (original C++), Adafruit port
# SPDX-License-Identifier: MIT
"""Voice parameters, ported from moonshine micro/klatt-tts config.h (VoiceParams).

Only the fields the default voice uses are kept. Features that are off by default
(LF glottal model, source tilt, breathiness, F6, F0 bandwidth widening) are not ported.
"""


class Voice:
    def __init__(self):
        # Source gains
        self.voice_gain = 23.49
        self.fric_gain = 0.578
        self.asp_gain = 0.295
        self.fric_q = 1.269

        # Segment timing (ms)
        self.duration_scale = 1.336
        self.lead_ms = 40.0
        self.tail_ms = 70.0
        self.stop_closure_voiced_ms = 61.96
        self.stop_closure_voiceless_ms = 55.0
        self.stop_burst_ms = 14.50
        self.stop_asp_ms = 35.17
        self.stop_closure_av = 0.15
        self.stop_burst_av = 0.20
        self.stop_closure_f1 = 220.0

        # Rosenberg glottal pulse (fractions of a pitch period)
        self.glottal_open = 0.40
        self.glottal_close = 0.16

        # Fixed high formants
        self.f4 = 3500.0
        self.b4 = 250.0
        self.f5 = 4500.0
        self.b5 = 300.0

        # Voice identity
        self.formant_scale = 1.0
        self.f0_scale = 1.0

        # Streaming output level
        self.output_gain = 0.27

        # Track smoothing time constants (ms)
        self.formant_smooth_ms = 21.72
        self.av_smooth_ms = 6.0
        self.af_attack_ms = 16.77
        self.af_release_ms = 8.0
        self.ah_smooth_ms = 5.0
        self.nasal_smooth_ms = 10.0

        # Prosody
        self.f0_start = 95.33
        self.f0_end = 92.0
        self.final_fall_hz = 10.0
        self.f0_flutter_hz = 1.82
        self.jitter = 0.0022
        self.shimmer = 0.036
        self.f0_accent_hz = 9.28
        self.f0_question_rise_hz = 25.0
        self.f0_declination_hz = 0.0
        self.f0_downstep = 1.0
        self.stress_len_scale = 1.0
        self.unstressed_len_scale = 1.0
        self.prepausal_len_scale = 1.0


def default_voice():
    return Voice()


def nojitter_voice():
    v = Voice()
    v.jitter = 0.0
    v.shimmer = 0.0
    return v


def female_voice():
    v = Voice()
    v.formant_scale = 1.18
    v.f0_scale = 1.9
    return v
