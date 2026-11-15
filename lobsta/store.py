"""Where the numbers live. Only this file writes data, and only from numbers
that passed the checks and that the owner confirmed.

SQLite is the working copy (so questions and alerts are fast and work offline).
If Google Sheets is configured, every confirmed invoice is also appended to the
owner's own spreadsheet, which stays theirs if Lobsta disappears.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import date, datetime
from pathlib import Path

SCHEMA = """
create table if not exists invoices(id integer primary key, supplier text, invoice_number text,
  date text, subtotal real, total real, status text, data text, flags text, image text, created text);
create table if not exists lines(invoice_id integer, n integer, description text, item_key text,
  quantity real, unit text, pack_kg real, unit_price real, line_total real,
  unit_cost real, cost_per text, base_qty real, supplier text, date text);
create table if not exists aliases(supplier text, norm text, item_key text, pack_kg real,
  primary key(supplier, norm));
create table if not exists counts(item_key text, date text, qty real, created text);
create index if not exists lines_item on lines(item_key, date);
"""


class Store:
    def __init__(self, path: str | None = None, sheets=None):
        self.path = path or os.environ.get("LOBSTA_DB", "lobsta.db")
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.lock = threading.Lock()
        self.sheets = sheets

    # ---- invoices -------------------------------------------------------
    def save_pending(self, inv: dict, flags: list, image: str | None = None) -> int:
        with self.lock:
            cur = self.db.execute(
                "insert into invoices(supplier,invoice_number,date,subtotal,total,status,data,flags,image,created)"
                " values(?,?,?,?,?,?,?,?,?,?)",
                (inv["supplier"], inv["invoice_number"], inv["date"], inv["subtotal"], inv["total"],
                 "pending", json.dumps(inv, ensure_ascii=False), json.dumps(flags, ensure_ascii=False),
                 image, datetime.now().isoformat(timespec="seconds")))
            self.db.commit()
            return cur.lastrowid

    def get_invoice(self, invoice_id: int) -> dict | None:
        r = self.db.execute("select * from invoices where id=?", (invoice_id,)).fetchone()
        if not r:
            return None
        return {"id": r["id"], "status": r["status"], "inv": json.loads(r["data"]),
                "flags": json.loads(r["flags"] or "[]")}

    def find_duplicate(self, supplier: str, number: str) -> int | None:
        if not number:
            return None
        r = self.db.execute("select id from invoices where supplier=? and invoice_number=? and status='confirmed'",
                            (supplier, number)).fetchone()
        return r["id"] if r else None

    def confirm(self, invoice_id: int, inv: dict | None = None) -> dict:
        """The one place invoice numbers become data."""
        from .matcher import norm_desc
        rec = self.get_invoice(invoice_id)
        if not rec:
            raise KeyError(invoice_id)
        if rec["status"] == "confirmed":
            return rec["inv"]
        inv = inv or rec["inv"]
        with self.lock:
            for ln in inv["lines"]:
                pk = (ln.get("pack") or {}).get("kg")
                self.db.execute(
                    "insert into lines values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (invoice_id, ln["n"], ln["description"], ln.get("item_key"), ln["quantity"], ln["unit"],
                     pk, ln["unit_price"], ln["line_total"], ln.get("unit_cost"), ln.get("cost_per"),
                     ln.get("base_qty"), inv["supplier"], inv["date"]))
                if ln.get("item_key"):
                    self.db.execute("insert or replace into aliases values(?,?,?,?)",
                                    (inv["supplier"], norm_desc(ln["description"]), ln["item_key"], pk))
            self.db.execute("update invoices set status='confirmed', data=? where id=?",
                            (json.dumps(inv, ensure_ascii=False), invoice_id))
            self.db.commit()
        if self.sheets:
            try:
                self.sheets.append_invoice(invoice_id, inv)
            except Exception as e:  # the sheet is a mirror; never lose the confirm
                print("sheets sync failed:", e)
        return inv

    # ---- lookups --------------------------------------------------------
    def get_alias(self, supplier: str, norm: str) -> dict | None:
        r = self.db.execute("select item_key, pack_kg from aliases where supplier=? and norm=?",
                            (supplier, norm)).fetchone()
        return dict(r) if r else None

    def price_history(self, item_key: str, before: str | None = None, limit: int = 12) -> list[dict]:
        q = ("select date, supplier, unit, unit_price, pack_kg, unit_cost, cost_per, base_qty, line_total"
             " from lines where item_key=? and unit_cost is not null")
        args: list = [item_key]
        if before:
            q += " and date < ?"
            args.append(before)
        q += " order by date desc limit ?"
        args.append(limit)
        return [dict(r) for r in self.db.execute(q, args)]

    def spend(self, item_key: str | None, start: str, end: str) -> dict:
        q = "select coalesce(sum(line_total),0) t, coalesce(sum(base_qty),0) q, count(*) n from lines where date>=? and date<=?"
        args: list = [start, end]
        if item_key:
            q += " and item_key=?"
            args.append(item_key)
        r = self.db.execute(q, args).fetchone()
        return {"total": round(r["t"], 2), "qty": round(r["q"], 2), "lines": r["n"]}

    def recent_flags(self, since: str) -> list[dict]:
        """Problems found on invoices confirmed since a date (for the briefing)."""
        out = []
        for r in self.db.execute("select data, flags from invoices where status='confirmed' and date>=? order by date desc",
                                 (since,)):
            inv = json.loads(r["data"])
            for f in json.loads(r["flags"] or "[]"):
                if f.get("code") in ("line_math", "price_jump", "shrink"):
                    out.append({"flag": f, "inv": inv})
        return out

    def spend_by_item(self, start: str, end: str) -> list[dict]:
        rows = self.db.execute(
            "select item_key, sum(line_total) t from lines where date>=? and date<=? and item_key is not null"
            " group by item_key order by t desc", (start, end))
        return [{"item_key": r["item_key"], "total": round(r["t"], 2)} for r in rows]

    # ---- stock ----------------------------------------------------------
    def add_count(self, item_key: str, qty: float, day: str | None = None) -> None:
        with self.lock:
            self.db.execute("insert into counts values(?,?,?,?)",
                            (item_key, day or date.today().isoformat(), qty,
                             datetime.now().isoformat(timespec="seconds")))
            self.db.commit()
        if self.sheets:
            try:
                self.sheets.append_count(item_key, qty, day or date.today().isoformat())
            except Exception as e:
                print("sheets sync failed:", e)

    def counts(self, item_key: str, limit: int = 8) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "select date, qty from counts where item_key=? order by date desc, created desc, rowid desc limit ?",
            (item_key, limit))]

    def received(self, item_key: str, after: str, upto: str) -> float:
        """Received strictly after one count date, up to and including another date."""
        r = self.db.execute("select coalesce(sum(base_qty),0) q from lines where item_key=? and date>? and date<=?",
                            (item_key, after, upto)).fetchone()
        return float(r["q"])

    def reset(self) -> None:
        with self.lock:
            for t in ("invoices", "lines", "aliases", "counts"):
                self.db.execute(f"delete from {t}")
            self.db.commit()


class Sheets:
    """Optional mirror to the owner's Google Sheet (append-only, code-written).

    Setup: create a Google service account, share the sheet with its email,
    then set LOBSTA_SHEET_ID and GOOGLE_APPLICATION_CREDENTIALS. See README.
    """
    LINE_HEAD = ["Invoice", "Date", "Supplier", "Line", "Description", "Item", "Qty", "Unit",
                 "Unit price", "Line total", "Cost per unit", "Per"]

    def __init__(self, sheet_id: str, creds_path: str | None = None):
        import gspread
        gc = gspread.service_account(filename=creds_path or os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
        self.book = gc.open_by_key(sheet_id)

    def _tab(self, name: str, head: list[str]):
        import gspread
        try:
            return self.book.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self.book.add_worksheet(name, rows=1000, cols=len(head))
            ws.append_row(head)
            return ws

    def append_invoice(self, invoice_id: int, inv: dict) -> None:
        rows = [[inv["invoice_number"] or invoice_id, inv["date"], inv["supplier"], ln["n"], ln["description"],
                 ln.get("item_key") or "", ln["quantity"], ln["unit"], ln["unit_price"], ln["line_total"],
                 ln.get("unit_cost") or "", ln.get("cost_per") or ""] for ln in inv["lines"]]
        self._tab("Purchases", self.LINE_HEAD).append_rows(rows, value_input_option="USER_ENTERED")
        self._tab("Invoices", ["Invoice", "Date", "Supplier", "Subtotal", "Total"]).append_row(
            [inv["invoice_number"] or invoice_id, inv["date"], inv["supplier"], inv["subtotal"], inv["total"]],
            value_input_option="USER_ENTERED")

    def append_count(self, item_key: str, qty: float, day: str) -> None:
        self._tab("Counts", ["Date", "Item", "Qty"]).append_row([day, item_key, qty],
                                                                value_input_option="USER_ENTERED")


def open_store(path: str | None = None) -> Store:
    sheets = None
    if os.environ.get("LOBSTA_SHEET_ID"):
        try:
            sheets = Sheets(os.environ["LOBSTA_SHEET_ID"])
        except Exception as e:
            print("Google Sheets not connected, using local store only:", e)
    return Store(path, sheets)
