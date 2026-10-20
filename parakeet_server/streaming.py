"""openDox - Medical transcription platform
Copyright (C) 2025  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
SPDX-License-Identifier: AGPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

VAD-segmented streaming transcription for the Parakeet ASR server.

Ported from the standalone prototype (``inpsection.py``) and adapted for
use inside the FastAPI Parakeet server:

* audio is ingested as **float32** PCM (16 kHz, mono) — the format the
  openDox frontend sends over its WebSocket,
* Silero VAD runs incrementally (stateful, O(new audio)) on 512-sample
  hops,
* speech segments are committed to Parakeet once a trailing silence is
  detected; while speech is ongoing the open segment is re-decoded every
  ``PARTIAL_REDECODE_INTERVAL_S`` so the partial transcript grows in
  real time (self-healing "live feel"),
* segments are auto-split at ``MAX_SEGMENT_S`` so Parakeet's input limit
  is never hit,
* committed text is appended and never re-decoded; only the open
  segment's partial text may change until it is committed.

This is offline ASR (no token streaming), but VAD-segmented streaming
makes it feel live: text grows as you speak and freezes at pauses.
"""

import logging
import os
import threading
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort

logger = logging.getLogger(__name__)

# onnx-asr model name -> resolves to istupakov/parakeet-tdt-0.6b-v3-onnx on HF.
# One instance of this model serves both the live WebSocket and the one-shot
# HTTP route (main.get_model), so it is only held in (V)RAM once.
MODEL_NAME = os.getenv("PARAKEET_MODEL", "nemo-parakeet-tdt-0.6b-v3")

# "int8" loads the dynamically quantized weights from the same HF repo (~0.7 GB
# instead of ~2.5 GB). Default in the CPU image only: dynamic int8 is built for
# CPU inference, and on the CUDA provider part of its ops fall back to the CPU,
# which costs more in host<->device copies than it saves. Empty = FP32.
QUANTIZATION = os.getenv("PARAKEET_QUANTIZATION", "").strip() or None

# Audio format expected by the rest of the backend (PCM float32, mono, 16 kHz).
PCM_SAMPLE_RATE = 16000

# Flat real-file directory for the Silero VAD ONNX file. onnxruntime validates
# external-data paths against the model's own directory and rejects the default
# HF cache (symlinks into blobs/), so we download into a flat directory via
# onnx-asr's `path=` arg. The Parakeet ASR model itself is loaded through the
# default HF cache (the existing parakeet_server already does this and it works
# in the container).
MODELS_DIR = Path(
    os.environ.get(
        "RTT_MODELS_DIR",
        Path(__file__).resolve().parent.parent / "models" / "parakeet-tdt-0.6b-v3",
    )
)
VAD_DIR = Path(
    os.environ.get(
        "RTT_VAD_DIR",
        Path(__file__).resolve().parent.parent / "models" / "silero-vad",
    )
)

# Silero VAD constants (16 kHz).
VAD_HOP = 512  # ~32 ms
VAD_CONTEXT = 64  # left context for the conv state
VAD_THRESHOLD = 0.5  # speech-on
VAD_NEG_THRESHOLD = 0.35  # speech-off (threshold - 0.15)
VAD_MIN_SPEECH_MS = 250  # ignore shorter speech runs
VAD_MIN_SILENCE_MS = 500  # silence needed to commit a segment (live feel)
VAD_SPEECH_PAD_MS = 30

# Open-segment (partial) re-decode cadence. Short enough that the live partial
# rarely lags far behind the final committed text. Measured in wall-clock time
# (see _maybe_decode_partial) so a backlog of queued frames can't cause a burst
# of back-to-back re-decodes once the executor catches up.
PARTIAL_REDECODE_INTERVAL_S = 0.4
# Pre-roll kept before the detected speech onset so Parakeet has the leading
# consonant/breath and doesn't clip word onsets.
ONSET_PREROLL_S = 0.25
# Hard cap so Parakeet's ~20-30 s input limit is never hit. Kept well below
# that limit because the open segment is re-decoded from scratch on every
# tick — cost grows with segment length, so a lower cap bounds per-speaker
# GPU load under concurrent sessions.
MAX_SEGMENT_S = 9.0

