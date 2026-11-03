"""Render a standalone three-scene Vietnamese narration sample."""
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .app import Scene
from .media import render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--format", choices=("short", "long"), default="short")
    args = parser.parse_args()
    load_dotenv()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    voice = os.getenv("FACTORY_VOICE", "vi-VN-HoaiMyNeural" if os.getenv("FACTORY_TTS") == "edge" else "vi")
    if voice == "mock":
        parser.error("Smoke test requires a real narration provider")
    lines = [
        ("Kiểm tra giọng đọc", "Đây là bài kiểm tra giọng đọc tiếng Việt. Mỗi cảnh có một đoạn âm thanh riêng. Trình dựng đo thời lượng của đoạn đọc trước khi ghép hình."),
        ("Đồng bộ phụ đề", "Phụ đề của cảnh này bắt đầu ngay khi giọng đọc bắt đầu. Dấu tiếng Việt cần hiển thị rõ ràng, chẳng hạn như chữ thử nghiệm và chữ đồng bộ."),
        ("Kiểm tra đầu ra", "Cuối cùng, chúng ta kiểm tra kích thước video, định dạng hình ảnh, định dạng âm thanh và thời lượng. Hãy nghe lại cả ba cảnh để kiểm tra chất lượng giọng đọc."),
    ]
    render(output, [Scene(caption=caption, narration=text) for caption, text in lines], args.format, voice)
    technical = json.loads((output / "technical.json").read_text(encoding="utf-8"))
    if technical["mostly_silent"]:
        raise SystemExit("FAIL: narration is mostly silent")
    if technical["black_intervals"]:
        raise SystemExit("FAIL: black frames detected")
    print(json.dumps({"file": str(output / "video.mp4"), "voice": voice, **technical}, ensure_ascii=False))


if __name__ == "__main__":
    main()
