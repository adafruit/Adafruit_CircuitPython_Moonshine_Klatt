# SPDX-FileCopyrightText: 2026 Adafruit Industries
# SPDX-License-Identifier: MIT
"""
`adafruit_moonshine_klatt`
================================================================================

Text to speech for CircuitPython using the Moonshine Klatt formant synthesizer.

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads
"""

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_Moonshine_Klatt.git"

import array
import gc

_SAMPLE_RATE = 22050
_SAMPLES_PER_FRAME = 110  # 5 ms at 22050 Hz
_FADE = 110  # 5 ms fade in and out on each word
_NATURAL_WPM = 108  # speaking rate of the voice timings at speed 1.0, measured
# Mixer buffer in bytes. The mixer fills halves of it (shared-module/audiomixer/Mixer.c) from a
# background callback between bytecodes, so a stall longer than one half (256 samples, 11.6 ms
# here) skips. Measured by recording with a mic: 512 skipped on the RP2040 (clicks up 45%), 1024
# to 8192 did not. 1024 has the shortest handover gaps and costs least RAM, which matters on the
# nRF52840, whose PWMAudioOut allocates about 8x buffer_size (9 KB at 1024, 17 KB at 2048).
# Pass a MixerVoice from your own Mixer for a larger buffer if other code stalls the loop.
_MIXER_BUFFER_SIZE = 1024
# Speech buffer: one allocation in TTS(), the largest block the heap allows, capped at 3 s.
# _RESERVE is left free for per-word work, which allocates at most about 12 KB of short-lived
# objects (measured on the longest test word) since the tracks are preallocated.
_MAX_BUFFER_SAMPLES = 3 * _SAMPLE_RATE
_RESERVE = 16384
# Frame tracks for one word, allocated once and refilled per word, never grown: growing them
# mid-speech failed on the nRF52840 and M4. 512 frames (2.56 s, 32 KB) holds every word at the
# default rate; a longer word (slow rates) is split at a phone boundary with a short pause.
_TRACK_FRAMES = 512
# Frames rendered per update() call. update() returns between slices so a finished word can be
# handed to the mixer within about one slice (10 frames, 35 ms on a 125 MHz RP2040) instead of
# after a whole word is rendered.
_SLICE_FRAMES = 10
# Pieces are at most 100 ms, so the ring holds several and rendering overlaps playback even in a
# ring shorter than two words. Pieces that sit next to each other in the ring play as one
# RawSample of up to half the ring (double buffering), so a mixer handover happens about once
# per half ring, or sooner when rendering falls behind.
_PIECE_FRAMES = 20
# A handover that lands inside a word leaves up to one mixer half-buffer of silence. 1.5 ms
# fades on both sides of it turn a click into a short dropout.
_EDGE = 32
_BUSY = object()  # _render_step made progress but has no finished piece yet
_VOICES = ("default", "female", "nojitter")
# Frame field order that klatt_fixed.FixedSynth.render_frame reads.
_FRAME_FIELDS = (
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
)
_PITCH_MIN = 0.5
_PITCH_MAX = 2.0


def _words(text):
    """Split text into per-word phone lists. A sentence pause stays with the word before it.
    Numbers come back from the G2P as one word joined by secondary stress marks ("one million
    two hundred ..."), which only numbers produce, so those split into their number words."""
    from adafruit_moonshine_klatt import klatt_g2p  # noqa: PLC0415

    word = []
    for tok in klatt_g2p.text_to_phones(text):
        if tok == "ˌ":
            if word:
                yield word
                word = []
        elif tok in (" ", "."):
            if word:
                if tok == ".":
                    word.append(tok)
                yield word
                word = []
        else:
            word.append(tok)
    if word:
        yield word


def _is_mixer_voice(obj) -> bool:
    # audiomixer exports only Mixer, not the MixerVoice type. Of the objects TTS accepts, only
    # a MixerVoice has a level.
    return hasattr(obj, "level")


