from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path


CHUNK_SECONDS = 30
BLOCK_SECONDS = 5 * 60


def stamp(seconds: float) -> str:
    return str(timedelta(seconds=max(0, int(seconds))))


@dataclass
class Utterance:
    start: float
    end: float
    text: str
    speaker: str = "Hablante no identificado"


def get_audio_url(url: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--no-warnings", "-f", "bestaudio/best", "-g", url],
        check=True,
        capture_output=True,
        text=True,
    )
    audio_url = result.stdout.strip().splitlines()[0]
    if not audio_url:
        raise RuntimeError("yt-dlp no devolvió una URL de audio.")
    return audio_url


def start_capture(url: str, audio_dir: Path) -> tuple[subprocess.Popen, subprocess.Popen]:
    downloader = subprocess.Popen(
        [sys.executable, "-m", "yt_dlp", "--no-warnings", "-f", "bestaudio/best", "-o", "-", url],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert downloader.stdout is not None
    ffmpeg = subprocess.Popen(
        [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            "-f", "segment", "-segment_time", str(CHUNK_SECONDS), "-reset_timestamps", "1",
            str(audio_dir / "chunk-%08d.wav"),
        ],
        stdin=downloader.stdout,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    downloader.stdout.close()
    return downloader, ffmpeg


def render(rows: list[Utterance], start: float, end: float) -> str:
    lines = [f"# Transcripción: {stamp(start)}–{stamp(end)}", ""]
    for row in rows:
        if row.end <= start or row.start >= end:
            continue
        lines.append(f"- **[{stamp(row.start)}] {row.speaker}:** {row.text}")
    if len(lines) == 2:
        lines.append("_Sin voz reconocida en este intervalo._")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe un directo accesible por URL.")
    parser.add_argument("url", help="URL pública del directo")
    parser.add_argument("--output", type=Path, default=Path("transcripciones"))
    parser.add_argument("--model", default="small", help="Modelo faster-whisper: tiny, base, small, medium o large-v3")
    parser.add_argument("--language", default=None, help="Idioma de audio, por ejemplo es; autodetección si se omite")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        parser.error("No se encontró ffmpeg. Instálalo y vuelve a ejecutar.")
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        parser.error("Faltan dependencias. Ejecuta: pip install -r requirements.txt")

    args.output.mkdir(parents=True, exist_ok=True)
    audio_dir = args.output / "audio"
    blocks_dir = args.output / "bloques"
    audio_dir.mkdir(exist_ok=True)
    blocks_dir.mkdir(exist_ok=True)
    print("Conectando al directo…", flush=True)
    model = WhisperModel(args.model, device=args.device, compute_type="int8" if args.device == "cpu" else "float16")
    rows: list[Utterance] = []
    downloader, ffmpeg = start_capture(args.url, audio_dir)
    chunk_number = 0
    last_block = -1

    try:
        while True:
            path = audio_dir / f"chunk-{chunk_number:08d}.wav"
            next_path = audio_dir / f"chunk-{chunk_number + 1:08d}.wav"
            while not next_path.exists() and ffmpeg.poll() is None:
                time.sleep(0.5)
            if not path.exists() or path.stat().st_size <= 44:
                print("No se obtuvo más audio; finalizando.", flush=True)
                break

            offset = chunk_number * CHUNK_SECONDS
            segments, _ = model.transcribe(str(path), language=args.language, vad_filter=True)
            for segment in segments:
                text = re.sub(r"\s+", " ", segment.text).strip()
                if text:
                    rows.append(Utterance(offset + segment.start, offset + segment.end, text))
                    print(f"[{stamp(offset + segment.start)}] {text}", flush=True)
            path.unlink(missing_ok=True)

            full_text = "# Transcripción en vivo\n\n" + "\n".join(
                f"- **[{stamp(r.start)}] {r.speaker}:** {r.text}" for r in rows
            ) + "\n"
            (args.output / "transcripcion.md").write_text(full_text, encoding="utf-8")
            finished_time = offset + CHUNK_SECONDS
            block_index = int(finished_time // BLOCK_SECONDS)
            if block_index > last_block:
                for index in range(last_block + 1, block_index + 1):
                    block_start = index * BLOCK_SECONDS
                    block_end = block_start + BLOCK_SECONDS
                    block_file = blocks_dir / f"bloque-{index * 5:04d}.md"
                    block_file.write_text(render(rows, block_start, block_end), encoding="utf-8")
                    print(f"Bloque guardado: {block_file}", flush=True)
                last_block = block_index
            chunk_number += 1
    except KeyboardInterrupt:
        print("\nCaptura detenida. Se conserva la transcripción guardada.", flush=True)
    except subprocess.CalledProcessError as exc:
        print(f"Error al obtener el stream: {exc.stderr or exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        for process in (ffmpeg, downloader):
            if process.poll() is None:
                process.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