# Bounds concurrent ASR recognize() calls across ALL sessions (process-wide,
# shared via ParakeetStreamEngine). Without this, every active session's
# partial re-decode + segment commit can hit the GPU at once with no
# backpressure, spiking VRAM and slowing down every concurrent speaker in
# lockstep. onnx-asr's recognize() is a blocking call, so this is a
# threading.Semaphore (sessions run inside asyncio.to_thread workers, not the
# event loop) held only around the recognize() call itself. Override via
# PARAKEET_MAX_CONCURRENT_DECODES.
MAX_CONCURRENT_DECODES = int(os.environ.get("PARAKEET_MAX_CONCURRENT_DECODES", "2"))


def resolve_providers() -> list[str] | None:
    """Return the ONNX execution providers to load models with.

    Priority order:
      1. ``RTT_ONNX_PROVIDERS`` env (comma-separated) — explicit override.
      2. CUDAExecutionProvider + CPU fallback when onnxruntime-gpu is
         installed (GPU build). TensorrtExecutionProvider is explicitly
         excluded — the CUDA base image has no TensorRT libs, and if
         onnxruntime tries TensorRT first it fails and silently falls back
         to **CPU**, bypassing CUDA entirely.
      3. onnxruntime default (CPU/CoreML auto) for the CPU build.

    Returns:
        Provider list, or ``None`` for onnxruntime defaults.
    """
    providers_env = os.environ.get("RTT_ONNX_PROVIDERS", "")
    if providers_env.strip():
        providers = [p.strip() for p in providers_env.split(",") if p.strip()]
        logger.info("Using ONNX providers (from env): %s", providers)
        return providers
    if "CUDAExecutionProvider" in ort.get_available_providers():
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        logger.info("Using ONNX providers (auto, GPU): %s", providers)
        return providers
    logger.info("Using ONNX providers (auto, CPU default)")
    return None


class ParakeetStreamEngine:
    """Lazy-loaded Parakeet TDT v3 ONNX recognizer + Silero VAD (factory).

    A single process-wide instance is shared by all streaming sessions; the
    heavy ONNX sessions (ASR + VAD) are loaded once and reused.
    """

    def __init__(self):
        self._asr = None  # onnx_asr TextResultsAsrAdapter
        self._vad_session = None  # raw onnxruntime Silero session for streaming
        self._load_lock = threading.Lock()
        # Shared across all StreamingSession instances so the cap applies
        # process-wide, not per session.
        self._decode_semaphore = threading.BoundedSemaphore(MAX_CONCURRENT_DECODES)
        logger.info("Parakeet stream engine initialized")

    def is_loaded(self) -> bool:
        """Whether the ONNX ASR + VAD models are loaded and ready."""
        return self._asr is not None and self._vad_session is not None

    def ensure_loaded(self) -> bool:
        """Load the ASR + VAD models on first use (thread-safe)."""
        if self._asr is not None and self._vad_session is not None:
            return True
        with self._load_lock:
            if self._asr is not None and self._vad_session is not None:
                return True
            return self._load()

    def _load(self) -> bool:
        try:
            import onnx_asr

            logger.info(
                "Loading ASR model %s (quantization=%s)...",
                MODEL_NAME,
                QUANTIZATION or "none",
            )
            providers = resolve_providers()
            self._asr = onnx_asr.load_model(
                MODEL_NAME, quantization=QUANTIZATION, providers=providers
            )

            # Raw Silero VAD session for incremental, stateful streaming. The
            # onnx-asr SileroVad class only processes whole waveforms, so we
            # drive the onnx model directly here. The VAD model is downloaded
            # into a flat directory (VAD_DIR) so we can locate the .onnx file.
            onnx_asr.load_vad("silero", path=str(VAD_DIR))
            vad_path = VAD_DIR / "silero_vad.onnx"
            self._vad_session = ort.InferenceSession(str(vad_path), providers=providers)

            logger.info("Parakeet stream engine loaded (ASR + VAD).")
            return True
        except Exception as e:
            logger.error("Failed to load Parakeet stream engine: %s", e)
            self._asr = None
            self._vad_session = None
            return False

    def get_asr(self):
        """Return the shared ASR model, loading it on first use.

        Raises:
            RuntimeError: If the model cannot be loaded.
        """
        if not self.ensure_loaded():
            raise RuntimeError("Parakeet stream engine failed to load")
        return self._asr

    def new_session(self) -> "StreamingSession":
        """Create a new live transcription session."""
        if not self.ensure_loaded():
            raise RuntimeError("Parakeet stream engine failed to load")
        return StreamingSession(self._asr, self._vad_session, self._decode_semaphore)


