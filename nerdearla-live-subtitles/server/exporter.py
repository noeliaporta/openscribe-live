"""Exportación de la transcripción final a SRT / VTT / texto plano.

Cada célula (cue) es un dict: {start, end, text} con tiempos en segundos.
"""
from __future__ import annotations

from typing import List, Dict


def _ts(seconds: float, sep: str) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def to_srt(cues: List[Dict]) -> str:
    lines = []
    for i, c in enumerate(cues, 1):
        lines.append(str(i))
        lines.append(f"{_ts(c['start'], ',')} --> {_ts(c['end'], ',')}")
        lines.append(c["text"].strip())
        lines.append("")
    return "\n".join(lines)


def to_vtt(cues: List[Dict]) -> str:
    lines = ["WEBVTT", ""]
    for c in cues:
        lines.append(f"{_ts(c['start'], '.')} --> {_ts(c['end'], '.')}")
        lines.append(c["text"].strip())
        lines.append("")
    return "\n".join(lines)


def to_text(cues: List[Dict]) -> str:
    return "\n".join(c["text"].strip() for c in cues if c["text"].strip())
