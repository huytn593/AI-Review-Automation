"""Non-secret runtime settings. Secrets remain in the operator's environment."""
import json
import os
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field


class Settings(BaseModel):
    ollama_model: str = Field(default='', max_length=100, pattern=r'^[\w.:/\-]*$')
    tts: Literal['espeak', 'edge'] = 'espeak'
    voice: str = Field(default='vi', pattern=r'^(vi|vi-VN-HoaiMyNeural|vi-VN-NamMinhNeural)$')
    rate: int = Field(default=0, ge=-40, le=40)
    volume: int = Field(default=0, ge=-50, le=20)
    encoder: Literal['auto', 'cpu'] = 'auto'


def load(root: Path):
    path = root / 'settings.json'
    if path.exists():
        return Settings.model_validate_json(path.read_text(encoding='utf-8'))
    return Settings(ollama_model=os.getenv('OLLAMA_MODEL', ''),
                    tts=os.getenv('FACTORY_TTS', 'espeak'),
                    voice=os.getenv('FACTORY_VOICE', 'vi-VN-HoaiMyNeural' if os.getenv('FACTORY_TTS') == 'edge' else 'vi') if os.getenv('FACTORY_VOICE') != 'mock' else 'vi',
                    encoder=os.getenv('FACTORY_ENCODER', 'auto'))


def save(root: Path, value: Settings):
    # Caller holds the SQLite writer lock: concurrent UI saves cannot race the rename.
    path = root / 'settings.partial.json'
    path.write_text(value.model_dump_json(indent=2), encoding='utf-8')
    path.replace(root / 'settings.json')
