# Audios de prueba

Colocá acá audios de charlas para probar el proyecto sin micrófono.

Podés bajar el audio de cualquier charla de Nerdearla de YouTube. Ejemplo con
`yt-dlp` (no incluido en las dependencias):

```bash
yt-dlp -x --audio-format wav -o "samples/charla_en.%(ext)s" "<URL_DE_YOUTUBE>"
```

Luego enviala a una sesión como si fuera un stream en vivo:

```bash
python scripts/stream_file.py samples/charla_en.wav --session escenario-1
```

El script usa `ffmpeg` para convertir cualquier formato a PCM 16 kHz mono, así
que acepta `.wav`, `.mp3`, `.m4a`, etc.
