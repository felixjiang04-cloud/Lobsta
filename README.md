# Lobsta

Snap a supplier invoice. The AI reads it. Plain code checks every number,
remembers every price, and tells the owner in their own language when they're
being overcharged. Nothing is saved until the owner taps confirm.

Built for small restaurants that will never hire an engineer: each restaurant
is one config file, set up in person.

## Quick start

1. `pip install -r requirements.txt` then `python -m pytest -q` (39 tests, no key or GPU needed).
2. `./run.sh` (Windows PowerShell: `.un.ps1`) and open `http://localhost:8080/`. Tap a sample invoice. This works with no API key or model.
3. For real photos, point the app at a reader: `LOBSTA_READER=local` and `LOBSTA_LOCAL_URL=<your server>/v1` (see Training), or set `ANTHROPIC_API_KEY`.

## Status

- **Run and tested:** the app, checks, alerts, keyword front desk, briefing, price comparison (simulated data), generator, scorer,
  and the fine-tuned reader served from a GPU (photos uploaded through the app are read and checked end to end).
- **Reader result:** on 40 held-out synthetic invoices, the fine-tuned and base Qwen2.5-VL-7B both read 99.8% of numbers
  correctly, and the math check caught the one misread. Fine-tuning mainly improved text fidelity and speed.
- **Known limit:** on real supplier invoices the reader copies the text well, but pack sizes written like `10/1KG` or `50.00#`
  and US-style dates are not parsed reliably yet, which causes false price alerts. Check each finding against its invoice.
- **Written but not run:** the Anthropic API reader, the agent mode of the front desk, Google Sheets sync, and the
  open-model front desk (`train/serve_chat.py`) on a GPU.

## How it works

```
photo ──► READER (vision model) ──► strings exactly as printed
                                         │
              ┌──────────────────────────┘        everything below is plain code
              ▼
   parse      "17,50 $" -> 17.50, "4 x 5 kg" -> 20 kg, lb -> kg
   check      qty x price = line total, lines = subtotal, subtotal + tax = total
   match      line -> owner's item (confirmed once, then a lookup table)
   remember   cost per kg vs the last 4 invoices: price jumps, shrinking packs
              ▼
   owner sees flags in their language ──► taps confirm ──► store writes
                                                            (SQLite + Google Sheet)

owner's text or voice ──► FRONT DESK (agent with tools) ──► tools are plain code:
                          spend, price history, stock, record counts, reorder plan
```

| File | What it does | AI? |
|---|---|---|
| `lobsta/reader.py` | Photo to JSON. Backends: Anthropic API, local OpenAI-compatible server (your fine-tune), mock | yes |
| `lobsta/parse.py` | Number formats, pack sizes, units, cost per kg | no |
| `lobsta/checks.py` | The arithmetic checks | no |
| `lobsta/matcher.py` | Invoice line to owner's item | suggestion only |
| `lobsta/pricing.py` | Price jumps and shrinking packs | no |
| `lobsta/stock.py` | On hand, daily use, reorder plan, order drafts | no |
| `lobsta/frontdesk.py` | Chat and voice counts. Agent with tools, or keyword rules offline | phrasing and tool choice only |
| `lobsta/store.py` | The only code that writes data | no |
| `lobsta/i18n.py` | Every sentence the owner sees, in zh / fr / en | no |
| `configs/*.json` | One restaurant each | |
| `app/` | FastAPI server, phone page `/`, projector page `/sheet` | |
| `gen/` | Synthetic invoice generator with known answers | |
| `train/` | Label, fine-tune, serve, score | |
| `scripts/` | Demo story, seeding, the real-invoice report | |

## The demo

`./run.sh` rebuilds the demo story for today's date: ten weeks of ordinary invoices per restaurant, then three
invoices dated today with things planted in them.

| Sample | What Lobsta should say |
|---|---|
| `sushi_1_fish` | Salmon $21.00/kg after ten weeks at $17.50: +20%, $43.40 extra |
| `sushi_2_dry` | Nori line 10 x 4.50 printed as 54.00 ($9 over). Rice bag 20 kg -> 18 kg at the same price (hidden +11.1%) |
| `sushi_3_clean` | Everything adds up |
| `hotpot_1_meat` | Beef rolls $7.90/lb after weeks at $6.80: +16.2%, $44.00 extra |
| `hotpot_2_veg` | Napa line 2 x 26 printed as 62 ($10 over). Enoki 25 x 200g -> 25 x 150g (hidden +33.3%) |
| `hotpot_3_clean` | Everything adds up |

- `demo/<profile>/*_print.png` are clean versions to **print on paper**, crumple, and photograph live. With an API
  key or your local model, a live photo of the printout goes through the real reader.
- Then ask: `还剩多少`, `该订什么`, `这个月三文鱼花了多少`, or dictate counts: `三文鱼剩八公斤，大米两袋`.
- Put `/sheet` on the projector: confirmed rows appear there within two seconds.
- `POST /api/reset?p=sushi` (or re-run `./run.sh`) puts the demo back to the start.
- The suppliers and prices in the demo are invented. Say so if a judge asks.

Phone on venue wifi can't always reach your laptop. Fallbacks: phone hotspot with the laptop joined to it, or
`cloudflared tunnel --url http://localhost:8080`. The mic needs HTTPS or localhost, so use the tunnel for voice on a phone.

## Options at each step

