"""
Easy Desinfestações — Video Creation Service
Flask web service that creates vertical short-form videos using FFmpeg.
Accepts image URLs + audio, outputs MP4 1080x1920.
"""

import os
import re
import base64
import tempfile
import subprocess
import logging
import uuid
import math
import urllib.request
from pathlib import Path

import requests
from flask import Flask, request, jsonify, send_file
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from io import BytesIO

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s"
)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────���────────
TARGET_W = 1080
TARGET_H = 1920
FPS      = 30
FADE_DUR = 0.5        # crossfade seconds between images
FONT_SIZE_WATERMARK = 42
FONT_SIZE_TITLE     = 64
WATERMARK_DEFAULT   = "Easy Desinfestações | 965 779 519"
OUTPUT_DIR          = Path(tempfile.gettempdir()) / "video_service"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB max body


def _temp_path(suffix: str) -> Path:
    return OUTPUT_DIR / f"{uuid.uuid4().hex}{suffix}"


def _download_image(url: str) -> Image.Image:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; VideoBot/1.0)"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return Image.open(BytesIO(resp.content)).convert("RGB")


def _resize_to_vertical(img: Image.Image) -> Image.Image:
    orig_w, orig_h = img.size
    target_ratio   = TARGET_W / TARGET_H
    orig_ratio      = orig_w / orig_h

    if orig_ratio > target_ratio:
        bg = img.copy()
        scale_fill = TARGET_H / orig_h
        bg = bg.resize((int(orig_w * scale_fill), TARGET_H), Image.LANCZOS)
        left = (bg.width - TARGET_W) // 2
        bg = bg.crop((left, 0, left + TARGET_W, TARGET_H))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=30))
        darkener = Image.new("RGB", bg.size, (0, 0, 0))
        bg = Image.blend(bg, darkener, alpha=0.35)
        scale_fit = TARGET_W / orig_w
        fg_h = int(orig_h * scale_fit)
        fg = img.resize((TARGET_W, fg_h), Image.LANCZOS)
        top = (TARGET_H - fg_h) // 2
        bg.paste(fg, (0, top))
        return bg

    scale = max(TARGET_W / orig_w, TARGET_H / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    img   = img.resize((new_w, new_h), Image.LANCZOS)
    left  = (new_w - TARGET_W) // 2
    top   = (new_h - TARGET_H) // 2
    return img.crop((left, top, left + TARGET_W, top + TARGET_H))


def _add_text_overlay(img: Image.Image, title: str, watermark: str) -> Image.Image:
    draw = ImageDraw.Draw(img, "RGBA")

    def _load_font(size: int):
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    font_title     = _load_font(FONT_SIZE_TITLE)
    font_watermark = _load_font(FONT_SIZE_WATERMARK)

    def _shadow_text(draw, xy, text, font, fill=(255, 255, 255), shadow_offset=3):
        x, y = xy
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0, 180))
        draw.text((x, y), text, font=font, fill=fill)

    if title:
        words = title.split()
        lines, current = [], ""
        for w in words:
            test = (current + " " + w).strip()
            if len(test) > 22 and current:
                lines.append(current)
                current = w
            else:
                current = test
        if current:
            lines.append(current)

        bar_h = FONT_SIZE_TITLE * len(lines) + 60
        draw.rectangle([(0, 0), (TARGET_W, bar_h)], fill=(0, 0, 0, 160))

        y_pos = 20
        for line in lines:
            bbox  = draw.textbbox((0, 0), line, font=font_title)
            tw    = bbox[2] - bbox[0]
            x_pos = (TARGET_W - tw) // 2
            _shadow_text(draw, (x_pos, y_pos), line, font_title)
            y_pos += FONT_SIZE_TITLE + 8

    wm_bar_h = FONT_SIZE_WATERMARK + 40
    draw.rectangle([(0, TARGET_H - wm_bar_h), (TARGET_W, TARGET_H)], fill=(0, 0, 0, 180))
    bbox_wm = draw.textbbox((0, 0), watermark, font=font_watermark)
    wm_w    = bbox_wm[2] - bbox_wm[0]
    wm_x    = (TARGET_W - wm_w) // 2
    wm_y    = TARGET_H - wm_bar_h + 15
    _shadow_text(draw, (wm_x, wm_y), watermark, font_watermark, shadow_offset=2)

    return img


