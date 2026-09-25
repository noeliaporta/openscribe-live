"""Gestor de sesiones y pipeline de subtítulos en tiempo real.

Cada Session:
- recibe chunks de audio PCM (16-bit mono) de un ingestor (escenario),
- acumula ~CHUNK_SECONDS de audio, transcribe y traduce en un worker,
- guarda cues para exportar (SRT/VTT/txt),
- difunde cada subtítulo a las colas de los suscriptores (audiencia).

Escalar a N escenarios = crear N sesiones. El SessionManager las mantiene en
un dict; cada una corre su propio worker asíncrono e independiente.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Set

from . import config


@dataclass
class Subtitle:
    session_id: str
    start: float
    end: float
    original: str
    lang: str
    translations: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "start": self.start,
            "end": self.end,
            "original": self.original,
            "lang": self.lang,
            "translations": self.translations,
        }


class Session:
    def __init__(self, session_id: str, name: str, transcriber, translator,
                 src_lang: str = "auto", targets: List[str] | None = None,
                 processor=None):
        self.id = session_id
        self.name = name
        self.transcriber = transcriber
        self.translator = translator
        # si hay processor (pipeline gemini_av) transcribe+traduce en 1 llamada
        self.processor = processor
        self.src_lang = src_lang
        # idiomas de salida que ofrecemos a la audiencia
        self.targets = targets or ["es", "en"]
        self.subscribers: Set[asyncio.Queue] = set()
        self.cues: List[dict] = []
        self._pcm = bytearray()
        self._start_wall = time.time()
        self._bytes_per_chunk = int(
            config.SAMPLE_RATE * 2 * config.CHUNK_SECONDS)
        self._lock = asyncio.Lock()
        self._loop = asyncio.get_event_loop()
        self.last_latency = 0.0
        self.error: str | None = None

    # -- ingesta -------------------------------------------------------------
    async def push_audio(self, pcm: bytes) -> None:
        self._pcm.extend(pcm)
        while len(self._pcm) >= self._bytes_per_chunk:
            chunk = bytes(self._pcm[: self._bytes_per_chunk])
            del self._pcm[: self._bytes_per_chunk]
            asyncio.create_task(self._process(chunk))

    async def _process(self, chunk: bytes) -> None:
        t0 = time.time()
        rel = t0 - self._start_wall
        try:
            # correr modelos (bloqueantes) en un thread para no frenar el loop
            if self.processor is not None:
                # Gemini escucha y traduce en una sola llamada (mejor calidad).
                text, detected, translations = await asyncio.to_thread(
                    self.processor.process, chunk, config.SAMPLE_RATE, self.targets)
                if not text:
                    return
                src = detected or (self.src_lang if self.src_lang != "auto" else "en")
            else:
                text, detected = await asyncio.to_thread(
                    self.transcriber.transcribe, chunk, config.SAMPLE_RATE)
                if not text:
                    return
                src = detected or (self.src_lang if self.src_lang != "auto" else "en")
                translations = {}
                for tgt in self.targets:
                    if tgt == src:
                        continue
                    translations[tgt] = await asyncio.to_thread(
                        self.translator.translate, text, src, tgt)
            sub = Subtitle(
                session_id=self.id, start=rel,
                end=rel + config.CHUNK_SECONDS,
                original=text, lang=src, translations=translations)
            self.cues.append({"start": sub.start, "end": sub.end, "text": text})
            self.last_latency = time.time() - t0
            print(f"[{self.id}] bloque procesado en {self.last_latency:.1f}s"
                  f" | {src} -> {list(translations.keys())} | \"{text[:60]}\"")
            await self._broadcast(sub)
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
            print(f"[{self.id}] ERROR al procesar bloque: {e}")

    # -- difusión ------------------------------------------------------------
    async def _broadcast(self, sub: Subtitle) -> None:
        for q in list(self.subscribers):
            try:
                q.put_nowait(sub.as_dict())
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)

    def status(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "src_lang": self.src_lang,
            "targets": self.targets,
            "subscribers": len(self.subscribers),
            "cues": len(self.cues),
            "latency": round(self.last_latency, 2),
            "error": self.error,
        }


class SessionManager:
    def __init__(self, transcriber, translator, processor=None):
        self.transcriber = transcriber
        self.translator = translator
        self.processor = processor
        self.sessions: Dict[str, Session] = {}

    def create(self, session_id: str, name: str, src_lang: str = "auto",
               targets: List[str] | None = None) -> Session:
        if session_id in self.sessions:
            return self.sessions[session_id]
        s = Session(session_id, name, self.transcriber, self.translator,
                    src_lang, targets, processor=self.processor)
        self.sessions[session_id] = s
        return s

    def get(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    def list(self) -> List[dict]:
        return [s.status() for s in self.sessions.values()]
