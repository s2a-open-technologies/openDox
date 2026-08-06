"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

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

Parakeet streaming ASR backend (VAD-segmented, over WebSocket).

Unlike ``OpenAICompatibleBackend`` (one HTTP POST per fixed chunk), this
backend opens a long-lived WebSocket to the Parakeet server's
``/v1/audio/stream`` endpoint and forwards every PCM frame as it arrives
from the frontend. The server runs incremental Silero VAD + Parakeet ONNX
ASR (see ``parakeet_server/streaming.py``) and streams back:

* ``{"partial": ...}``      — live growing transcript (open segment only),
* ``{"committed": ..., "delta": ...}`` — a segment was frozen,
* ``{"final": ...}``        — session flushed after the stop signal.

``record.py`` drives a ``ParakeetStreamSession`` per WebSocket connection.
The backend object itself is a thin factory + health-check wrapper so it
fits the existing ``ASRBackend`` interface; ``supports_streaming()``
returns ``True`` and ``record.py`` branches on that to use the streaming
path instead of the fixed-chunk path.
"""

import asyncio
import json
import urllib.parse
from typing import Optional

import numpy as np
import requests
import websockets

from backend.components.modules.logger import get_logger

from .base import ASRBackend

logger = get_logger(__name__)


class ParakeetStreamBackend(ASRBackend):
    """Streaming Parakeet backend that proxies a WebSocket to the Parakeet server.

    The endpoint is the same base URL as the HTTP path (e.g.
    ``http://parakeet:5001/v1``); the streaming path ``/audio/stream`` is
    appended here and the scheme is rewritten to ``ws``/``wss``.
    """

    def __init__(self, endpoint: str, api_key: Optional[str] = None):
        self.base_endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.stream_url = self._build_stream_url(self.base_endpoint)

    @staticmethod
    def _build_stream_url(base: str) -> str:
        """Build the WebSocket URL for the Parakeet streaming endpoint.

        Args:
            base: Base HTTP(S) URL, e.g. ``http://parakeet:5001/v1``.

        Returns:
            WebSocket URL, e.g. ``ws://parakeet:5001/v1/audio/stream``.
        """
        parsed = urllib.parse.urlparse(base)
        if parsed.scheme == "https":
            scheme = "wss"
        elif parsed.scheme == "http":
            scheme = "ws"
        else:
            scheme = "ws"
        path = parsed.path or ""
        if not path.endswith("/audio/stream"):
            path = path.rstrip("/") + "/audio/stream"
        host = parsed.netloc
        return urllib.parse.urlunparse((scheme, host, path, "", "", ""))

    def open_session(
        self, on_partial, on_committed, on_final, on_error
    ) -> "ParakeetStreamSession":
        """Open a streaming session.

        Args:
            on_partial: Async callback ``(partial_text: str) -> None`` called
                whenever the live partial transcript updates.
            on_committed: Async callback ``(committed: str, delta: str) ->
                None`` called when a speech segment is frozen.
            on_final: Async callback ``(final_text: str) -> None`` called once
                after the stop signal is processed.
            on_error: Async callback ``(error: Exception) -> None`` called on
                connection failure.

        Returns:
            A ``ParakeetStreamSession`` ready to ``connect()`` and ``feed()``.
        """
        return ParakeetStreamSession(
            stream_url=self.stream_url,
            api_key=self.api_key,
            on_partial=on_partial,
            on_committed=on_committed,
            on_final=on_final,
            on_error=on_error,
        )

    # ── ASRBackend interface (used for health check / non-streaming calls) ──

    def transcribe(
        self,
        audio: bytes | np.ndarray | str,
        language: str = "de",
        beam_size: int = 5,
        prompt: str | None = None,
        params: dict | None = None,
    ) -> str:
        """Streaming backend is not used for one-shot transcription.

        Falls back to a plain HTTP POST to the Parakeet server's
        ``/audio/transcriptions`` endpoint so the health/test path and any
        non-streaming caller still work.
        """
        from .openai_compatible import OpenAICompatibleBackend

        return OpenAICompatibleBackend(
            endpoint=self.base_endpoint,
            api_key=self.api_key,
            model="nemo-parakeet-tdt-0.6b-v3",
        ).transcribe(
            audio,
            language=language,
            beam_size=beam_size,
            prompt=prompt,
            params=params,
        )

    def supports_streaming(self) -> bool:
        """This backend streams partial results over a WebSocket."""
        return True

    def health_check(self) -> bool:
        """Check if the Parakeet server is reachable via its /v1/models route."""
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            url = self.base_endpoint.replace("/audio/transcriptions", "/models")
            if not url.endswith("/models"):
                url = self.base_endpoint.rstrip("/") + "/models"
            response = requests.get(url, headers=headers, timeout=5)
            return response.status_code in [200, 404]
        except Exception as e:
            logger.warning(f"Parakeet stream health check failed: {e}")
            return False

    def get_chunk_config(self) -> dict:
        """Streaming backend segments internally; chunk config is irrelevant.

        Returns a sentinel config so the non-streaming path in ``record.py``
        is never taken for this backend.
        """
        return {"chunk_length_s": 0, "overlap_s": 0}


class ParakeetStreamSession:
    """One streaming transcription session over a WebSocket.

    Lifecycle:
        1. ``await connect()`` — opens the WS to the Parakeet server.
        2. ``await feed(pcm_bytes)`` — forward a float32 PCM frame.
        3. ``await stop()`` — send the stop control frame and wait for the
           final transcript. The reader task finishes on its own.
        4. ``await close()`` — tear down (idempotent).
    """

    def __init__(
        self,
        stream_url: str,
        api_key: Optional[str],
        on_partial,
        on_committed,
        on_final,
        on_error,
    ):
        self.stream_url = stream_url
        self.api_key = api_key
        self._on_partial = on_partial
        self._on_committed = on_committed
        self._on_final = on_final
        self._on_error = on_error

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._closed = False
        self._final_event = asyncio.Event()

    async def connect(self) -> None:
        """Open the WebSocket and start the background reader task."""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            self._ws = await websockets.connect(
                self.stream_url,
                additional_headers=headers,
                max_size=None,
                ping_interval=20,
                ping_timeout=60,
                close_timeout=10,
            )
        except Exception as e:
            await self._safe_error(e)
            raise
        self._reader_task = asyncio.create_task(self._reader_loop())

    async def feed(self, pcm: bytes) -> None:
        """Send one float32 PCM frame to the Parakeet server.

        Args:
            pcm: Raw float32 little-endian 16 kHz mono PCM bytes.
        """
        if self._ws is None:
            return
        try:
            await self._ws.send(pcm)
        except Exception as e:
            await self._safe_error(e)

    async def stop(self, timeout: float = 30.0) -> None:
        """Signal end-of-stream and wait for the server's final transcript.

        Args:
            timeout: Max seconds to wait for the ``final`` message. The
                session is closed regardless once the wait returns.
        """
        if self._ws is None:
            return
        try:
            await self._ws.send(json.dumps({"event": "stop"}))
        except Exception as e:
            await self._safe_error(e)
            return
        try:
            await asyncio.wait_for(self._final_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("[parakeet-stream] timed out waiting for final transcript")
        finally:
            await self.close()

    async def close(self) -> None:
        """Tear down the WebSocket and cancel the reader task (idempotent)."""
        if self._closed:
            return
        self._closed = True
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass

    async def _reader_loop(self) -> None:
        """Background task: read JSON messages and dispatch to callbacks."""
        if self._ws is None:
            return
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
                if "error" in msg:
                    await self._safe_error(Exception(str(msg["error"])))
                    continue
                if "partial" in msg:
                    await self._maybe_call(self._on_partial, msg["partial"])
                if "committed" in msg:
                    delta = msg.get("delta", "")
                    await self._maybe_call(self._on_committed, msg["committed"], delta)
                if "final" in msg:
                    await self._maybe_call(self._on_final, msg["final"])
                    self._final_event.set()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if not self._closed:
                await self._safe_error(e)

    async def _maybe_call(self, cb, *args) -> None:
        """Invoke a callback if it's a coroutine function, awaiting it."""
        if cb is None:
            return
        result = cb(*args)
        if asyncio.iscoroutine(result):
            await result

    async def _safe_error(self, e: Exception) -> None:
        """Forward an error to the on_error callback, swallowing failures."""
        try:
            if self._on_error is not None:
                result = self._on_error(e)
                if asyncio.iscoroutine(result):
                    await result
        except Exception:
            pass
        logger.warning("[parakeet-stream] %s", e)
