"""Configuración central del servidor.

Toda la config se lee de variables de entorno (ver .env.example) para que
desplegar en otra conferencia sea solo cambiar un archivo .env. El .env se
carga automáticamente al importar este módulo.
"""
import os

# Cargar .env automáticamente si python-dotenv está instalado.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _get(name: str, default: str) -> str:
    return os.environ.get(name, default)


# --- Pipeline ----------------------------------------------------------------
# "split"      = transcribir (whisper/gemini) y luego traducir (argos/gemini).
# "gemini_av"  = una sola llamada a Gemini: audio -> transcripción + traducción.
PIPELINE = _get("PIPELINE", "split")

# --- Backends intercambiables (modo split) -----------------------------------
# Transcripción: "whisper" (100% local, faster-whisper) o "gemini" (API).
TRANSCRIBE_BACKEND = _get("TRANSCRIBE_BACKEND", "whisper")
# Traducción: "argos" (100% local) o "gemini" (API).
TRANSLATE_BACKEND = _get("TRANSLATE_BACKEND", "argos")

# --- Whisper (local) ---------------------------------------------------------
# tiny / base / small / medium / large-v3 . Para tiempo real usar tiny o base.
WHISPER_MODEL = _get("WHISPER_MODEL", "base")
WHISPER_DEVICE = _get("WHISPER_DEVICE", "cpu")        # cpu | cuda
WHISPER_COMPUTE = _get("WHISPER_COMPUTE", "int8")     # int8 | float16 | float32

# --- Gemini (API) ------------------------------------------------------------
GEMINI_API_KEY = _get("GEMINI_API_KEY", "")
GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-3.8-flash")
# Reintentos ante errores transitorios (ej. 503 UNAVAILABLE).
GEMINI_RETRIES = int(_get("GEMINI_RETRIES", "3"))

# --- Audio -------------------------------------------------------------------
SAMPLE_RATE = int(_get("SAMPLE_RATE", "16000"))   # Hz, mono, PCM 16-bit
# Segundos de audio que se acumulan antes de procesar un bloque.
CHUNK_SECONDS = float(_get("CHUNK_SECONDS", "4.0"))

# --- Glosario ----------------------------------------------------------------
# Ruta a un JSON {"termino": "traducción"} para nombres propios / términos técnicos.
GLOSSARY_PATH = _get("GLOSSARY_PATH", "glossary.json")

# --- Servidor ----------------------------------------------------------------
HOST = _get("HOST", "127.0.0.1")
PORT = int(_get("PORT", "8000"))
