"""테스트 공용 헬퍼 — 키 헤더, 합성 프레임."""
import io

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

KEY = {"X-API-Key": "changeme-web"}
ADMIN = {"X-Admin-Key": "changeme-admin"}


def make_frame(w=1280, h=720, blur=False, dark=False, texture=True) -> bytes:
    img = Image.new("RGB", (w, h), (170, 170, 175))
    d = ImageDraw.Draw(img)
    d.rectangle([80, 300, w - 80, h - 40], fill=(120, 120, 125))
    arr = np.asarray(img).astype("int16")
    if texture:
        arr = arr + np.random.default_rng(1).integers(-28, 28, size=(h, w, 1), dtype="int16")
    img = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(9))
    if dark:
        img = Image.fromarray((np.asarray(img) * 0.1).astype("uint8"))
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=88); return buf.getvalue()


