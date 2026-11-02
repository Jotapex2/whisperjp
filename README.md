# Transcriptor de directos

Aplicación local para capturar el audio de un directo público de YouTube, transcribirlo con Whisper y guardar una transcripción continua junto con archivos Markdown por intervalos de cinco minutos.

## Requisitos

- Python 3.11 o posterior
- FFmpeg
- Una máquina encendida y conectada durante el directo
- `yt-dlp` debe poder acceder al directo según las condiciones de YouTube y del canal

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## Uso

```bash
python -m transcriptor "https://www.youtube.com/live/Fxsd4UYqFAU" --output transcripciones
```

El sistema extrae audio en fragmentos de 30 segundos, transcribe cada fragmento y actualiza `transcripcion.md` en vivo. Al completar cada bloque de cinco minutos, crea `bloques/bloque-0000.md`, `bloques/bloque-0005.md`, etc. Los tiempos se cuentan desde el inicio de la captura.

Para seleccionar idioma, por ejemplo español:

```bash
python -m transcriptor URL --language es
```

La primera ejecución de faster-whisper puede descargar el modelo elegido (por defecto `small`). Para hardware limitado, usa `--model base`; para más calidad, `--model medium`.

## Identificación de hablantes

La versión inicial etiqueta todos los fragmentos como `Hablante no identificado`. La transcripción automática no conoce nombres reales. Para mostrar `Voz 1`, `Voz 2` con diarización se debe configurar un proveedor/modelo de diarización y sus credenciales; el programa no hace reconocimiento biométrico ni intenta averiguar identidades. No atribuyas una voz a una persona sin confirmación independiente.

## Límites

- GitHub Actions no es adecuado para capturar un directo largo continuamente; este programa se ejecuta en una computadora o servidor propio.
- No envía mensajes cada cinco minutos: guarda bloques y los va actualizando localmente. Se puede integrar más adelante con un canal de notificación.
- La disponibilidad del stream depende de que sea público y accesible para yt-dlp. Respeta derechos, privacidad y términos de servicio.
- Si el proceso se interrumpe, los fragmentos y transcripción ya escritos permanecen en disco.

## Archivos

- `transcripcion.md`: transcripción acumulada
- `bloques/`: resúmenes textuales por intervalo
- `audio/`: fragmentos temporales, borrados al procesarse correctamente

```text
live-transcriptor/
  transcriptor/
    __init__.py
    __main__.py
```
