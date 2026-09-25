"""Backends de traducción intercambiables + glosario.

translate(text, src, tgt) -> str
- ArgosTranslator: 100% local (argostranslate).
- GeminiTranslator: usa la API de Gemini.

El glosario (JSON {"término": "traducción"}) se aplica como post-proceso para
fijar nombres propios y términos técnicos.
"""
from __future__ import annotations

import json
import os
import re
import time

from . import config


def _retry(fn, retries: int):
    """Reintenta ante errores transitorios de la API (ej. 503)."""
    last = None
    for i in range(max(1, retries)):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if any(c in str(e) for c in ("503", "UNAVAILABLE", "429", "500", "deadline")):
                time.sleep(0.6 * (i + 1))
                continue
            raise
    raise last


def _load_glossary() -> dict:
    path = config.GLOSSARY_PATH
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _apply_glossary(text: str, glossary: dict) -> str:
    for term, repl in glossary.items():
        text = re.sub(rf"\b{re.escape(term)}\b", repl, text, flags=re.IGNORECASE)
    return text


class ArgosTranslator:
    """Traducción local con argostranslate (offline)."""

    def __init__(self) -> None:
        import argostranslate.translate as t
        self._t = t
        self.glossary = _load_glossary()

    def translate(self, text: str, src: str, tgt: str) -> str:
        if not text or src == tgt:
            return text
        try:
            out = self._t.translate(text, src, tgt)
        except Exception:
            out = text
        return _apply_glossary(out, self.glossary)


class GeminiTranslator:
    """Traducción usando la API de Gemini."""

    def __init__(self) -> None:
        from google import genai

        if not config.GEMINI_API_KEY:
            raise RuntimeError("Falta GEMINI_API_KEY para el backend gemini")
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model = config.GEMINI_MODEL
        self.glossary = _load_glossary()

    def translate(self, text: str, src: str, tgt: str) -> str:
        if not text or src == tgt:
            return text
        gl = ""
        if self.glossary:
            pairs = ", ".join(f"{k}={v}" for k, v in self.glossary.items())
            gl = f" Respetá estos términos fijos: {pairs}."
        prompt = (
            f"Traducí de {src} a {tgt}. Devolvé solo la traducción, sin "
            f"comentarios ni comillas.{gl}\n\nTexto: {text}"
        )
        resp = _retry(lambda: self.client.models.generate_content(
            model=self.model, contents=prompt), config.GEMINI_RETRIES)
        out = (resp.text or "").strip()
        return _apply_glossary(out, self.glossary)


def get_translator():
    backend = config.TRANSLATE_BACKEND.lower()
    if backend == "gemini":
        return GeminiTranslator()
    return ArgosTranslator()
