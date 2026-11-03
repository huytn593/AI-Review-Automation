"""Narration adapters. Mock audio is only available for tests and previews."""
import os
from pathlib import Path
import subprocess
import time
from typing import Callable, Protocol
import sys


class TTSProvider(Protocol):
    def synthesize(self, text: str, output: Path, seconds: float) -> None: ...


class CommandTTS:
    def __init__(self, run: Callable, voice: str):
        self.run = run
        self.voice = voice

    def synthesize(self, text: str, output: Path, seconds: float) -> None:
        cwd = output.parent
        if self.voice == "mock":
            self.run("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                     "anullsrc=r=48000:cl=mono", "-t", str(seconds), output.name, cwd=cwd)
            return
        if os.getenv("FACTORY_TTS", "espeak") == "edge":
            source = output.with_suffix(".mp3")
            command = (sys.executable, "-m", "edge_tts", "--voice", self.voice,
                       "--text", text, "--write-media", source.name)
        else:
            source = output
            command = (os.getenv("ESPEAK_BIN", "espeak-ng"), "-v", self.voice,
                       "-w", output.name, "-b", "1", "--", text)
        for attempt in range(2):
            source.unlink(missing_ok=True)
            try:
                self.run(*command, cwd=cwd, timeout=60)
                if source != output:
                    self.run("ffmpeg", "-v", "error", "-y", "-i", source.name,
                             output.name, cwd=cwd)
                return
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                if attempt == 1:
                    raise
                time.sleep(1)
