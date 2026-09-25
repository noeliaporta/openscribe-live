"""Backends de transcripción + procesador combinado de Gemini (audio).

- WhisperTranscriber: 100% local con faster-whisper.
- GeminiTranscriber: transcripción con la API de audio de Gemini.
- GeminiAVProcessor: en UNA sola llamada, Gemini escucha el audio y devuelve
  la transcripción original + las traducciones. Más rápido y preciso que
  encadenar transcripción y traducción por separado.
"""
from __future__ import annotations

import io
import json
import re
import time
import wave
from typing import Dict, List, Tuple

from . import config


def _pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _retry(fn, retries: int):
    """Reintenta ante errores transitorios de la API (ej. 503)."""
    last = None
    for i in range(max(1, retries)):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            msg = str(e)
            # solo reintentar errores tipicamente transitorios
            if any(c in msg for c in ("503", "UNAVAILABLE", "429", "500", "deadline")):
                time.sleep(0.6 * (i + 1))
                continue
            raise
    raise last


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


class WhisperTranscriber:
    """Transcripción local con faster-whisper (offline, sin API)."""

    def __init__(self) -> None:
        from faster_whisper import WhisperModel

        self.model = WhisperModel(
            config.WHISPER_MODEL,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE,
        )

    def transcribe(self, pcm: bytes, sample_rate: int) -> Tuple[str, str]:
        import numpy as np

        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        segments, info = self.model.transcribe(
            audio, beam_size=1, vad_filter=True, no_speech_threshold=0.6)
        text = " ".join(s.text.strip() for s in segments).strip()
        return text, (info.language or "")


class GeminiTranscriber:
    """Transcripción usando la API de audio de Gemini."""

    def __init__(self) -> None:
        from google import genai

        if not config.GEMINI_API_KEY:
            raise RuntimeError("Falta GEMINI_API_KEY para el backend gemini")
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model = config.GEMINI_MODEL

    def transcribe(self, pcm: bytes, sample_rate: int) -> Tuple[str, str]:
        from google.genai import types

        wav = _pcm_to_wav(pcm, sample_rate)
        resp = _retry(lambda: self.client.models.generate_content(
            model=self.model,
            contents=[
                "Transcribe este audio literalmente. Devuelve solo el texto, "
                "sin comentarios. Si no hay habla clara, devuelve vacío.",
                types.Part.from_bytes(data=wav, mime_type="audio/wav"),
            ],
        ), config.GEMINI_RETRIES)
        return (resp.text or "").strip(), ""


class GeminiAVProcessor:
    """Transcribe + traduce el audio en una sola llamada a Gemini.

    process(pcm, sample_rate, targets) -> (original, lang, translations)
    """

    def __init__(self) -> None:
        from google import genai
        from .translator import _load_glossary

        if not config.GEMINI_API_KEY:
            raise RuntimeError("Falta GEMINI_API_KEY para el pipeline gemini_av")
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model = config.GEMINI_MODEL
        self.glossary = _load_glossary()

    def process(self, pcm: bytes, sample_rate: int,
                targets: List[str]) -> Tuple[str, str, Dict[str, str]]:
        from google.genai import types

        wav = _pcm_to_wav(pcm, sample_rate)
        tgt = ", ".join(targets)
        prompt = (
            "Escuchá este audio de una charla técnica. Devolvé SOLO un JSON "
            'válido con esta forma exacta: {"lang":"<codigo ISO del idioma '
            'hablado>","original":"<transcripcion literal>","translations":'
            '{"<codigo>":"<traduccion>"}}. '
            f"Traducí a estos idiomas: {tgt}. No traduzcas al mismo idioma del "
            "audio (omití esa clave). Si no hay habla clara, devolvé original "
            "vacío. No agregues nada fuera del JSON."
        )
        if self.glossary:
            pairs = ", ".join(f"{k}={v}" for k, v in self.glossary.items())
            prompt += f" Respetá estos términos fijos: {pairs}."

        resp = _retry(lambda: self.client.models.generate_content(
            model=self.model,
            contents=[prompt,
                      types.Part.from_bytes(data=wav, mime_type="audio/wav")],
        ), config.GEMINI_RETRIES)

        raw = _strip_code_fence(resp.text or "")
        if not raw:
            return "", "", {}
        try:
            data = json.loads(raw)
        except Exception:
            # si no devolvió JSON válido, usamos el texto como original
            return raw, "", {}
        original = (data.get("original") or "").strip()
        lang = (data.get("lang") or "").strip()
        translations = {k: (v or "").strip()
                        for k, v in (data.get("translations") or {}).items()
                        if v}
        return original, lang, translations


def get_transcriber():
    backend = config.TRANSCRIBE_BACKEND.lower()
    if backend == "gemini":
        return GeminiTranscriber()
    return WhisperTranscriber()


def get_processor():
    """Devuelve un procesador combinado si PIPELINE lo pide, si no None."""
    if config.PIPELINE.lower() == "gemini_av":
        return GeminiAVProcessor()
    return None
