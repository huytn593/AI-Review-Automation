"""CPU renderer with per-scene audio and burned-in subtitles."""
import json
import os
from pathlib import Path
import subprocess


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True,
                          text=True, timeout=600).stdout


def timestamp(seconds):
    total = round(seconds * 1000)
    minutes, ms = divmod(total, 60000)
    hours, minutes = divmod(minutes, 60)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


def render(folder: Path, scenes, format_name, voice, demo_path=None):
    width, height = (1080, 1920) if format_name == "short" else (1920, 1080)
    timeline, captions, playlist = [], [], []
    elapsed = 0.0
    for index, scene in enumerate(scenes):
        wav = f"voice-{index}.wav"
        if voice == "mock":
            run("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                "anullsrc=r=48000:cl=mono", "-t", str(scene.seconds), wav, cwd=folder)
        else:
            run(os.getenv("ESPEAK_BIN", "espeak-ng"), "-v", voice, "-w", wav,
                scene.narration, cwd=folder)
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
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-t", str(duration), "-c:v", "libx264",
            "-preset", "ultrafast", "-threads", "2", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", clip, cwd=folder)
    (folder / "subtitles.srt").write_text("\n".join(captions), encoding="utf-8")
    (folder / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "concat.txt").write_text("\n".join(playlist), encoding="utf-8")
    run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "1", "-i",
        "concat.txt", "-c", "copy", "-movflags", "+faststart", "video.mp4", cwd=folder)
    run("ffmpeg", "-v", "error", "-y", "-ss", "0.5", "-i", "video.mp4",
        "-frames:v", "1", "thumbnail.jpg", cwd=folder)
    return elapsed
