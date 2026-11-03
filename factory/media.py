"""CPU renderer with per-scene audio and burned-in subtitles."""
import json
import os
from pathlib import Path
import subprocess

from .tts import CommandTTS


def run(*args, cwd=None, timeout=600):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True,
                          encoding="utf-8", errors="replace", timeout=timeout).stdout


def timestamp(seconds):
    total = round(seconds * 1000)
    minutes, ms = divmod(total, 60000)
    hours, minutes = divmod(minutes, 60)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


def render(folder: Path, scenes, format_name, voice, demo_path=None, checkpoint=lambda: None):
    width, height = (1080, 1920) if format_name == "short" else (1920, 1080)
    if demo_path is not None and not demo_path.is_file():
        raise ValueError("Thiếu file demo")
    encoder = "libx264"
    if os.getenv("FACTORY_ENCODER", "auto") != "cpu":
        try:
            run("ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                f"color=s={width}x{height}", "-frames:v", "1", "-pix_fmt", "yuv420p",
                "-c:v", "h264_nvenc", "-f", "null", "-", timeout=15)
            encoder = "h264_nvenc"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
    timeline, captions, playlist = [], [], []
    elapsed = 0.0
    for index, scene in enumerate(scenes):
        checkpoint()
        wav = f"voice-{index}.wav"
        CommandTTS(run, voice).synthesize(scene.narration, folder / wav, scene.seconds)
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
        run("ffmpeg", "-v", "error", "-y", *visual, "-i", wav,
            "-map", "0:v:0", "-map", "1:a:0", "-filter_threads", "1", "-vf", filters,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-t", str(duration), "-c:v", encoder,
            "-preset", "ultrafast" if encoder == "libx264" else "p1", "-threads", "2", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", clip, cwd=folder)
    checkpoint()
    (folder / "subtitles.srt").write_text("\n".join(captions), encoding="utf-8")
    (folder / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "concat.txt").write_text("\n".join(playlist), encoding="utf-8")
    run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "1", "-i",
        "concat.txt", "-c", "copy", "-movflags", "+faststart", "video.mp4", cwd=folder)
    run("ffmpeg", "-v", "error", "-y", "-ss", "0.5", "-i", "video.mp4",
        "-frames:v", "1", "thumbnail.jpg", cwd=folder)
    probe = json.loads(run("ffprobe", "-v", "error", "-show_streams", "-show_format",
                           "-of", "json", "video.mp4", cwd=folder))
    streams = {stream["codec_type"]: stream for stream in probe["streams"]}
    video, audio = streams.get("video", {}), streams.get("audio", {})
    if (video.get("codec_name"), video.get("width"), video.get("height")) != ("h264", width, height):
        raise ValueError("Video stream sai codec hoặc kích thước")
    actual_duration = float(probe["format"]["duration"])
    if audio.get("codec_name") != "aac" or abs(actual_duration - elapsed) > max(.25, len(scenes) * .06):
        raise ValueError("Audio stream hoặc thời lượng MP4 không hợp lệ")
    audio_log = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", "video.mp4", "-vn", "-af",
         "silencedetect=n=-50dB:d=0.5", "-f", "null", "-"], cwd=folder,
        check=True, capture_output=True, encoding="utf-8", errors="replace", timeout=120,
    ).stderr
    import re
    silent = sum(float(value) for value in re.findall(r"silence_duration: ([0-9.]+)", audio_log))
    (folder / "technical.json").write_text(json.dumps({
        "encoder": encoder, "audio_silence_seconds": silent,
        "mostly_silent": silent >= actual_duration * .95,
        "duration": actual_duration,
    }), encoding="utf-8")
    return elapsed
