# app/incident/whisper_provider.py
"""Real speech-to-text provider using faster-whisper.

Converts user-provided audio into timestamped transcript segments
that feed into the existing incident evidence pipeline.

IMPORTANT:
  - This provider processes audio that the USER intentionally provides.
  - LUMINA does NOT automatically capture cellular-call audio.
  - The model is loaded lazily on first use, not at import time.
  - Raw audio is written to a temporary file, transcribed, then deleted.
  - No audio data is persisted in SQLite or any permanent store.
  - No network requests are made for transcription.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from typing import Any, Optional

from app.incident.transcript_provider import (
    TranscriptBatch,
    TranscriptProvider,
    TranscriptSegment,
)

# Supported audio MIME types and extensions
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".webm", ".wma"}
SUPPORTED_MIME_TYPES = {
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/flac",
    "audio/ogg",
    "audio/x-m4a",
    "audio/mp4",
    "audio/webm",
    "audio/x-ms-wma",
}

# 50 MB maximum upload size
MAX_AUDIO_BYTES = 50 * 1024 * 1024

# Default model — small balances accuracy and resource usage
_DEFAULT_MODEL = "small"


def _cuda_usable() -> bool:
    """Return True only if CUDA is actually usable at runtime.

    The NVIDIA driver may report CUDA capability while the CUDA runtime
    libraries (e.g. cuBLAS) are not installed. We verify the runtime
    libraries are loadable before claiming CUDA support.
    """
    import ctypes
    from ctypes import util

    # Look for the cuBLAS runtime shared library that CTranslate2 needs.
    for name in ("cublas64_12.dll", "cublas64.dll", "cublasLt64_12.dll"):
        # Try Windows API search path first, then ctypes util
        try:
            ctypes.CDLL(name)
            return True
        except OSError:
            continue
        except Exception:
            continue

    # Fall back to loader util path probes
    try:
        path = util.find_library("cublas64_12")
        if path:
            ctypes.CDLL(path)
            return True
    except Exception:
        pass

    return False


def _resolve_device() -> str:
    """Resolve the compute device: cuda if usable, else cpu."""
    try:
        import ctranslate2

        cuda_types = ctranslate2.get_supported_compute_types("cuda")
        if cuda_types and _cuda_usable():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _resolve_compute_type(device: str) -> str:
    """Resolve compute type for the given device."""
    if device == "cuda":
        return "float16"
    return "int8"


class WhisperSTTProvider(TranscriptProvider):
    """Speech-to-text provider using faster-whisper (CTranslate2).

    Accepts audio as bytes or a file path, transcribes locally using
    the Whisper model, and returns a TranscriptBatch with timestamped
    segments.

    The model is loaded lazily on first call to provide_segments().
    Configuration via environment variables:
      LUMINA_STT_MODEL    — model size (tiny/base/small/medium/large-v3)
      LUMINA_STT_DEVICE   — compute device (auto/cuda/cpu)
      LUMINA_STT_COMPUTE  — compute type (auto/float16/int8)
    """

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
    ) -> None:
        self._model_size = model_size or os.environ.get(
            "LUMINA_STT_MODEL", _DEFAULT_MODEL
        )
        self._requested_device = device or os.environ.get("LUMINA_STT_DEVICE", "auto")
        self._requested_compute = compute_type or os.environ.get(
            "LUMINA_STT_COMPUTE", "auto"
        )
        if self._requested_device == "auto":
            self._resolved_device = _resolve_device()
        else:
            self._resolved_device = self._requested_device

        if self._requested_compute == "auto":
            self._resolved_compute = _resolve_compute_type(self._resolved_device)
        else:
            self._resolved_compute = self._requested_compute

        self._model: Any = None

    @property
    def provider_id(self) -> str:
        return "whisper_stt"

    @property
    def provider_name(self) -> str:
        return "Whisper Speech-to-Text"

    @property
    def is_available(self) -> bool:
        """Available only if faster-whisper is importable."""
        try:
            import faster_whisper  # noqa: F401

            return True
        except ImportError:
            return False

    def _ensure_model(self) -> None:
        """Lazy-load the Whisper model on first use."""
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            self._model_size,
            device=self._resolved_device,
            compute_type=self._resolved_compute,
        )

    async def provide_segments(
        self,
        input_data: Any,
        incident_id: str,
        batch_id: Optional[str] = None,
    ) -> TranscriptBatch:
        """Transcribe audio and return timestamped transcript segments.

        Uses asyncio.to_thread() to run CPU-bound Whisper inference in a
        thread pool, keeping the FastAPI event loop responsive for other
        requests during transcription.

        Args:
            input_data: Audio data as bytes, a file path string, or a
                        file-like object with a read() method.
            incident_id: The incident these segments belong to.
            batch_id: Optional caller-controlled idempotency id. When provided
                      it is used verbatim so a retry of the same logical upload
                      maps to the same batch (allowing the engine's has_batch()
                      dedup). When None a fresh id is generated and retries are
                      NOT deduplicated.

        Returns:
            TranscriptBatch with timestamped segments.

        Raises:
            ValueError: If input is empty, invalid, or unsupported.
            RuntimeError: If model initialization or transcription fails.
        """
        # Run the entire synchronous transcription pipeline in a thread
        # to avoid blocking the event loop.
        return await asyncio.to_thread(
            self._transcribe_sync, input_data, incident_id, batch_id,
        )

    def _transcribe_sync(
        self,
        input_data: Any,
        incident_id: str,
        batch_id: Optional[str],
    ) -> TranscriptBatch:
        """Synchronous transcription (runs in thread via asyncio.to_thread)."""
        self._ensure_model()
        assert self._model is not None
        assert self._resolved_device is not None

        tmp_path: Optional[str] = None
        try:
            tmp_path = self._write_temp_audio(input_data)
            segments_iter, language_info = self._model.transcribe(
                tmp_path,
                word_timestamps=False,
                vad_filter=True,
            )

            segments: list[TranscriptSegment] = []
            full_text_parts: list[str] = []

            for seg in segments_iter:
                text = seg.text.strip()
                if not text:
                    continue

                segment = TranscriptSegment(
                    text=text,
                    start_time=round(seg.start, 3),
                    end_time=round(seg.end, 3),
                    speaker_attribution_method="STT",
                    speaker_epistemic_status="UNKNOWN",
                    source_provider=self.provider_id,
                    metadata={
                        "language": language_info.language,
                        "language_probability": round(
                            language_info.language_probability, 4
                        ),
                        "device": self._resolved_device,
                        "compute_type": self._resolved_compute,
                        "model": self._model_size,
                    },
                )
                segments.append(segment)
                full_text_parts.append(text)

            if batch_id is None:
                batch_id = uuid.uuid4().hex[:16]

            return TranscriptBatch(
                batch_id=batch_id,
                incident_id=incident_id,
                segments=segments,
                full_text=" ".join(full_text_parts),
                source="STT_PROVIDER",
                metadata={
                    "provider": self.provider_id,
                    "model": self._model_size,
                    "device": self._resolved_device,
                    "compute_type": self._resolved_compute,
                    "language": language_info.language,
                    "duration_seconds": language_info.duration,
                },
            )

        except Exception as exc:
            if isinstance(exc, (ValueError, RuntimeError)):
                raise
            raise RuntimeError(f"Transcription failed: {exc}") from exc

        finally:
            self._cleanup_temp(tmp_path)

    def _write_temp_audio(self, input_data: Any) -> str:
        """Write audio input to a secure temporary file.

        Returns the path to the temporary file.
        The caller is responsible for deletion via _cleanup_temp().
        """
        suffix = ".wav"
        content: bytes

        if isinstance(input_data, (str, bytes, os.PathLike)):
            path_str = str(input_data)

            if os.path.isfile(path_str):
                ext = os.path.splitext(path_str)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    suffix = ext

                file_size = os.path.getsize(path_str)
                if file_size > MAX_AUDIO_BYTES:
                    raise ValueError(
                        f"Audio file too large: {file_size} bytes "
                        f"(maximum: {MAX_AUDIO_BYTES})"
                    )
                if file_size == 0:
                    raise ValueError("Audio file is empty")

                # Copy the source file to a temporary file so that we NEVER
                # modify or delete the caller's original audio. The temp copy
                # is cleaned up by the caller via _cleanup_temp().
                return self._copy_to_temp(path_str, suffix)

        if isinstance(input_data, bytes):
            content = input_data
        elif hasattr(input_data, "read"):
            content = input_data.read()
            if isinstance(content, str):
                content = content.encode("utf-8")
        elif isinstance(input_data, str):
            content = input_data.encode("utf-8")
        else:
            raise ValueError(
                f"Unsupported input type: {type(input_data).__name__}. "
                "Provide audio as bytes, file path, or file-like object."
            )

        if len(content) == 0:
            raise ValueError("Audio input is empty")

        if len(content) > MAX_AUDIO_BYTES:
            raise ValueError(
                f"Audio input too large: {len(content)} bytes "
                f"(maximum: {MAX_AUDIO_BYTES})"
            )

        fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="lumina_audio_")
        try:
            os.write(fd, content)
        finally:
            os.close(fd)

        return tmp_path

    @staticmethod
    def _copy_to_temp(source_path: str, suffix: str) -> str:
        """Copy an existing audio file to a temporary file.

        Returns the path to the temporary copy. The caller is responsible for
        deletion via _cleanup_temp(). The original source file is untouched.
        """
        fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="lumina_audio_")
        try:
            with open(source_path, "rb") as src, os.fdopen(fd, "wb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
        except BaseException:
            # Ensure we don't leave a half-written temp file behind
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return tmp_path

    @staticmethod
    def _cleanup_temp(tmp_path: Optional[str]) -> None:
        """Best-effort removal of temporary audio file."""
        if tmp_path is None:
            return
        try:
            if os.path.isfile(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass
