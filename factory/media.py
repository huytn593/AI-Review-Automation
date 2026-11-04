"""CPU renderer with per-scene audio and burned-in subtitles."""
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import signal
import time
import os
from pathlib import Path
import subprocess

from .tts import CommandTTS


_checkpoint = ContextVar("render_checkpoint", default=None)


def execute(*args, cwd=None, timeout=600):
    checkpoint = _checkpoint.get()
    with subprocess.Popen(
        args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding="utf-8", errors="replace", start_new_session=os.name != "nt",
    ) as process:
        started = time.monotonic()
        logger = logging.getLogger(__name__)
        logger.info("process start at=%s pid=%s cwd=%s target=%s tool=%s",
                    datetime.now(timezone.utc).isoformat(), process.pid, cwd, args[-1], args[0])
        deadline = started + timeout
        try:
            while True:
                if checkpoint:
                    checkpoint()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(args, timeout)
                try:
                    out, err = process.communicate(timeout=min(.25, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            if process.poll() is None:
                if os.name == "nt":
                    try:
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                       capture_output=True, timeout=10, check=True)
                    except (OSError, subprocess.SubprocessError):
                        process.kill()
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            process.communicate()
            raise
        finally:
            logger.info("process end at=%s pid=%s cwd=%s target=%s exit=%s elapsed=%.3fs",
                        datetime.now(timezone.utc).isoformat(), process.pid, cwd, args[-1], process.returncode, time.monotonic() - started)
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, args, out, err)
        return out, err


def run(*args, cwd=None, timeout=600):
    return execute(*args, cwd=cwd, timeout=timeout)[0]


class NvencFailure(RuntimeError):
    pass


def encode_scene(encoder, *args, **kwargs):
    try:
        return run(*args, **kwargs)
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or "").lower()
        if encoder == "h264_nvenc" and any(
            "[h264_nvenc" in line and any(marker in line for marker in (
                "cannot load", "no capable devices", "openencodesession",
                "initializeencoder", "driver does not support", "out of memory",
            )) for line in message.splitlines()
        ):
            raise NvencFailure(message) from exc
        raise


def timestamp(seconds):
    total = round(seconds * 1000)
    minutes, ms = divmod(total, 60000)
    hours, minutes = divmod(minutes, 60)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


def render(folder: Path, scenes, format_name, voice, demo_path=None, checkpoint=lambda: None, settings=None):
    token = _checkpoint.set(checkpoint)
    try:
        try:
            return _render(folder, scenes, format_name, voice, demo_path, checkpoint, settings=settings)
        except NvencFailure:
            logging.getLogger(__name__).warning("NVENC failed during encoding; retrying with libx264")
            return _render(folder, scenes, format_name, voice, demo_path, checkpoint, force_cpu=True, settings=settings)
    finally:
        (folder / "video.partial.mp4").unlink(missing_ok=True)
        _checkpoint.reset(token)


