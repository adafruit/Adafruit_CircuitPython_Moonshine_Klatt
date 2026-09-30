# SPDX-FileCopyrightText: 2026 Adafruit Industries
# SPDX-License-Identifier: MIT
"""Speak a few phrases through an I2S amplifier, such as the Audio BFF on a QT Py."""

import time

import audiobusio
import board

import adafruit_moonshine_klatt as speech

audio = audiobusio.I2SOut(board.A3, board.A2, board.A1)
tts = speech.TTS(audio)

while True:
    for voice in tts.voices:
        tts.voice = voice
        start = time.monotonic()
        tts.say(f"Hello from Circuit Python. This is the {voice} voice.")
        print(f"{voice}: {time.monotonic() - start:.2f} s")
        time.sleep(1)
    time.sleep(3)
