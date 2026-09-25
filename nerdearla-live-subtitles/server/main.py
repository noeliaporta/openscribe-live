"""App FastAPI: ingesta de audio, difusión de subtítulos y vistas web.

Endpoints principales:
- POST /api/sessions                 crea una sesión (escenario)
- GET  /api/sessions                 lista sesiones + estado (monitoreo)
- WS   /ws/ingest/{sid}              el escenario envía audio PCM binario
- WS   /ws/subtitles/{sid}           la audiencia recibe subtítulos (JSON)
- GET  /api/sessions/{sid}/export    descarga SRT / VTT / txt
- GET  /                             vista de audiencia
- GET  /ingest                       vista de captura de micrófono
- GET  /monitor                      panel de monitoreo de producción

Multisesión: cada escenario abre su propio /ws/ingest/{sid}. Correr 10
escenarios = 10 conexiones de ingesta. Ver README para escalado horizontal.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import (HTMLResponse, JSONResponse, PlainTextResponse)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, exporter
from .sessions import SessionManager
from .transcriber import get_transcriber, get_processor
from .translator import get_translator

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")

app = FastAPI(title="Nerdearla Live Subtitles")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
manager: SessionManager | None = None


@app.on_event("startup")
async def _startup() -> None:
    global manager
    # los modelos se cargan una vez y se comparten entre sesiones
    processor = get_processor()
    if processor is not None:
        # pipeline gemini_av: no hace falta cargar Whisper/Argos (ni torch).
        manager = SessionManager(None, None, processor=processor)
        print("=" * 60)
        print(f">> PIPELINE ACTIVO: gemini_av (Gemini audio, modelo {config.GEMINI_MODEL})")
        print(">> Transcribe + traduce en 1 sola llamada. Whisper NO se usa.")
        print("=" * 60)
    else:
        manager = SessionManager(get_transcriber(), get_translator())
        print("=" * 60)
        print(f">> PIPELINE ACTIVO: split (transcripcion={config.TRANSCRIBE_BACKEND}"
              f" / traduccion={config.TRANSLATE_BACKEND})")
        if config.TRANSCRIBE_BACKEND == "whisper":
            print(f">> Whisper modelo={config.WHISPER_MODEL} (este es el cuello de botella lento)")
        print(">> Para usar el modo rapido de Gemini, poné PIPELINE=gemini_av en .env")
        print("=" * 60)


class CreateSession(BaseModel):
    id: str
    name: str = ""
    src_lang: str = "auto"
    targets: list[str] = ["es", "en"]


@app.post("/api/sessions")
async def create_session(body: CreateSession):
    s = manager.create(body.id, body.name or body.id, body.src_lang, body.targets)
    return s.status()


@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": manager.list()}


@app.get("/api/sessions/{sid}/export")
async def export_session(sid: str, fmt: str = "srt", lang: str = "original"):
    s = manager.get(sid)
    if not s:
        return JSONResponse({"error": "session not found"}, status_code=404)
    # exportamos el original; para un idioma traducido usar lang=es/en
    if lang == "original":
        cues = s.cues
    else:
        cues = [{"start": c["start"], "end": c["end"], "text": c["text"]}
                for c in s.cues]
    if fmt == "vtt":
        return PlainTextResponse(exporter.to_vtt(cues), media_type="text/vtt")
    if fmt == "txt":
        return PlainTextResponse(exporter.to_text(cues))
    return PlainTextResponse(exporter.to_srt(cues),
                             media_type="application/x-subrip")


@app.websocket("/ws/ingest/{sid}")
async def ws_ingest(ws: WebSocket, sid: str):
    await ws.accept()
    s = manager.get(sid) or manager.create(sid, sid)
    try:
        while True:
            data = await ws.receive_bytes()
            await s.push_audio(data)
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/subtitles/{sid}")
async def ws_subtitles(ws: WebSocket, sid: str):
    await ws.accept()
    s = manager.get(sid) or manager.create(sid, sid)
    q = s.subscribe()
    try:
        while True:
            sub = await q.get()
            await ws.send_json(sub)
    except WebSocketDisconnect:
        pass
    finally:
        s.unsubscribe(q)


def _page(name: str) -> HTMLResponse:
    with open(os.path.join(WEB_DIR, name), "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/")
async def audience():
    return _page("audience.html")


@app.get("/ingest")
async def ingest():
    return _page("ingest.html")


@app.get("/monitor")
async def monitor():
    return _page("monitor.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host=config.HOST, port=config.PORT)