| Step | Default here | Alternatives | When to switch |
|---|---|---|---|
| Reader | Claude vision via API | Your LoRA fine-tune on the 5090 (`LOBSTA_READER=local`); any OpenAI-compatible server | When your scorer shows the fine-tune is close enough; pitch is cost and privacy |
| Voice | Browser speech recognition | Whisper large-v3 on the 5090 (faster-whisper) behind an endpoint | Kitchen noise or mixed Chinese/French defeats the browser |
| Front desk | Agent with five tools (Haiku) | Keyword rules (`LOBSTA_CHAT=rules`), works offline | Venue wifi dies |
| Item matching | Keywords, then owner confirms once | Add an LLM suggestion for unknown lines | Real invoices have abbreviations keywords miss |
| Store | SQLite + Google Sheets mirror | Sheets only; Postgres | More than a handful of shops |
| Usage ("what went out") | Spoken closing counts | Daily sales report photo x recipes; POS integration | Shops with fixed recipes (sushi) |
| Channel | Mobile web page | SMS/WhatsApp bot (Twilio), iMessage agent (Photon track) | Owners who won't open a link |

## Front desk on the open model, and the price comparison

With `LOBSTA_READER=local` (and no Anthropic key) the front desk uses the same open model as the reader, served by
`train/serve_chat.py`. The model does two things: it picks a route (stock, reorder, spend, price, compare, briefing,
count, chat) and it rewrites the code's answer in a secretary's voice with one suggestion. Code produces the facts,
and `numbers_ok` rejects any reply containing a number that code didn't produce, falling back to the code's wording.
Any failure falls back to keyword rules.

"Am I overpaying?" compares the shop's latest cost per kg with quartiles across other shops (`lobsta/benchmark.py`).
There is no real network yet, so `network/demo_prices.json` is **simulated** and every answer says so.

## Google Sheets (optional, 10 minutes)

1. console.cloud.google.com: create a project, enable the Google Sheets API, create a service account, download its JSON key as `service-account.json`.
2. Create a Google Sheet and share it (Editor) with the service account's email.
3. `export LOBSTA_SHEET_ID=<the long id in the sheet URL>` and `export GOOGLE_APPLICATION_CREDENTIALS=service-account.json`.

Confirmed invoices are appended to `Purchases` and `Invoices` tabs, counts to `Counts`. If the sheet can't be reached
the app keeps working on the local store and prints why.

## Training the reader (the 5090)

One model is trained: the reader. Voice and the front desk use off-the-shelf models.

```bash
# on the GPU box (Linux or WSL2)
pip install -r requirements.txt && pip install unsloth

# 1. synthetic invoices with known answers (FR / EN / ZH, three layouts, phone-photo effects)
python -m gen.generate --n 3000 --out data/synth
python -m gen.generate --n 200  --out data/synth_val --seed 7

# 2. real invoices: label with the API model, keep only math-clean labels, hold 10 out
python -m train.label_real --photos data/real --hold-out 10
#    then open data/real/val/*.json and correct each one by hand against its photo

# 3. build the dataset and smoke-test the trainer (2 minutes)
python -m train.prepare_dataset --src data/synth data/real/labeled --out data/ds
python -m train.finetune --data data/ds --out runs/smoke --max-steps 30 --limit 200

# 4. the real run
python -m train.finetune --data data/ds --out runs/reader --epochs 1

# 5. serve it, and the untouched base model for a before/after
python -m train.serve_local --adapter runs/reader/final --port 8000
python -m train.serve_local --adapter unsloth/Qwen2.5-VL-7B-Instruct-bnb-4bit --port 8001

# 6. score: fine-tune vs base vs API, on real held-out invoices
python -m train.evaluate --data data/real/val --backends anthropic local:http://localhost:8000/v1 local:http://localhost:8001/v1
```

`train.evaluate` prints the table for your slide: share of numbers read exactly, share of invoices fully right,
how many misreads the math check caught, and seconds per invoice. Only quote numbers it actually printed.

Things that go wrong:
- **Torch can't see the 5090.** 50-series cards need a PyTorch build for CUDA 12.8+. `pip install --upgrade torch --index-url https://download.pytorch.org/whl/cu128`.
- **Out of memory.** `--batch 1 --accum 16`, or `--max-side 896`, or the 3B model.
- **Model writes prose instead of JSON.** Train longer, or check `PROMPT` in `lobsta/reader.py` is what both training and serving use (it is, by import).
- **Synthetic invoices don't look like hers.** That's expected: they teach the output format and number copying. The real labeled ones teach her suppliers' layouts, which is why they're repeated 5x.
- **No time.** The app works on the API reader. Put the fine-tune on the roadmap slide and don't claim results you don't have.

## Setting up a new restaurant

Copy `configs/sushi.json`. Set `business`, `owner_language`, `delivery_days`, the suppliers (name exactly as on
their invoices, phone, language), and the items: a key, names, `base_unit`, a few `keywords` as they appear on
invoices, and optionally `par`, `daily_use`, `order_pack`, `count_units` (base units per spoken case or bag).
Open `/?p=<file name>`.

## AI tools used

Built with Claude (claude.ai) and Claude Code for the code, pages and docs. The invoice reader is Qwen2.5-VL-7B,
fine-tuned with LoRA using Unsloth on synthetic invoices from `gen/`.

## Privacy

Real invoices show supplier account numbers and prices. Keep `data/` out of the public repo (it's in
`.gitignore`), and ask before putting a restaurant's name or invoice photo on Devpost.
