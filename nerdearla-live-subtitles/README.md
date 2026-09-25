# Nerdearla Live Subtitles 🎙️

Solución **open source** de transcripción y traducción simultánea **a escala**
para conferencias. Toma audio en vivo de un escenario y genera subtítulos en
tiempo real: transcripción en el idioma original y traducción a español e
inglés. Soporta **múltiples sesiones en paralelo** (varios escenarios) y una
vista web donde cada persona elige su sesión y su idioma.

> Hecho para la **Nerdearla Vibeathon**. Licencia **MIT** (aprobada por la OSI).

## ✨ Qué hace

- 🎙️ **Transcripción en vivo** del idioma original (español o inglés, autodetectado).
- 🌎 **Traducción en vivo** EN→ES (y ES→EN, y más idiomas si el backend lo permite).
- 👥 **Multisesión**: 2, 5, 10+ escenarios en simultáneo, cada uno aislado.
- 📺 **Vista de audiencia**: web donde se elige sesión + idioma.
- 📊 **Panel de monitoreo**: estado, latencia, líneas y errores por sesión.
- 💾 **Exportación** al final de cada charla: SRT / VTT / texto.
- 📖 **Glosario** de términos técnicos y nombres propios.
- 🔌 **Backends intercambiables**: 100% local (Whisper + Argos), API (Gemini),
  o **modo combinado Gemini** que transcribe y traduce en una sola llamada.

## 🏗️ Arquitectura

```
  Escenario 1 ] --audio PCM--> WS /ws/ingest/escenario-1 --.
  Escenario 2 ] --audio PCM--> WS /ws/ingest/escenario-2 --|
                                                            v
                                                   +------------------+
                                                   |  SessionManager  |
                                                   |  (1 worker por   |
                                                   |   sesión)        |
                                                   +--------+---------+
                                    transcribe (Whisper/Gemini)
                                    translate  (Argos/Gemini)
                                                            |
                                                            v
  Audiencia ] <--subtítulos JSON-- WS /ws/subtitles/{sesion} (pub/sub)
```

Cada sesión acumula ~4 s de audio, transcribe, traduce a los idiomas de salida
y difunde el resultado a todas las personas suscriptas a esa sesión. Los
modelos corren en un thread aparte para no bloquear el bucle asíncrono.

## 🚀 Cómo levantarlo

Requisitos: **Python 3.10–3.12** (⚠️ **no** uses 3.13: `sentencepiece` aún no
compila) y **ffmpeg** (solo para el script de prueba con archivos).

> **Windows**: si `pip install` falla al compilar `torch`/`ctranslate2`, instalá
> el runtime de Visual C++:
> `winget install Microsoft.VCRedist.2015+.x64`. Con el modo combinado Gemini
> (`PIPELINE=gemini_av`) esto **no** hace falta: no se instala Whisper ni torch.

```bash
git clone <tu-repo> && cd nerdearla-live-subtitles
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # ajustá si querés (funciona con los defaults)
```

### Modelos / credenciales que necesita

| Backend | Variable | Qué necesita |
|---|---|---|
| **Whisper** (transcripción, *default*) | `TRANSCRIBE_BACKEND=whisper` | Nada. Descarga el modelo (`base`) la primera vez. 100% local. |
| **Argos** (traducción, *default*) | `TRANSLATE_BACKEND=argos` | Paquetes de idioma (ver abajo). 100% local. |
| **Gemini** (transcripción y/o traducción) | `TRANSCRIBE_BACKEND=gemini` / `TRANSLATE_BACKEND=gemini` | `GEMINI_API_KEY` en `.env`. |
| **Gemini combinado** (transcribe **+** traduce en 1 llamada) | `PIPELINE=gemini_av` | `GEMINI_API_KEY` en `.env`. No necesita Whisper/Argos/torch. Mejor calidad y menor latencia. |

> El archivo `.env` se carga solo (via `python-dotenv`). En Windows/PowerShell
> también podés exportar la clave a mano: `$env:GEMINI_API_KEY="tu-clave"`.
>
> **Recomendado para la demo**: poné en `.env`:
>
> ```
> PIPELINE=gemini_av
> GEMINI_API_KEY=tu-clave
> GEMINI_MODEL=gemini-3.8-flash
> ```

