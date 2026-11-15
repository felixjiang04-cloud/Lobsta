"""Serve the fine-tuned reader on the 5090 behind an OpenAI-compatible endpoint,
so the app (and train.evaluate) can use it with LOBSTA_READER=local.

  python -m train.serve_local --adapter runs/reader/final --port 8000
  # compare against the untouched base model on another port:
  python -m train.serve_local --adapter unsloth/Qwen2.5-VL-7B-Instruct-bnb-4bit --port 8001

On the laptop running the app:
  export LOBSTA_READER=local LOBSTA_LOCAL_URL=http://<5090 address>:8000/v1
Reaching a home PC from the venue: Tailscale (easiest) or `cloudflared tunnel --url http://localhost:8000`.
Not run in the cloud workspace (no GPU there).
"""
from __future__ import annotations

import argparse
import base64
import io
import time


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--adapter", required=True, help="LoRA folder from finetune.py, or a base model id")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--max-side", type=int, default=1024)
    a = ap.parse_args()

    import torch
    import uvicorn
    from fastapi import FastAPI
    from PIL import Image
    from unsloth import FastVisionModel

    model, tokenizer = FastVisionModel.from_pretrained(a.adapter, load_in_4bit=True)
    FastVisionModel.for_inference(model)
    app = FastAPI()

    @app.get("/v1/models")
    def models():
        return {"data": [{"id": "lobsta-reader"}]}

    @app.post("/v1/chat/completions")
    def chat(body: dict):
        """Invoice reading (one image + the reader prompt) and plain text chat (the front desk)."""
        img, msgs = None, []
        for m in body["messages"]:
            if isinstance(m["content"], str):
                msgs.append({"role": m["role"], "content": [{"type": "text", "text": m["content"]}]})
                continue
            parts = []
            for part in m["content"]:
                if part["type"] == "image_url":
                    b64 = part["image_url"]["url"].split(",", 1)[1]
                    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
                    if max(img.size) > a.max_side:
                        k = a.max_side / max(img.size)
                        img = img.resize((round(img.width * k), round(img.height * k)))
                    parts.append({"type": "image"})
                elif part["type"] == "text":
                    parts.append({"type": "text", "text": part["text"]})
            msgs.append({"role": m["role"], "content": parts})
        prompt = tokenizer.apply_chat_template(msgs, add_generation_prompt=True)
        if img is not None:
            inputs = tokenizer(img, prompt, add_special_tokens=False, return_tensors="pt").to("cuda")
        else:
            inputs = tokenizer(text=prompt, add_special_tokens=False, return_tensors="pt").to("cuda")
        gen = dict(max_new_tokens=int(body.get("max_tokens", 2048)), do_sample=False, use_cache=True)
        t0 = time.time()
        with torch.inference_mode():
            # "adapter": false asks for the untouched base model (the invoice LoRA is not meant for chat)
            if body.get("adapter") is False and hasattr(model, "disable_adapter"):
                with model.disable_adapter():
                    out = model.generate(**inputs, **gen)
            else:
                out = model.generate(**inputs, **gen)
        answer = tokenizer.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
        return {"choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                "usage": {"completion_tokens": int(out.shape[1] - inputs["input_ids"].shape[1])},
                "seconds": round(time.time() - t0, 2)}

    uvicorn.run(app, host=a.host, port=a.port)


if __name__ == "__main__":
    main()