def _render(folder, scenes, format_name, voice, demo_path, checkpoint, force_cpu=False, settings=None):
    settings = settings or {}
    width, height = (1080, 1920) if format_name == "short" else (1920, 1080)
    if demo_path is not None and not demo_path.is_file():
        raise ValueError("Thiếu file demo")
    encoder = "libx264"
    if not force_cpu and settings.get("encoder", os.getenv("FACTORY_ENCODER", "auto")) != "cpu":
        try:
            run("ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                f"color=s={width}x{height}", "-frames:v", "1", "-pix_fmt", "yuv420p",
                "-c:v", "h264_nvenc", "-f", "null", "-", timeout=15)
            encoder = "h264_nvenc"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
    logging.getLogger(__name__).info("Render encoder: %s", encoder)
    timeline, captions, playlist = [], [], []
    elapsed = 0.0
    for index, scene in enumerate(scenes):
        checkpoint()
        wav = f"voice-{index}.wav"
        CommandTTS(run, voice, settings).synthesize(scene.narration, folder / wav, scene.seconds)
        duration = float(run("ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of", "csv=p=0", wav, cwd=folder))
        timeline.append({**scene.model_dump(), "start": elapsed, "duration": duration})
        captions.append(f"{index+1}\n{timestamp(elapsed)} --> "
                        f"{timestamp(elapsed+duration)}\n{scene.caption}\n")
        elapsed += duration
        clip = f"scene-{index}.mp4"
        playlist.append(f"file '{clip}'")
        (folder / "caption.srt").write_text(
            f"1\n00:00:00,000 --> {timestamp(duration)}\n{scene.caption}\n", encoding="utf-8")
        visual = ["-f", "lavfi", "-i", f"color=c=0x152540:s={width}x{height}:r=24"]
        if scene.visual_type == "demo" and demo_path:
            visual = ["-i", str(demo_path)]
        filters = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                   f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x152540,"
                   "setsar=1,fps=24,tpad=stop_mode=clone:stop_duration=20,"
                   "subtitles=caption.srt:force_style='Alignment=2,FontSize=18,Outline=2'")
        encode_scene(encoder, "ffmpeg", "-v", "error", "-y", *visual, "-i", wav,
            "-map", "0:v:0", "-map", "1:a:0", "-filter_threads", "1", "-vf", filters,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-t", str(duration), "-c:v", encoder,
            "-preset", "ultrafast" if encoder == "libx264" else "p1", "-threads", "2", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", clip, cwd=folder)
    checkpoint()
    (folder / "subtitles.srt").write_text("\n".join(captions), encoding="utf-8")
    (folder / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "concat.txt").write_text("\n".join(playlist), encoding="utf-8")
    run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "1", "-i",
        "concat.txt", "-c", "copy", "-movflags", "+faststart", "video.partial.mp4", cwd=folder)
    checkpoint()
    run("ffmpeg", "-v", "error", "-y", "-ss", "0.5", "-i", "video.partial.mp4",
        "-frames:v", "1", "thumbnail.jpg", cwd=folder)
    probe = json.loads(run("ffprobe", "-v", "error", "-show_streams", "-show_format",
                           "-of", "json", "video.partial.mp4", cwd=folder))
    streams = {stream["codec_type"]: stream for stream in probe["streams"]}
    video, audio = streams.get("video", {}), streams.get("audio", {})
    if video.get("pix_fmt") != "yuv420p" or (video.get("codec_name"), video.get("width"), video.get("height")) != ("h264", width, height):
        raise ValueError("Video stream sai codec hoặc kích thước")
    actual_duration = float(probe["format"]["duration"])
    if audio.get("codec_name") != "aac" or abs(actual_duration - elapsed) > max(.25, len(scenes) * .06):
        raise ValueError("Audio stream hoặc thời lượng MP4 không hợp lệ")
    _, audio_log = execute("ffmpeg", "-hide_banner", "-i", "video.partial.mp4", "-vn", "-af",
                           "silencedetect=n=-50dB:d=0.5", "-f", "null", "-", cwd=folder, timeout=120)
    _, black_log = execute("ffmpeg", "-hide_banner", "-i", "video.partial.mp4", "-an", "-vf",
                           "blackdetect=d=0.5:pix_th=0.10", "-f", "null", "-", cwd=folder, timeout=120)
    import re
    silent = sum(float(value) for value in re.findall(r"silence_duration: ([0-9.]+)", audio_log))
    (folder / "technical.json").write_text(json.dumps({
        "encoder": encoder, "black_intervals": re.findall(r"black_start:([0-9.]+)", black_log), "audio_silence_seconds": silent,
        "mostly_silent": silent >= actual_duration * .95,
        "duration": actual_duration,
    }), encoding="utf-8")
    checkpoint()
    (folder / "video.partial.mp4").replace(folder / "video.mp4")
    return elapsed
