# SPDX-FileCopyrightText: 2026 Adafruit Industries
# SPDX-License-Identifier: MIT
"""Speak a few phrases through an I2S amplifier.

Uncomment the I2SOut lines for your board. The default is a Feather RP2040, RP2350 or ESP32-S3
with a MAX98357A amp: BCLK to A0, LRC to A1, DIN to A2.
"""

import time

import audiobusio
import board

import adafruit_moonshine_klatt as speech

# Feather RP2040, RP2350 or ESP32-S3 with a MAX98357A. On the RP2040 and RP2350, bit clock and
# word select must be consecutive GPIOs: A0 and A1 are GPIO26 and GPIO27.
audio = audiobusio.I2SOut(board.A0, board.A1, board.A2)

# QT Py ESP32-S3 with an Audio BFF.
# audio = audiobusio.I2SOut(board.A3, board.A2, board.A1)

# Feather RP2040 Prop-Maker. The built-in amp is on the switched external power rail.
# import digitalio
# external_power = digitalio.DigitalInOut(board.EXTERNAL_POWER)
# external_power.switch_to_output(value=True)
# audio = audiobusio.I2SOut(board.I2S_BIT_CLOCK, board.I2S_WORD_SELECT, board.I2S_DATA)

tts = speech.TTS(audio)

while True:
    for voice in tts.voices:
        tts.voice = voice
        start = time.monotonic()
        tts.say(f"Hello from Circuit Python. This is the {voice} voice.")
        print(f"{voice}: {time.monotonic() - start:.2f} s")
        time.sleep(1)
    time.sleep(3)
