"""LoRA fine-tune of a small open vision model to read invoices. Runs on one
RTX 5090 (32 GB). NOT run in the cloud workspace this repo was written in
(no GPU there): expect to fix a version mismatch or two on first launch.

Setup on the 5090 box (Linux or WSL2; Unsloth is painful on bare Windows):
  pip install unsloth                       # pulls torch, transformers, peft, trl, bitsandbytes
  # RTX 50-series needs a PyTorch build for CUDA 12.8 or newer. If torch can't see the
  # GPU:  pip install --upgrade torch --index-url https://download.pytorch.org/whl/cu128

Run:
  python -m gen.generate --n 3000 --out data/synth
  python -m train.prepare_dataset --src data/synth data/mum/labeled --out data/ds
  python -m train.finetune --data data/ds --out runs/reader --epochs 1

Smoke test first (2 minutes, proves the pipeline before you commit an hour):
  python -m train.finetune --data data/ds --out runs/smoke --max-steps 30 --limit 200

The API follows Unsloth's vision fine-tuning guide:
https://unsloth.ai/docs/basics/vision-fine-tuning
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lobsta.reader import PROMPT


def load_rows(path: Path, limit: int | None, max_side: int):
    from PIL import Image
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            r = json.loads(line)
            img = Image.open(r["image"]).convert("RGB")
            if max(img.size) > max_side:          # same-ish size for every image keeps memory flat
                k = max_side / max(img.size)
                img = img.resize((round(img.width * k), round(img.height * k)))
            rows.append({"messages": [
                {"role": "user", "content": [{"type": "image", "image": img}, {"type": "text", "text": PROMPT}]},
                {"role": "assistant", "content": [{"type": "text", "text": r["answer"]}]}]})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data/ds")
    ap.add_argument("--out", default="runs/reader")
    # Known-good default. Other options: unsloth/Qwen2.5-VL-3B-Instruct-bnb-4bit (faster, weaker),
    # or a Qwen3-VL build (check the exact repo name on huggingface.co/unsloth before using it).
    ap.add_argument("--model", default="unsloth/Qwen2.5-VL-7B-Instruct-bnb-4bit")
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--max-steps", type=int, default=-1)
    ap.add_argument("--limit", type=int, default=None, help="use only the first N rows (smoke test)")
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--max-side", type=int, default=1024, help="longest image side in pixels")
    ap.add_argument("--max-len", type=int, default=4096)
    a = ap.parse_args()

    from unsloth import FastVisionModel                      # import unsloth before transformers
    from unsloth.trainer import UnslothVisionDataCollator
    from trl import SFTConfig, SFTTrainer

    model, tokenizer = FastVisionModel.from_pretrained(a.model, load_in_4bit=True,
                                                       use_gradient_checkpointing="unsloth")
    model = FastVisionModel.get_peft_model(
        model,
        finetune_vision_layers=True,      # invoices are a visual task: train the vision side too
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=a.rank, lora_alpha=a.rank, lora_dropout=0, bias="none", random_state=3407)

    train = load_rows(Path(a.data) / "train.jsonl", a.limit, a.max_side)
    print(f"{len(train)} training invoices")
    FastVisionModel.for_training(model)
    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer, train_dataset=train,
        data_collator=UnslothVisionDataCollator(model, tokenizer),
        args=SFTConfig(
            per_device_train_batch_size=a.batch, gradient_accumulation_steps=a.accum,
            warmup_steps=10, num_train_epochs=a.epochs, max_steps=a.max_steps,
            learning_rate=a.lr, lr_scheduler_type="cosine", optim="adamw_8bit", weight_decay=0.01,
            logging_steps=5, save_strategy="steps", save_steps=100, save_total_limit=3,
            seed=3407, output_dir=a.out, report_to="none",
            # required for vision fine-tuning with this collator:
            remove_unused_columns=False, dataset_text_field="", dataset_kwargs={"skip_prepare_dataset": True},
            max_length=a.max_len))
    stats = trainer.train()
    final = Path(a.out) / "final"
    model.save_pretrained(str(final))
    tokenizer.save_pretrained(str(final))
    (final / "lobsta_train.json").write_text(json.dumps(
        {"base_model": a.model, "rows": len(train), "epochs": a.epochs, "max_side": a.max_side,
         "train_runtime_s": stats.metrics.get("train_runtime"), "train_loss": stats.metrics.get("train_loss")}, indent=1))
    print("saved LoRA adapter to", final)
    print("serve it:  python -m train.serve_local --adapter", final)


if __name__ == "__main__":
    main()
