#!/usr/bin/env python3
"""Envía un archivo de audio a una sesión como si fuera un stream en vivo.

Útil para probar el proyecto sin micrófono y para simular varios escenarios
en paralelo (corré este script N veces con distintos --session).

Ejemplo:
    python scripts/stream_file.py samples/charla_en.wav --session escenario-1
    python scripts/stream_file.py samples/charla_es.wav --session escenario-2

Requiere ffmpeg en el PATH para convertir a PCM 16 kHz mono.
"""
import argparse
import asyncio
import subprocess
import sys

import websockets  # pip install websockets

SR = 16000
CHUNK_MS = 200  # tamaño de envío


def decode_to_pcm(path: str) -> bytes:
    """Convierte cualquier audio a PCM 16-bit mono 16 kHz usando ffmpeg."""
    cmd = [
        "ffmpeg", "-v", "quiet", "-i", path,
        "-ac", "1", "-ar", str(SR), "-f", "s16le", "pipe:1",
    ]
    return subprocess.run(cmd, capture_output=True, check=True).stdout


async def stream(path: str, session: str, host: str, realtime: bool) -> None:
    pcm = decode_to_pcm(path)
    bytes_per_chunk = int(SR * 2 * CHUNK_MS / 1000)
    uri = f"ws://{host}/ws/ingest/{session}"
    async with websockets.connect(uri, max_size=None) as ws:
        print(f"Enviando {len(pcm)} bytes a {uri}")
        for i in range(0, len(pcm), bytes_per_chunk):
            await ws.send(pcm[i:i + bytes_per_chunk])
            if realtime:
                await asyncio.sleep(CHUNK_MS / 1000)
        print("Fin del archivo.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--session", default="escenario-1")
    p.add_argument("--host", default="127.0.0.1:8000")
    p.add_argument("--fast", action="store_true",
                   help="envia sin esperar (no simula tiempo real)")
    args = p.parse_args()
    try:
        asyncio.run(stream(args.file, args.session, args.host, not args.fast))
    except FileNotFoundError:
        print("ffmpeg no encontrado o archivo inexistente", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
