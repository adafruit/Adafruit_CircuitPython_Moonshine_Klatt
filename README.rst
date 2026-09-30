Introduction
============


.. image:: https://readthedocs.org/projects/adafruit-circuitpython-moonshine-klatt/badge/?version=latest
    :target: https://docs.circuitpython.org/projects/moonshine-klatt/en/latest/
    :alt: Documentation Status


.. image:: https://raw.githubusercontent.com/adafruit/Adafruit_CircuitPython_Bundle/main/badges/adafruit_discord.svg
    :target: https://adafru.it/discord
    :alt: Discord


.. image:: https://github.com/adafruit/Adafruit_CircuitPython_Moonshine_Klatt/workflows/Build%20CI/badge.svg
    :target: https://github.com/adafruit/Adafruit_CircuitPython_Moonshine_Klatt/actions
    :alt: Build Status


.. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
    :target: https://github.com/astral-sh/ruff
    :alt: Code Style: Ruff

Text to speech for CircuitPython using the Moonshine Klatt formant synthesizer. It needs no
voice data files and renders speech on the board, word by word, through ``audiomixer``.

``say()`` waits until the text has been spoken. ``say(text, wait=False)`` returns right away;
call ``update()`` from your main loop to keep speaking.


Dependencies
=============
This library depends on:

* `Adafruit CircuitPython <https://github.com/adafruit/circuitpython>`_ 11 or later, on a board
  that can load native ``.mpy`` files (``microcontroller.cpu.architecture`` is not ``None``)

The per-sample synthesis loop is a precompiled native kernel, one file per architecture:

======================  =============================================
``klatt_kernel`` file   Boards
======================  =============================================
``armv6m``              RP2040
``armv7emsp``           SAMD51 (M4), nRF52840, RP2350, STM32F4
``xtensawin``           ESP32-S2, ESP32-S3
``rv32imc``             ESP32-C3, C5, C6
======================  =============================================

This library does not run on Blinka or SAMD21 (M0) boards.

Please ensure all dependencies are available on the CircuitPython filesystem.
This is easily achieved by downloading
`the Adafruit library and driver bundle <https://circuitpython.org/libraries>`_
or individual libraries can be installed using
`circup <https://github.com/adafruit/circup>`_.

Installing to a Connected CircuitPython Device with Circup
==========================================================

Make sure that you have ``circup`` installed in your Python environment.
Install it with the following command if necessary:

.. code-block:: shell

    pip3 install circup

With ``circup`` installed and your CircuitPython device connected use the
following command to install:

.. code-block:: shell

    circup install adafruit_moonshine_klatt

Or the following command to update an existing version:

.. code-block:: shell

    circup update

Usage Example
=============

.. code-block:: python

    import audiobusio
    import board

    import adafruit_moonshine_klatt as speech

    audio = audiobusio.I2SOut(board.A3, board.A2, board.A1)
    tts = speech.TTS(audio)
    tts.say("Hello from Circuit Python.")

Speed and memory
================

Rendering runs a little slower than real time on some boards, so ``TTS`` fills a buffer before
it starts playing and pauses briefly if rendering falls behind. At default clock speeds,
render time divided by audio length for a short sentence is under 0.4 on the ESP32-S3, about
0.6 on the SAMD51 and about 1.0 on the nRF52840.

``TTS()`` allocates its buffers once, taking the largest block the heap allows (up to 3 s of
audio). Create it early, before other large allocations.

Building the kernel
===================

``src/klatt_turbo.py`` is the kernel source, a turbo (``@micropython.viper``) function.
``src/Makefile`` compiles it with ``mpy-cross -march`` for each architecture into
``adafruit_moonshine_klatt/klatt_kernel.<arch>.mpy``:

.. code-block:: shell

    cd src
    make MPY_CROSS=path/to/circuitpython/mpy-cross/build/mpy-cross

Use an ``mpy-cross`` from the CircuitPython version the files will run on.
``src/klatt_kernel.c`` is the same kernel in C, kept as a reference.

Documentation
=============
API documentation for this library can be found on `Read the Docs <https://docs.circuitpython.org/projects/moonshine-klatt/en/latest/>`_.

For information on building library documentation, please check out
`this guide <https://learn.adafruit.com/creating-and-sharing-a-circuitpython-library/sharing-our-docs-on-readthedocs#sphinx-5-1>`_.

Contributing
============

Contributions are welcome! Please read our `Code of Conduct
<https://github.com/adafruit/Adafruit_CircuitPython_Moonshine_Klatt/blob/HEAD/CODE_OF_CONDUCT.md>`_
before contributing to help this project stay welcoming.