class StreamingSession:
    """Live, VAD-segmented streaming transcription.

    Audio is ingested as float32 PCM (mono, 16 kHz) — the exact format the
    openDox frontend sends over its WebSocket. The session:
      * maintains a growing audio buffer for the currently open segment,
      * runs Silero VAD incrementally (stateful) on 512-sample hops,
      * commits a segment to ASR once ``VAD_MIN_SILENCE_MS`` of trailing
        silence follows speech (and auto-splits at ``MAX_SEGMENT_S``),
      * re-decodes the open segment every
        ``PARTIAL_REDECODE_INTERVAL_S`` so the partial transcript grows
        while the user is still speaking.

    ``partial_transcript()`` = committed_text + " " + current_partial.
    """

    def __init__(
        self,
        asr,
        vad_session: ort.InferenceSession,
        decode_semaphore: threading.BoundedSemaphore,
    ):
        self._asr = asr
        self._vad = vad_session
        # Process-wide cap on concurrent recognize() calls (see
        # MAX_CONCURRENT_DECODES); shared with every other active session.
        self._decode_semaphore = decode_semaphore

        # Audio buffer for the currently open segment (float32, mono, 16 kHz).
        # We trim committed audio out so this only holds the open segment.
        self._audio = np.zeros(0, dtype=np.float32)

        # Silero VAD state (2, 1, 128).
        self._vad_state = np.zeros((2, 1, 128), dtype=np.float32)

        # VAD state machine.
        self._in_speech = False
        self._speech_start = 0  # absolute sample index since session start
        self._last_speech_sample = 0
        self._silence_run = 0  # consecutive silent hops
        # Absolute index up to which VAD has processed samples.
        self._vad_processed_samples = 0

        # Offset of the first sample currently held in self._audio (we trim
        # committed audio to bound memory). All "absolute" indices above are
        # relative to session start, not to self._audio.
        self._audio_offset = 0

        # Accumulated committed text.
        self._committed_text_parts: list[str] = []

        # Current partial (open segment) text.
        self._partial_text = ""

        # Throttle for partial re-decode, in wall-clock time (time.monotonic()),
        # not audio-content time — a stall (e.g. executor contention under
        # concurrent sessions) followed by a burst of queued frames must not
        # trigger several re-decodes back-to-back just because a lot of audio
        # content crossed the threshold in that burst.
        self._last_partial_decode_s = 0.0

        # Total samples ingested (for time bookkeeping).
        self._total_samples = 0

    # ── public ──────────────────────────────────────────────────────────

    def ingest(
        self, audio: np.ndarray | bytes, sample_rate: int = PCM_SAMPLE_RATE
    ) -> str:
        """Append float32 PCM audio and return the current partial transcript.

        Args:
            audio: Float32 PCM samples (mono, ``sample_rate`` Hz) as a numpy
                array or raw bytes (float32 little-endian). 16 kHz expected;
                other rates are linearly resampled as a fallback.
            sample_rate: Sample rate of ``audio``. Defaults to 16 kHz.

        Returns:
            The full partial transcript = committed + current partial.
        """
        if isinstance(audio, bytes):
            if not audio:
                return self.partial_transcript()
            samples = np.frombuffer(audio, dtype=np.float32).copy()
        else:
            samples = np.asarray(audio, dtype=np.float32)

        if samples.size == 0:
            return self.partial_transcript()

        if sample_rate != PCM_SAMPLE_RATE:
            n = int(samples.size * PCM_SAMPLE_RATE / sample_rate)
            samples = np.interp(
                np.linspace(0, samples.size - 1, n),
                np.arange(samples.size),
                samples,
            ).astype(np.float32)

        self._audio = np.concatenate([self._audio, samples])
        self._total_samples += samples.size

        self._run_vad_incremental(samples.size)
        self._maybe_decode_partial()
        return self.partial_transcript()

    def partial_transcript(self) -> str:
        """Return committed text + current open-segment partial."""
        committed = " ".join(p for p in self._committed_text_parts if p)
        if self._partial_text:
            if committed:
                return (committed + " " + self._partial_text).strip()
            return self._partial_text
        return committed

    def open_partial_text(self) -> str:
        """Return only the open segment's partial text (no committed text).

        Useful for callers that track committed text separately and only need
        the live, still-changing tail to render alongside it.
        """
        return self._partial_text.strip()

    def committed_text(self) -> str:
        """Return only the committed (frozen) text so far.

        Unlike ``partial_transcript()``, the open segment's partial is
        excluded — useful for the caller to detect newly committed chunks.
        """
        return " ".join(p for p in self._committed_text_parts if p).strip()

    def finish(self) -> str:
        """Flush any open segment and return the final transcript."""
        if self._in_speech:
            # Decode one final partial up to the very end so the trailing
            # words (between the last partial tick and stop) are captured.
            self._flush_segment(end_abs=self._total_samples, force=True)
        return " ".join(p for p in self._committed_text_parts if p).strip()

    # ── VAD ─────────────────────────────────────────────────────────────

    def _run_vad_incremental(self, n_new: int) -> None:
        """Run Silero over newly added samples, update segment state."""
        if n_new <= 0:
            return

        hop = VAD_HOP
        ctx = VAD_CONTEXT
        # Absolute end index that can be processed in whole hops.
        processable = (self._total_samples // hop) * hop
        if self._vad_processed_samples >= processable:
            return

        idx = self._vad_processed_samples
        while idx + hop <= processable:
            # Frame = [idx-ctx, idx+hop) in absolute coordinates.
            frame_start_abs = max(0, idx - ctx)
            frame_start_rel = frame_start_abs - self._audio_offset
            frame_end_rel = idx + hop - self._audio_offset
            if frame_start_rel < 0:
                # Left context falls before what we keep in memory; pad zeros.
                pad = -frame_start_rel
                frame = np.pad(self._audio[:frame_end_rel], (pad, 0))
                frame_start_rel = 0
            else:
                frame = self._audio[frame_start_rel:frame_end_rel]
            if frame.shape[0] < ctx + hop:
                frame = np.pad(frame, (ctx + hop - frame.shape[0], 0))
            frame = frame.reshape(1, -1).astype(np.float32)

            out, new_state = self._vad.run(
                ["output", "stateN"],
                {
                    "input": frame,
                    "state": self._vad_state,
                    "sr": np.array([PCM_SAMPLE_RATE], dtype=np.int64),
                },
            )
            self._vad_state = new_state
            prob = float(out[0, 0])

            self._update_state_machine(prob, idx + hop)
            idx += hop

        self._vad_processed_samples = idx

    def _update_state_machine(self, prob: float, sample_idx: int) -> None:
        silence_hop_samples = VAD_HOP

        if not self._in_speech:
            if prob >= VAD_THRESHOLD:
                self._in_speech = True
                # Keep a pre-roll before the detected onset so leading
                # consonants/breaths aren't clipped.
                preroll = int(ONSET_PREROLL_S * PCM_SAMPLE_RATE)
                self._speech_start = max(0, sample_idx - preroll)
                self._last_speech_sample = sample_idx
                self._silence_run = 0
        else:
            if prob >= VAD_THRESHOLD:
                self._last_speech_sample = sample_idx
                self._silence_run = 0
            else:
                self._silence_run += silence_hop_samples
                min_silence = int(VAD_MIN_SILENCE_MS * PCM_SAMPLE_RATE / 1000)
                if self._silence_run >= min_silence:
                    # Commit the segment that just ended (ends at the last
                    # speech sample, not at the end of the silence run).
                    self._flush_segment(end_abs=self._last_speech_sample, force=False)
                    self._in_speech = False
                    self._silence_run = 0
                    return

            # Auto-split very long segments so Parakeet's input limit is safe.
            seg_len_s = (sample_idx - self._speech_start) / PCM_SAMPLE_RATE
            if seg_len_s >= MAX_SEGMENT_S:
                self._flush_segment(end_abs=sample_idx, force=True)
                # Continue speech as a fresh segment from here.
                self._speech_start = sample_idx

    # ── ASR ─────────────────────────────────────────────────────────────

    def _maybe_decode_partial(self) -> None:
        """Re-decode the open segment periodically for a live partial."""
        if not self._in_speech:
            return
        now_s = time.monotonic()
        if now_s - self._last_partial_decode_s < PARTIAL_REDECODE_INTERVAL_S:
            return
        start_rel = self._speech_start - self._audio_offset
        seg_len_s = (self._audio.size - start_rel) / PCM_SAMPLE_RATE
        if start_rel < 0 or seg_len_s < 0.5:
            return
        self._last_partial_decode_s = now_s
        try:
            waveform = self._audio[start_rel:]
            with self._decode_semaphore:
                result = self._asr.recognize(waveform, sample_rate=PCM_SAMPLE_RATE)
            self._partial_text = _text_from_result(result)
        except Exception as e:
            logger.warning("partial decode failed: %s", e)

    def _flush_segment(self, end_abs: int, *, force: bool) -> None:
        """Commit the current open segment (if any) to ASR.

        Args:
            end_abs: Absolute end index (last speech sample, or current
                position if forced). After committing, we drop all audio up
                to ``end_abs`` from the buffer and rebase indices.
            force: Whether this flush is forced (e.g. auto-split / finish).
        """
        start_rel = self._speech_start - self._audio_offset
        end_rel = end_abs - self._audio_offset
        if start_rel >= end_rel or start_rel < 0:
            self._partial_text = ""
            self._trim_to(end_abs)
            return

        seg_audio = self._audio[start_rel:end_rel]
        seg_len_s = seg_audio.size / PCM_SAMPLE_RATE
        if seg_len_s < VAD_MIN_SPEECH_MS / 1000.0:
            self._partial_text = ""
            self._trim_to(end_abs)
            return

        try:
            with self._decode_semaphore:
                result = self._asr.recognize(seg_audio, sample_rate=PCM_SAMPLE_RATE)
            text = _text_from_result(result)
            if text:
                self._committed_text_parts.append(text)
        except Exception as e:
            logger.warning("segment decode failed: %s", e)
        finally:
            self._partial_text = ""
            self._trim_to(end_abs)

    def _trim_to(self, end_abs: int) -> None:
        """Drop all audio up to absolute index ``end_abs``, rebasing indices."""
        drop = end_abs - self._audio_offset
        if drop <= 0:
            return
        self._audio = self._audio[drop:]
        self._audio_offset = end_abs
        # speech_start is reset by the caller via the state machine; keep it
        # consistent if speech is ongoing.
        if self._in_speech:
            self._speech_start = max(self._speech_start, end_abs)


def _text_from_result(result) -> str:
    """Extract a clean text string from an onnx-asr recognize() result."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    text = getattr(result, "text", None)
    if text is None and isinstance(result, (list, tuple)) and result:
        return " ".join(_text_from_result(r) for r in result).strip()
    return (text or "").strip()


# Process-wide singleton consumed by main.py.
parakeet_stream_engine = ParakeetStreamEngine()