def _process_audio(audio_data: str):
    audio_path = _temp_path(".mp3")

    if audio_data.startswith("data:audio"):
        _, encoded = audio_data.split(",", 1)
        raw = base64.b64decode(encoded)
        audio_path.write_bytes(raw)
    elif audio_data.startswith("http://") or audio_data.startswith("https://"):
        resp = requests.get(audio_data, timeout=30)
        resp.raise_for_status()
        audio_path.write_bytes(resp.content)
    else:
        raw = base64.b64decode(audio_data)
        audio_path.write_bytes(raw)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True
    )
    try:
        duration = float(probe.stdout.strip())
    except ValueError:
        duration = 60.0

    return audio_path, duration


def _build_video(image_paths, audio_path, duration, output_path):
    n        = len(image_paths)
    img_dur  = duration / n
    fade     = FADE_DUR

    inputs = []
    for p in image_paths:
        inputs += ["-loop", "1", "-t", str(img_dur + fade), "-i", str(p)]
    inputs += ["-i", str(audio_path)]

    fc_parts = []
    for i in range(n):
        fc_parts.append(f"[{i}:v]scale={TARGET_W}:{TARGET_H},setsar=1[v{i}]")

    prev = "v0"
    for i in range(1, n):
        offset = img_dur * i - fade * (i - 1) - fade
        offset = max(offset, 0.1)
        curr   = f"cf{i}"
        fc_parts.append(
            f"[{prev}][v{i}]xfade=transition=fade:duration={fade}:offset={offset:.3f}[{curr}]"
        )
        prev = curr

    fc_parts.append(f"[{prev}]fps={FPS}[vout]")
    filter_complex = "; ".join(fc_parts)
    audio_input_idx = n

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", f"{audio_input_idx}:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Easy Desinfestacoes Video Service"})


@app.route("/create-video", methods=["POST"])
def create_video():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"success": False, "error": "Invalid JSON body"}), 400

    image_urls = data.get("image_urls", [])[:12]
    audio_data = data.get("audio_url", "")
    title      = data.get("title", "")
    watermark  = data.get("watermark_text", WATERMARK_DEFAULT)

    if not image_urls or not audio_data:
        return jsonify({"success": False, "error": "image_urls and audio_url required"}), 400

    tmp_files = []
    try:
        image_paths = []
        for i, url in enumerate(image_urls):
            try:
                img  = _download_image(url)
                img  = _resize_to_vertical(img)
                img  = _add_text_overlay(img, title if i == 0 else "", watermark)
                path = _temp_path(".jpg")
                img.save(path, "JPEG", quality=92)
                image_paths.append(path)
                tmp_files.append(path)
            except Exception as e:
                log.warning("Image %d failed: %s", i, e)

        if not image_paths:
            return jsonify({"success": False, "error": "All image downloads failed"}), 500

        audio_path, audio_duration = _process_audio(audio_data)
        tmp_files.append(audio_path)

        output_path = _temp_path(".mp4")
        tmp_files.append(output_path)
        _build_video(image_paths, audio_path, audio_duration, output_path)

        video_bytes  = output_path.read_bytes()
        video_base64 = base64.b64encode(video_bytes).decode("utf-8")

        return jsonify({
            "success":      True,
            "video_base64": video_base64,
            "duration":     round(audio_duration, 2),
            "size_bytes":   len(video_bytes),
        })

    except Exception as e:
        log.exception("Error creating video")
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        for f in tmp_files:
            try:
                if isinstance(f, Path) and f.exists():
                    f.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