Instalar paquetes de Argos para EN↔ES (una sola vez):

```bash
python -c "import argostranslate.package as p; p.update_package_index(); \
[p.install_from_path(x.download()) for x in p.get_available_packages() \
if (x.from_code,x.to_code) in [('en','es'),('es','en')]]"
```

### Arrancar el servidor

```bash
python -m server.main         # o: uvicorn server.main:app --port 8000
```

Abrí en el navegador:

- **`/`** → vista de audiencia (elegí sesión + idioma).
- **`/ingest`** → captura de micrófono para un escenario.
- **`/monitor`** → panel de monitoreo de producción.

## 🧪 Probar con audios (sin micrófono)

Poné un audio en `samples/` (ver `samples/README.md` para bajar charlas de
Nerdearla desde YouTube) y envialo como si fuera un stream en vivo:

```bash
python scripts/stream_file.py samples/charla_en.wav --session escenario-1
```

Luego abrí `/` y elegí la sesión `escenario-1` con idioma **Español** para ver
la traducción en vivo.

## 👥 Dos (o más) sesiones en simultáneo

En dos terminales:

```bash
python scripts/stream_file.py samples/charla_en.wav --session escenario-1
python scripts/stream_file.py samples/charla_es.wav --session escenario-2
```

Cada sesión es independiente. En `/` aparecen ambas para elegir; en `/monitor`
se ve el estado de las dos.

## 📈 Cómo escalar a más escenarios

- **En una máquina**: cada sesión es un worker asíncrono ligero; el límite real
  es la capacidad de inferencia. Con Whisper `base` en CPU alcanza para unas
  pocas sesiones; para 10+ conviene GPU (`WHISPER_DEVICE=cuda`), un modelo más
  chico (`tiny`), o el backend Gemini que descarga el cómputo a la API.
- **Horizontal (recomendado a escala)**: como cada sesión se identifica por su
  `session_id` en la URL del WebSocket, se pueden correr **N instancias del
  servidor** (una o varias sesiones cada una) detrás de un reverse proxy
  (nginx/traefik) que rutee `/ws/ingest/{sid}` y `/ws/subtitles/{sid}` por
  `sid`. Cada instancia es *stateless* respecto de las demás.
- **Contenedores**: empaquetar con Docker y escalar réplicas (K8s/Compose),
  una o dos sesiones por réplica para acotar la latencia.
- Ajustá `CHUNK_SECONDS` para balancear latencia vs. precisión (menos segundos
  = más rápido pero más cortado).

## 🧩 Checklist del MVP (Vibeathon)

- [x] Recibe audio en vivo de al menos una fuente (micrófono **y** archivo/stream).
- [x] Transcripción en tiempo real del idioma original (ES o EN, autodetectado).
- [x] Traducción en tiempo real EN→ES (y ES→EN).
- [x] Muestra subtítulos (vista web de audiencia).
- [x] Procesa ≥ 2 sesiones en simultáneo + cómo escalar (esta sección).
- [x] Licencia OSI (**MIT**) + README para desplegar.

Opcionales ya incluidos: exportación SRT/VTT/txt, glosario, panel de monitoreo,
soporte multi-idioma (agregá códigos en `targets` al crear la sesión, ej. `pt`).

## 🔌 API breve

| Método | Ruta | Uso |
|---|---|---|
| POST | `/api/sessions` | crea sesión `{id, name, src_lang, targets}` |
| GET | `/api/sessions` | lista sesiones + estado |
| WS | `/ws/ingest/{sid}` | ingesta de audio PCM 16-bit mono 16 kHz |
| WS | `/ws/subtitles/{sid}` | recibe subtítulos JSON |
| GET | `/api/sessions/{sid}/export?fmt=srt\|vtt\|txt` | descarga transcripción |

## 📄 Licencia

MIT — ver [LICENSE](LICENSE). Uso libre para cualquier conferencia.
