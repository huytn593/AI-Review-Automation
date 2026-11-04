"""Acquire bounded, checksum-verified Poly Haven models for the hero."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import struct
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

API = "https://api.polyhaven.com"
AGENT = "AI-Review-Studio/1.0 (+https://github.com/huytn593/AI-Review-Automation)"
OUTPUT = Path(__file__).resolve().parents[1] / "frontend/public/assets"
MANIFEST = OUTPUT.parents[1] / "src/botanical-manifest.json"
BUDGET = 12_000_000
ROLES = {
    "fern": r"\bfern",
    "flower": r"flower|dandelion",
    "grass": r"grass",
    "rock": r"moss.*(rock|stone)|(rock|stone).*moss",
}


def check_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "api.polyhaven.com", "cdn.polyhaven.com", "dl.polyhaven.org",
    } or parsed.username is not None:
        raise ValueError(f"Unexpected Poly Haven URL host: {parsed.hostname!r}")


class PolyHavenRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read(url, limit):
    check_url(url)
    opener = build_opener(PolyHavenRedirect())
    with opener.open(Request(url, headers={"User-Agent": AGENT}), timeout=15) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("File exceeds size limit")
    return data


def download(entry):
    size = entry["size"]
    data = read(entry["url"], size)
    if len(data) != size or hashlib.md5(data).hexdigest() != entry["md5"].lower():
        raise ValueError("Provider checksum mismatch")
    return data


def package(source):
    files = source.get("include", {})
    if source["size"] + sum(item["size"] for item in files.values()) > 4_000_000:
        raise ValueError("Model exceeds per-asset budget")
    model = json.loads(download(source))
    if model["asset"]["version"] != "2.0" or model.get("extensionsRequired"):
        raise ValueError("Unsupported glTF")
    binary = bytearray()

    def append(data):
        offset = len(binary)
        binary.extend(data)
        binary.extend(b"\0" * (-len(binary) % 4))
        return offset

    offsets = [append(download(files[buffer["uri"]])) for buffer in model["buffers"]]
    views = model.setdefault("bufferViews", [])
    for view in views:
        view["byteOffset"] = view.get("byteOffset", 0) + offsets[view["buffer"]]
        view["buffer"] = 0
    for image in model.get("images", []):
        if "uri" not in image:
            continue
        data = download(files[image.pop("uri")])
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif data.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        else:
            raise ValueError("Unsupported texture format")
        image.update(bufferView=len(views), mimeType=mime)
        views.append(dict(buffer=0, byteOffset=append(data), byteLength=len(data)))
    model["buffers"] = [{"byteLength": len(binary)}]
    header = json.dumps(model, separators=(",", ":")).encode()
    header += b" " * (-len(header) % 4)
    return (struct.pack("<4sII", b"glTF", 2, 28 + len(header) + len(binary))
            + struct.pack("<I4s", len(header), b"JSON") + header
            + struct.pack("<I4s", len(binary), b"BIN\0") + binary)


def main():
    catalog = json.loads(read(API + "/assets", 8_000_000))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = []
    used = 0
    for role, pattern in ROLES.items():
        candidates = [(key, info) for key, info in sorted(catalog.items())
                      if info.get("type") == 2 and re.fullmatch(r"[a-z0-9_]+", key)
                      and re.search(pattern, key + " " + info["name"], re.I)]
        for key, info in candidates[:5]:
            try:
                source = json.loads(read(f"{API}/files/{key}", 2_000_000))["gltf"]["1k"]["gltf"]
                data = package(source)
                if used + len(data) > BUDGET:
                    raise ValueError("Total budget exceeded")
            except (OSError, KeyError, ValueError) as error:
                print(f"{role}/{key}: {error}")
                continue
            checksum = hashlib.sha256(data).hexdigest()
            filename = f"bio-{role}-{checksum[:12]}.glb"
            (OUTPUT / filename).write_bytes(data)
            used += len(data)
            records.append(dict(role=role, name=info["name"], provider="Poly Haven",
                                author=list(info.get("authors", {})), source=f"https://polyhaven.com/a/{key}",
                                license="CC0-1.0", licenseUrl="https://polyhaven.com/license",
                                commercialUse=True, attribution="Powered by Poly Haven",
                                downloadedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                originalFormat="glTF", outputFormat="GLB",
                                originalBytes=source["size"] + sum(item["size"] for item in source.get("include", {}).values()),
                                path=f"/assets/{filename}", bytes=len(data), sha256=checksum))
            break
        else:
            print(f"No compatible {role} model")
    if not records:
        raise SystemExit("No verified assets. Existing manifest retained.")
    temporary = MANIFEST.with_suffix(".tmp")
    temporary.write_text(json.dumps(records, indent=2), encoding="utf-8")
    temporary.replace(MANIFEST)
    print(f"Powered by Poly Haven — {len(records)} models, {used} bytes")


if __name__ == "__main__":
    main()