class TTS:
    """Speak text through an audio output.

    :param audio: An audio output object with ``play()``, ``stop()`` and ``playing``, such as
        `audiobusio.I2SOut`, `audioio.AudioOut` or `audiopwmio.PWMAudioOut`. The library
        creates its own `audiomixer.Mixer` on it. Or an `audiomixer.MixerVoice` from the
        caller's mixer, whose sample rate must match `sample_rate`.
    """

    def __init__(self, audio) -> None:
        self._queue = []
        self._words = None  # phone lists left in the text being spoken
        self._word = None  # [tracks, frame count, next frame] of the word being rendered
        self._carry = None  # rest of a word too long for the tracks, rendered next
        # Rendered pieces are (start, end, word_start, word_end) spans of one ring buffer, laid
        # down in order after the ones still playing or waiting, so nothing is allocated per
        # word and the heap does not fragment.
        self._buf = None
        self._cap = 0
        self._pending = []  # rendered pieces waiting for the mixer voice, oldest first
        self._piece = None  # [start, frames, first frame, frames done] of the piece in progress
        self._playing = None  # (start, end) of the span the mixer voice is playing
        # Pre-buffer: before speech starts, and after running dry, render until the ring is
        # full before playing. A board that renders slower than real time then speaks with
        # one pause up front instead of a gap between every word.
        self._filling = False
        self._synth = None  # built on first use and when the voice changes
        self._spare_synth = None  # the previous voice's synth, reused by _make_synth
        self._rate = 150
        self._volume = 1.0
        self._pitch = 1.0
        self._voice_name = _VOICES[0]

        if _is_mixer_voice(audio):
            self._audio = None
            self._mixer = None
            self._mixer_voice = audio
        else:
            import audiomixer  # noqa: PLC0415

            self._audio = audio
            self._mixer = audiomixer.Mixer(
                voice_count=1,
                buffer_size=_MIXER_BUFFER_SIZE,
                sample_rate=_SAMPLE_RATE,
                channel_count=1,
                bits_per_sample=16,
                samples_signed=True,
            )
            self._mixer_voice = self._mixer.voice[0]
            audio.play(self._mixer)
        self._mixer_voice.level = self._volume
        # Long-lived allocations first, then the speech buffer, so per-word garbage cannot
        # fragment the heap under it. On a 264 KB RP2040 this ordering is what makes it fit.
        from adafruit_moonshine_klatt import klatt_frames, klatt_g2p  # noqa: F401, PLC0415

        self._make_synth()
        self._tracks = klatt_frames.new_tracks(_TRACK_FRAMES)
        self._alloc_buffer()

    @property
    def sample_rate(self) -> int:
        """Sample rate of the speech output in Hz."""
        return _SAMPLE_RATE

    @property
    def speaking(self) -> bool:
        """True while speech is playing or queued."""
        return (
            self._mixer_voice.playing
            or bool(self._pending)
            or self._word is not None
            or self._carry is not None
            or self._words is not None
            or bool(self._queue)
        )

    @property
    def rate(self) -> int:
        """Speaking rate in words per minute. Default 150."""
        return self._rate

    @rate.setter
    def rate(self, value: int) -> None:
        if value <= 0:
            raise ValueError("rate must be > 0")
        self._rate = value

    @property
    def volume(self) -> float:
        """Volume from 0.0 to 1.0, applied as the mixer voice level. Default 1.0."""
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        self._volume = min(max(value, 0.0), 1.0)
        self._mixer_voice.level = self._volume

    @property
    def pitch(self) -> float:
        """Pitch multiplier, 1.0 is normal. Clamped to 0.5 to 2.0."""
        return self._pitch

    @pitch.setter
    def pitch(self, value: float) -> None:
        self._pitch = min(max(value, _PITCH_MIN), _PITCH_MAX)

    @property
    def voice(self) -> str:
        """Voice preset name. See `voices` for the ones available."""
        return self._voice_name

    @voice.setter
    def voice(self, name: str) -> None:
        if name not in _VOICES:
            raise ValueError(f"voice must be one of {_VOICES}")
        if name != self._voice_name:
            if self._synth is not None:
                self._spare_synth = self._synth
            self._synth = None
        self._voice_name = name

    @property
    def voices(self) -> tuple:
        """Voice preset names available."""
        return _VOICES

    def say(self, text: str, *, wait: bool = True, interrupt: bool = False) -> None:
        """Speak ``text``. If speech is already playing, ``text`` is queued after it.

        :param str text: The text to speak.
        :param bool wait: If True, return when all queued speech ends. If False, return
            right away; call `update` in the main loop to keep speech going.
        :param bool interrupt: If True, stop current speech and clear the queue first.
        """
        if interrupt:
            self.stop()
        self._queue.append(text)
        self.update()
        if wait:
            while self.speaking:
                self.update()

    def update(self) -> None:
        """Render and queue the next chunk of speech when the mixer is ready for it. Call
        often from the main loop after ``say(..., wait=False)``."""
        if self._playing is not None and not self._mixer_voice.playing:
            self._playing = None
        if self._playing is None and not self._pending and self._more_to_render():
            self._filling = True  # nothing playing and nothing ready: pre-buffer first
        self._play_next()
        # One slice of work per call, so the caller's loop, and the handover to the mixer,
        # never wait for a whole word to render.
        step = self._render_step()
        if step is None:
            if self._filling:
                self._filling = False  # ring full, or the text is all rendered
                self._play_next()
        elif step is not _BUSY:
            self._pending.append(step)
            self._play_next()

    def _more_to_render(self):
        return (
            self._word is not None
            or self._carry is not None
            or self._words is not None
            or bool(self._queue)
        )

    def _play_next(self):
        if self._playing is None and self._pending and not self._filling:
            import audiocore  # noqa: PLC0415

            # Merge pieces that sit next to each other into one run, up to half the ring, so
            # the other half is free to render into while this run plays.
            pending = self._pending
            first = pending.pop(0)
            last = first
            limit = first[0] + self._cap // 2
            while pending and pending[0][0] == last[1] and pending[0][1] <= limit:
                last = pending.pop(0)
            start, end = first[0], last[1]
            out = self._buf
            edge = min(_EDGE, (end - start) // 2)
            if not first[2]:  # starts inside a word
                for i in range(edge):
                    out[start + i] = out[start + i] * i // edge
            if not last[3]:  # ends inside a word
                for i in range(edge):
                    out[end - 1 - i] = out[end - 1 - i] * i // edge
            self._playing = (start, end)
            self._mixer_voice.play(
                audiocore.RawSample(memoryview(out)[start:end], sample_rate=_SAMPLE_RATE)
            )

    def stop(self) -> None:
        """Stop speaking and clear the queue."""
        self._queue.clear()
        self._words = None
        self._word = None
        self._carry = None
        self._piece = None
        self._pending = []
        self._filling = False
        self._mixer_voice.stop()
        self._playing = None

    def _next_phones(self):
        """Phone list of the next word of the queued text, or None when nothing is left."""
        if self._carry is not None:
            phones, self._carry = self._carry, None
            return phones
        while True:
            if self._words is None:
                if not self._queue:
                    return None
                self._words = _words(self._queue.pop(0))
            try:
                return next(self._words)
            except StopIteration:
                self._words = None

    def _place(self, size):
        """Start of a free span of ``size`` samples in the ring buffer after the pieces still in
        use, or None until enough of them have played."""
        busy = self._pending if self._playing is None else [self._playing] + self._pending
        if not busy:
            return 0 if size <= self._cap else None
        tail = busy[0][0]  # start of the oldest span in use
        head = busy[-1][1]  # end of the newest
        if head > tail:  # in use: [tail, head), free: [head, cap) and [0, tail)
            if head + size <= self._cap:
                return head
            return 0 if size <= tail else None
        # Wrapped. In use: [tail, cap) and [0, head), free: [head, tail)
        return head if head + size <= tail else None

    def _render_step(self):
        """Do one slice of rendering work. Returns a finished piece (start, end, word_start,
        word_end),
        _BUSY if work was done but the piece is not finished, or None when nothing is left or
        there is no room in the ring until more of the queued pieces have played."""
        spf = _SAMPLES_PER_FRAME
        if self._piece is None:
            if self._word is None:
                phones = self._next_phones()
                if phones is None:
                    return None
                self._word = self._prepare(phones)
                return _BUSY  # word setup is a step of its own
            n, first = self._word[1], self._word[2]
            count = min(n - first, _PIECE_FRAMES, self._cap // spf)
            start = self._place(count * spf)
            if start is None:
                return None
            self._piece = [start, count, first, 0]
        if self._synth is None:
            self._make_synth()  # the voice changed mid-word
        start, count, first, done = self._piece
        tracks, n, _ = self._word
        out = self._buf
        synth = self._synth
        stop = first + min(count, done + _SLICE_FRAMES)
        i = first + done
        last = n - 1
        render_at = synth.render_at
        offset = start + done * spf
        while i < stop:
            render_at(tracks, i, i + 1 if i < last else i, spf, out, offset)
            offset += spf
            i += 1
        if i < first + count:
            self._piece[3] = i - first
            return _BUSY
        self._piece = None
        size = count * spf
        # Fade length comes from the whole word, not this piece, so splitting a word does not
        # change its sound. Every piece is at least one frame (110 samples), which covers it.
        fade = min(n * spf // 2, _FADE)
        if first == 0:
            for i in range(fade):
                out[start + i] = out[start + i] * i // fade
        word_end = first + count == n
        if word_end:
            end = start + size - 1
            for i in range(fade):
                out[end - i] = out[end - i] * i // fade
            self._word = None
        else:
            self._word[2] = first + count
        return (start, start + size, first == 0, word_end)

    def _make_synth(self):
        from adafruit_moonshine_klatt import klatt_fixed, klatt_voice  # noqa: PLC0415

        make = getattr(klatt_voice, self._voice_name + "_voice")
        self._base_f0_scale = make().f0_scale
        # After a voice change, refill the previous synth's arrays instead of allocating new
        # ones: by then the ring holds most of the heap and an 8.7 KB table may not fit.
        synth = self._spare_synth
        self._spare_synth = None
        if synth is None:
            synth = klatt_fixed.FixedSynth(_SAMPLE_RATE, make())
        else:
            synth.set_voice(make())
        self._synth = synth

    def _alloc_buffer(self):
        """Allocate the ring buffer: the largest single block the heap can give, up to 3 s,
        leaving _RESERVE free for per-word work. gc.mem_free() counts scattered free space, so
        the size is found by trying allocations (binary search to within 20 frames)."""
        spf = _SAMPLES_PER_FRAME
        gc.collect()
        lo = 0
        hi = min(_MAX_BUFFER_SAMPLES, (gc.mem_free() - _RESERVE) // 2)
        hi -= hi % spf
        while hi - lo > 20 * spf:
            mid = (lo + hi) // 2
            mid -= mid % spf
            try:
                # One allocation; array("h", bytes(n)) would briefly need twice the memory.
                array.array("h", [0]) * mid  # allocated and dropped: only testing that it fits
                lo = mid
            except MemoryError:
                hi = mid
        if hi > lo:
            try:
                array.array("h", [0]) * hi  # allocated and dropped: only testing that it fits
                lo = hi
            except MemoryError:
                pass
        if lo < 20 * spf:
            raise MemoryError("not enough RAM for the speech buffer")
        gc.collect()
        self._buf = array.array("h", [0]) * lo
        self._cap = lo

    def _prepare(self, phones):
        """Frame tracks for one word: [tracks, frame count, next frame to render]."""
        from adafruit_moonshine_klatt import klatt_frames  # noqa: PLC0415

        if self._synth is None:
            self._make_synth()
        synth = self._synth
        synth.voice.f0_scale = self._base_f0_scale * self._pitch
        # Same steps as klatt_frames.phones_to_frames, but frames are assembled one at a time
        # from the array("f") tracks instead of zipped into a list of tuples.
        dur_scale = synth.voice.duration_scale * _NATURAL_WPM / self._rate
        segs = klatt_frames.build_segments(phones, synth.voice)
        n = klatt_frames.count_frames(segs, dur_scale)
        while n > _TRACK_FRAMES and len(phones) > 1:
            half = len(phones) // 2
            rest = phones[half:]
            self._carry = rest if self._carry is None else rest + self._carry
            phones = phones[:half]
            segs = klatt_frames.build_segments(phones, synth.voice)
            n = klatt_frames.count_frames(segs, dur_scale)
        t = klatt_frames.fill_tracks(segs, synth.voice, dur_scale, out=self._tracks)
        return [[t[k] for k in _FRAME_FIELDS], n, 0]

    def deinit(self) -> None:
        """Stop speaking and release the mixer this object created. The audio output and a
        caller's mixer are not deinitialized; the caller owns them."""
        self.stop()
        self._buf = None
        self._tracks = None
        self._synth = None
        self._spare_synth = None
        if self._mixer is not None:
            self._audio.stop()
            self._mixer.deinit()
            self._mixer = None

    def __enter__(self) -> "TTS":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.deinit()
