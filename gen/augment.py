"""Make a clean render look like a phone photo taken in a kitchen:
tilt, perspective, uneven light, shadow, blur, sensor noise, JPEG."""
from __future__ import annotations

import io
import random

import numpy as np
from PIL import Image, ImageFilter


def _perspective_coeffs(src, dst):
    a = []
    for (x, y), (u, v) in zip(dst, src):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    b = np.array(src, dtype=np.float64).reshape(8)
    return np.linalg.solve(np.array(a, dtype=np.float64), b).tolist()


def phone_photo(img: Image.Image, rng: random.Random, strength: float = 1.0, max_side: int = 1280) -> Image.Image:
    w, h = img.size
    nrng = np.random.default_rng(rng.randint(0, 2**31))
    # paper tint + faint fold lines
    arr = np.asarray(img).astype(np.float32)
    tint = np.array([rng.uniform(0.93, 1.0), rng.uniform(0.93, 1.0), rng.uniform(0.86, 0.98)], dtype=np.float32)
    arr *= tint
    for _ in range(rng.randint(0, 2)):
        if rng.random() < 0.5:
            yy = rng.randint(int(h * 0.2), int(h * 0.8))
            arr[yy - 1:yy + 2] *= rng.uniform(0.86, 0.95)
        else:
            xx = rng.randint(int(w * 0.2), int(w * 0.8))
            arr[:, xx - 1:xx + 2] *= rng.uniform(0.86, 0.95)
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    # place on a table background, then tilt + perspective
    pad = int(0.06 * w)
    bg_col = rng.choice([(60, 55, 50), (120, 110, 100), (40, 40, 45), (150, 140, 120), (90, 70, 55)])
    canvas = Image.new("RGB", (w + 2 * pad, h + 2 * pad), bg_col)
    canvas.paste(img, (pad, pad))
    cw, ch = canvas.size
    j = lambda: rng.uniform(-1, 1) * 0.035 * strength
    dst = [(cw * (0 + abs(j())), ch * (0 + abs(j()))), (cw * (1 - abs(j())), ch * (0 + abs(j()))),
           (cw * (1 - abs(j())), ch * (1 - abs(j()))), (cw * (0 + abs(j())), ch * (1 - abs(j())))]
    src = [(0, 0), (cw, 0), (cw, ch), (0, ch)]
    canvas = canvas.transform((cw, ch), Image.PERSPECTIVE, _perspective_coeffs(src, dst), Image.BICUBIC,
                              fillcolor=bg_col)
    canvas = canvas.rotate(rng.uniform(-4, 4) * strength, resample=Image.BICUBIC, expand=False, fillcolor=bg_col)
    # light: gradient + soft shadow blob
    arr = np.asarray(canvas).astype(np.float32)
    yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
    ang = rng.uniform(0, 2 * np.pi)
    grad = ((xx / cw - 0.5) * np.cos(ang) + (yy / ch - 0.5) * np.sin(ang))
    arr *= (1 + grad * rng.uniform(0.1, 0.45) * strength)[..., None]
    if rng.random() < 0.6 * strength:
        cx, cy = rng.uniform(0, cw), rng.uniform(0, ch)
        r = rng.uniform(0.3, 0.7) * cw
        blob = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r)))
        arr *= (1 - blob * rng.uniform(0.15, 0.4))[..., None]
    arr *= rng.uniform(0.8, 1.08)
    arr += nrng.normal(0, rng.uniform(2, 9) * strength, arr.shape)
    canvas = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    if rng.random() < 0.7:
        canvas = canvas.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.3) * strength))
    scale = max_side / max(canvas.size)
    if scale < 1:
        canvas = canvas.resize((round(cw * scale), round(ch * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    canvas.save(buf, "JPEG", quality=rng.randint(45, 88))
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
