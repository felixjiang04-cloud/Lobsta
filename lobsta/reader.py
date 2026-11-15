"""The only place a model looks at an invoice. It transcribes; it never computes.

Backends (set LOBSTA_READER):
  anthropic  - Claude vision via the Anthropic API (default when ANTHROPIC_API_KEY is set)
  local      - any OpenAI-compatible server: your fine-tuned model on the 5090
               (train/serve_local.py, vLLM, Ollama, LM Studio) or OpenAI itself
  mock       - reads the answer file next to a generated invoice (offline demos, tests)
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from pathlib import Path

# The same instruction is used for the API model, for labeling, and as the
# training prompt of the fine-tuned model, so they are directly comparable.
PROMPT = """You are reading a photo of a supplier invoice for a restaurant.
Copy what is printed. Do not calculate, correct, translate or guess.
Return only JSON with this shape:
{"supplier": "", "invoice_number": "", "date": "YYYY-MM-DD", "language": "fr|en|zh", "currency": "CAD",
 "lines": [{"code": "", "description": "", "quantity": "", "unit": "", "pack": "", "unit_price": "", "line_total": ""}],
 "subtotal": "", "taxes": [{"name": "", "amount": ""}], "total": ""}
Rules:
- One entry in "lines" per product line, in the order printed. Skip headers, deposits shown as notes, and blank rows.
- Numbers are strings exactly as printed, keeping the decimal mark ("17,50" stays "17,50").
- "unit" is the unit the price is per (kg, lb, caisse, case, 箱, un, ...). "pack" is the pack size if printed
  (for example "25 lb" or "4 x 5 kg"), otherwise "".
- "description" is the product text as printed, in its original language.
- If something is unreadable use "" for it. Never invent a value."""


def extract_json(text: str) -> dict:
    """Models sometimes wrap JSON in prose or code fences. Take the outermost object."""
    text = re.sub(r"```(?:json)?", "", text or "")
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON in reader output")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            esc = (ch == "\\") and not esc
            if ch == '"' and not esc:
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unterminated JSON in reader output")


MAX_SIDE = 1600


def _b64(path: str) -> tuple[str, str]:
    """Phone photos are 4-12 MB and stored sideways with an EXIF rotation flag. Upright them and
    shrink to MAX_SIDE so the model sees the page the right way up and the upload stays small."""
    try:
        import io
        from PIL import Image, ImageOps
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            if max(im.size) > MAX_SIDE:
                k = MAX_SIDE / max(im.size)
                im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=90)
        return "image/jpeg", base64.standard_b64encode(buf.getvalue()).decode()
    except Exception:
        mime = mimetypes.guess_type(path)[0] or "image/jpeg"
        return mime, base64.standard_b64encode(Path(path).read_bytes()).decode()


def read_anthropic(path: str, model: str | None = None) -> dict:
    import anthropic
    mime, data = _b64(path)
    msg = anthropic.Anthropic().messages.create(
        model=model or os.environ.get("LOBSTA_API_MODEL", "claude-sonnet-5-5"),
        max_tokens=4096,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}},
            {"type": "text", "text": PROMPT}]}])
    return extract_json("".join(b.text for b in msg.content if b.type == "text"))


def read_local(path: str, model: str | None = None, base_url: str | None = None) -> dict:
    """OpenAI-compatible chat/completions with an image. Uses httpx, no SDK needed."""
    import httpx
    mime, data = _b64(path)
    base = (base_url or os.environ.get("LOBSTA_LOCAL_URL", "http://localhost:8000/v1")).rstrip("/")
    r = httpx.post(f"{base}/chat/completions", timeout=180,
                   headers={"Authorization": f"Bearer {os.environ.get('LOBSTA_LOCAL_KEY', 'none')}"},
                   json={"model": model or os.environ.get("LOBSTA_LOCAL_MODEL", "lobsta-reader"),
                         "temperature": 0, "max_tokens": 4096,
                         "messages": [{"role": "user", "content": [
                             {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                             {"type": "text", "text": PROMPT}]}]})
    if r.status_code >= 500 or "json" not in r.headers.get("content-type", ""):
        raise RuntimeError(f"the model server at {base} isn't answering (HTTP {r.status_code}). "
                           "Is the RunPod pod running and the server started?")
    r.raise_for_status()
    return extract_json(r.json()["choices"][0]["message"]["content"])


def read_mock(path: str) -> dict:
    side = Path(path).with_suffix(".json")
    if not side.exists():
        raise FileNotFoundError(f"mock reader needs {side.name} next to the image (generated invoices have it)")
    return json.loads(side.read_text(encoding="utf-8"))


def backend() -> str:
    b = os.environ.get("LOBSTA_READER")
    if b:
        return b
    return "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "mock"


def read_invoice(path: str, which: str | None = None) -> dict:
    which = which or backend()
    if which == "anthropic":
        return read_anthropic(path)
    if which == "local":
        return read_local(path)
    if which == "mock":
        return read_mock(path)
    raise ValueError(f"unknown reader backend {which!r}")
