"""Record a user-operated demo. Use only where recording is authorized."""
import argparse
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from dotenv import load_dotenv


def main():
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=UUID)
    parser.add_argument("url")
    args = parser.parse_args()
    if urlsplit(args.url).scheme != "https":
        parser.error("HTTPS URL required")
    load_dotenv()
    folder = Path(os.getenv("FACTORY_DATA", "workspace")) / str(args.job)
    folder.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()
        page.goto(args.url)
        input("Đăng nhập thủ công nếu cần. Nhấn Enter khi màn hình đã sạch thông tin nhạy cảm.")
        storage = context.storage_state()
        context.close()
        context = browser.new_context(storage_state=storage, record_video_dir=folder,
                                      record_video_size={"width": 1280, "height": 720},
                                      viewport={"width": 1280, "height": 720})
        page = context.new_page()
        page.goto(args.url)
        input("Thực hiện demo. Nhấn Enter để dừng, hoặc Ctrl+C để hủy.")
        page.screenshot(path=folder / "demo.png")
        video = page.video
        context.close()
        video.path().replace(folder / "recording.webm")
        browser.close()


if __name__ == "__main__":
    main()
