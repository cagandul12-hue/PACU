"""Logika inti PACU – Pantau Akuisisi & Capaian Unit (tanpa dependensi Streamlit, jadi bisa diuji terpisah).

Aturan bisnis:
- Setiap produk punya bobot poin.
- Setiap group (R01..R04) punya target poin per karyawan.
- Achievement rate = base point / target group * 100.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

# ----------------------------------------------------------------------------
# Konstanta
# ----------------------------------------------------------------------------
PRODUCT_POINTS = {
    "livin": 1,
    "merchant": 1,
    "mcy": 0.5,
    "edc": 1,
    "mtr": 1,
    "mtb": 5,
    "prioritas": 5,
    "deposito": 5,
    "kopra": 2,
}
PRODUCT_KEYS = list(PRODUCT_POINTS.keys())

PRODUCT_LABELS = {
    "livin": "Livin’ Mandiri",
    "merchant": "Livin’ Merchant",
    "mcy": "MCY/MTI",
    "edc": "EDC",
    "mtr": "MTR",
    "mtb": "MTB",
    "prioritas": "Prioritas",
    "deposito": "Deposito",
    "kopra": "Kopra",
}

TARGETS = {"R01": 6, "R02": 10, "R03": 15, "R04": 20}
GROUPS = list(TARGETS.keys())

DEFAULT_PRODUCT_TARGETS = {
    "livin": 40,
    "merchant": 12,
    "mcy": 24,
    "edc": 10,
    "mtr": 10,
    "mtb": 4,
    "prioritas": 4,
    "deposito": 4,
    "kopra": 1,
}

EXPORT_DATASETS = {
    "ProductSummary": "Product Target & Realization Summary",
    "Leaderboard": "Leaderboard",
    "DailyInputs": "Detail Input Harian",
}


# ----------------------------------------------------------------------------
# Helper hitung & format
# ----------------------------------------------------------------------------
def uid() -> str:
    return "id-" + uuid.uuid4().hex[:12] + format(int(time.time() * 1000), "x")


def num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def target_of(group: str) -> int:
    return TARGETS.get(group, 0)


def point_of(record: dict) -> float:
    return sum(num(record.get(k)) * w for k, w in PRODUCT_POINTS.items())


def achievement_rate(point: float, group: str) -> float:
    target = target_of(group)
    return (point / target) * 100 if target else 0.0


def fmt_num(n: Any) -> str:
    """Format angka gaya id-ID: 1.234,5 (maks 1 desimal)."""
    n = round(num(n), 1)
    s = f"{n:,.1f}"  # 1,234.5
    s = s.replace(",", "_").replace(".", ",").replace("_", ".")
    if s.endswith(",0"):
        s = s[:-2]
    return s


def fmt_pct(n: Any) -> str:
    return fmt_num(n) + "%"


def status_class(rate: float) -> str:
    if rate >= 100:
        return "green"
    if rate >= 80:
        return "orange"
    return "red"


def status_text(rate: float) -> str:
    if rate >= 100:
        return "High Achiever"
    if rate >= 80:
        return "On Track"
    return "Need Follow-up"


def product_status_text(rate: float) -> str:
    if rate >= 100:
        return "Achieved"
    if rate >= 80:
        return "On Track"
    return "Need Push"


def product_realization(records: list[dict]) -> dict:
    totals = {k: 0.0 for k in PRODUCT_KEYS}
    for r in records:
        for k in PRODUCT_KEYS:
            totals[k] += num(r.get(k))
    return totals


def product_achievement(realization: float, target: float) -> float:
    return (num(realization) / num(target)) * 100 if num(target) > 0 else 0.0


# ----------------------------------------------------------------------------
# Filter & agregasi
# ----------------------------------------------------------------------------
def filter_records(records, start=None, end=None, group=None, employee=None):
    """start/end: string ISO 'YYYY-MM-DD' atau None. group/employee: None = semua."""
    out = []
    for r in records:
        d = r.get("date", "")
        if start and d < start:
            continue
        if end and d > end:
            continue
        if group and r.get("group") != group:
            continue
        if employee and r.get("employeeName") != employee:
            continue
        out.append(r)
    return out


def _blank_row(name: str, group: str) -> dict:
    row = {"employeeName": name, "group": group, "target": target_of(group),
           "count": 0, "point": 0.0, "rate": 0.0}
    row.update({k: 0.0 for k in PRODUCT_KEYS})
    return row


def aggregate_by_employee(employees, records, include_empty=False):
    rows: dict[str, dict] = {}
    for emp in employees:
        rows[emp["name"]] = _blank_row(emp["name"], emp.get("group", ""))
    for r in records:
        name = r.get("employeeName", "")
        if name not in rows:
            rows[name] = _blank_row(name, r.get("group", ""))
        row = rows[name]
        # Sama seperti web asli: group = group pada input terakhir (urutan simpan).
        row["group"] = r.get("group") or row["group"]
        row["target"] = target_of(row["group"])
        for k in PRODUCT_KEYS:
            row[k] += num(r.get(k))
        row["count"] += 1
    result = []
    for row in rows.values():
        row["point"] = point_of(row)
        row["rate"] = achievement_rate(row["point"], row["group"])
        if include_empty or row["count"] > 0:
            result.append(row)
    result.sort(key=lambda x: (-x["rate"], -x["point"], x["employeeName"].lower()))
    return result


PERIOD_PRESETS = ["Semua waktu", "Hari ini", "7 hari terakhir", "Bulan ini", "Bulan lalu", "Kustom"]


def period_range(preset: str, today: date | None = None, custom=(None, None)):
    """Kembalikan (start, end) bertipe date atau (None, None) untuk 'Semua waktu'."""
    today = today or today_local()
    if preset == "Hari ini":
        return today, today
    if preset == "7 hari terakhir":
        return today - timedelta(days=6), today
    if preset == "Bulan ini":
        return today.replace(day=1), today
    if preset == "Bulan lalu":
        last = today.replace(day=1) - timedelta(days=1)
        return last.replace(day=1), last
    if preset == "Kustom":
        return custom
    return None, None


def group_summary(employees, records) -> list[dict]:
    """Ringkasan per group: jumlah karyawan, yang aktif, total poin, rata-rata achievement."""
    rows = aggregate_by_employee(employees, records, include_empty=True)
    out = []
    for g in GROUPS:
        members = [r for r in rows if r["group"] == g]
        active = [r for r in members if r["count"] > 0]
        out.append({
            "group": g,
            "target": target_of(g),
            "members": len(members),
            "active": len(active),
            "points": sum(r["point"] for r in members),
            "avg": sum(r["rate"] for r in active) / len(active) if active else 0.0,
            "achieved": sum(1 for r in active if r["rate"] >= 100),
        })
    return out


def employee_progress(employees, records, name: str) -> dict | None:
    for r in aggregate_by_employee(employees, records, include_empty=True):
        if r["employeeName"] == name:
            return r
    return None


def kpis(employees, records) -> dict:
    rows = aggregate_by_employee(employees, records, False)
    total_point = sum(point_of(r) for r in records)
    avg = sum(r["rate"] for r in rows) / len(rows) if rows else 0.0
    return {
        "records": len(records),
        "points": total_point,
        "avg": avg,
        "high": sum(1 for r in rows if r["rate"] >= 100),
        "top": rows[0]["employeeName"] if rows else "-",
    }


# ----------------------------------------------------------------------------
# Baris export (struktur kolom sama dengan web asli)
# ----------------------------------------------------------------------------
def product_summary_rows(records, product_targets, start, end):
    filtered = filter_records(records, start, end)
    totals = product_realization(filtered)
    rows = [["Product", "Target", "Realization", "AchievementPercent", "PeriodStart", "PeriodEnd"]]
    for k in PRODUCT_KEYS:
        target = num(product_targets.get(k))
        real = totals[k]
        rows.append([PRODUCT_LABELS[k], target, real,
                     round(product_achievement(real, target), 2), start, end])
    return rows


def leaderboard_rows(employees, records, start, end, group=None, employee=None):
    filtered = filter_records(records, start, end, group, employee)
    ranking = aggregate_by_employee(employees, filtered, False)
    rows = [["Rank", "Name", "Group", "Target", "BasePoint", "AchievementPercent",
             "Status", "PeriodStart", "PeriodEnd"]]
    for i, r in enumerate(ranking, 1):
        rows.append([i, r["employeeName"], r["group"], r["target"], round(r["point"], 2),
                     round(r["rate"], 2), status_text(r["rate"]), start, end])
    return rows


def detail_rows(records, start, end):
    rows = [["Date", "Agent", "Merchant", "Product", "InputType", "Value", "Notes",
             "Latitude", "Longitude"]]
    for r in filter_records(records, start, end):
        for k in PRODUCT_KEYS:
            v = num(r.get(k))
            if not v:
                continue
            rows.append([r.get("date", ""), r.get("employeeName", ""), "", PRODUCT_LABELS[k],
                         "Daily Acquisition", v, r.get("remarks", ""), "", ""])
    return rows


def build_report_sheets(state, start, end, datasets, group=None, employee=None):
    employees, records = state["employees"], state["records"]
    builders = {
        "ProductSummary": lambda: product_summary_rows(records, state["productTargets"], start, end),
        "Leaderboard": lambda: leaderboard_rows(employees, records, start, end, group, employee),
        "DailyInputs": lambda: detail_rows(records, start, end),
    }
    return [{"sheetName": d, "title": EXPORT_DATASETS[d], "rows": builders[d]()}
            for d in datasets if d in builders]


def build_xlsx(sheets: list[dict]) -> bytes:
    import xlsxwriter

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    head = wb.add_format({"bold": True, "bg_color": "#0A2F73", "font_color": "#FFFFFF",
                          "border": 1})
    for sh in sheets:
        ws = wb.add_worksheet(sh["sheetName"][:31])
        rows = sh["rows"]
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                ws.write(r, c, val, head if r == 0 else None)
        for c, h in enumerate(rows[0]):
            width = max(len(str(h)), *(len(str(r[c])) for r in rows[1:])) if len(rows) > 1 else len(str(h))
            ws.set_column(c, c, min(max(width + 2, 10), 48))
        ws.freeze_panes(1, 0)
    wb.close()
    return buf.getvalue()


def build_pdf(sheets: list[dict], title: str, subtitle: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1.2 * cm,
                            rightMargin=1.2 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm,
                            title=title)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Paragraph(subtitle, styles["Normal"]),
             Spacer(1, 10)]
    navy = colors.HexColor("#0A2F73")
    for sh in sheets:
        story.append(Paragraph(sh["title"], styles["Heading2"]))
        rows = [[str(c) for c in row] for row in sh["rows"]]
        if len(rows) == 1:
            story.append(Paragraph("Tidak ada data pada periode ini.", styles["Italic"]))
            story.append(Spacer(1, 12))
            continue
        table = Table(rows, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), navy),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D5E6")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FC")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story += [table, Spacer(1, 14)]
    doc.build(story)
    return buf.getvalue()


# ----------------------------------------------------------------------------
# Penyimpanan
# ----------------------------------------------------------------------------
def _as_list(value) -> list:
    """Firebase kadang mengubah array menjadi dict; samakan seperti firebaseArray() di web asli."""
    if isinstance(value, list):
        return [v for v in value if v]
    if isinstance(value, dict):
        return [v for v in value.values() if v]
    return []


def normalize_state(data: dict | None) -> dict:
    data = data or {}
    targets = dict(DEFAULT_PRODUCT_TARGETS)
    raw = data.get("productTargets")
    if isinstance(raw, dict):
        for k in PRODUCT_KEYS:
            if num(raw.get(k)) > 0:
                targets[k] = num(raw[k]) if num(raw[k]) % 1 else int(num(raw[k]))
    employees = [e for e in _as_list(data.get("employees")) if e.get("name")]
    for e in employees:
        e.setdefault("id", uid())
        e.setdefault("group", "R01")
    records = _as_list(data.get("records"))
    for r in records:
        r.setdefault("id", uid())
    return {"employees": employees, "records": records, "productTargets": targets,
            "lastUpdate": data.get("lastUpdate")}


class JsonStore:
    """Simpan ke file JSON lokal (atomic write)."""

    label = "Penyimpanan lokal aktif"

    def __init__(self, path: str, seed_path: str | None = None):
        self.path = path
        self.seed_path = seed_path

    def load(self) -> dict:
        if not os.path.exists(self.path):
            seed = {}
            if self.seed_path and os.path.exists(self.seed_path):
                with open(self.seed_path, encoding="utf-8") as f:
                    seed = json.load(f)
            state = normalize_state(seed)
            if seed:
                self.save(state)
            return state
        with open(self.path, encoding="utf-8") as f:
            return normalize_state(json.load(f))

    def save(self, state: dict) -> None:
        state = dict(state)
        state["lastUpdate"] = int(time.time() * 1000)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path) or ".", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


class FirebaseStore:
    """Firebase Realtime Database lewat REST (opsional, node 'raceDashboard').

    Catatan: butuh Database Rules yang mengizinkan akses (atau `auth` = database secret/token).
    """

    label = "Firebase Realtime Database aktif"

    def __init__(self, db_url: str, auth: str | None = None, node: str = "raceDashboard"):
        self.url = f"{db_url.rstrip('/')}/{node}.json"
        self.auth = auth

    def _params(self):
        return {"auth": self.auth} if self.auth else {}

    def load(self) -> dict:
        import requests

        r = requests.get(self.url, params=self._params(), timeout=15)
        r.raise_for_status()
        return normalize_state(r.json())

    def save(self, state: dict) -> None:
        import requests

        payload = {
            "employees": state["employees"] or None,
            "records": state["records"] or None,
            "productTargets": state["productTargets"],
            "lastUpdate": int(time.time() * 1000),
        }
        r = requests.patch(self.url, params=self._params(), json=payload, timeout=15)
        r.raise_for_status()


class SupabaseStore:
    """Supabase (Postgres) lewat REST. Seluruh data disimpan sebagai satu baris JSON di tabel `pacu_state`."""

    label = "Supabase aktif · sinkron otomatis"
    supports_sync = True

    def __init__(self, url: str, key: str, table: str = "pacu_state", row_id: str = "main",
                 seed_path: str | None = None):
        self.base = f"{url.rstrip('/')}/rest/v1/{table}"
        self.row_id = row_id
        self.seed_path = seed_path
        self.headers = {"apikey": key, "Content-Type": "application/json"}
        if key.startswith("eyJ"):  # kunci format lama (JWT) juga dikirim sebagai Bearer
            self.headers["Authorization"] = f"Bearer {key}"

    def _get(self, select: str):
        import requests

        r = requests.get(self.base, headers=self.headers, timeout=15,
                         params={"id": f"eq.{self.row_id}", "select": select})
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase {r.status_code}: {r.text[:200]}")
        return r.json()

    def load(self) -> dict:
        rows = self._get("data")
        if rows:
            return normalize_state(rows[0].get("data"))
        seed = {}
        if self.seed_path and os.path.exists(self.seed_path):
            with open(self.seed_path, encoding="utf-8") as f:
                seed = json.load(f)
        state = normalize_state(seed)
        self.save(state)  # baris pertama dibuat otomatis
        return state

    def peek(self) -> int:
        """Cek cepat penanda update terakhir (tanpa mengunduh seluruh data)."""
        rows = self._get("lu:data->>lastUpdate")
        try:
            return int(float(rows[0]["lu"])) if rows and rows[0].get("lu") else 0
        except (TypeError, ValueError):
            return 0

    def save(self, state: dict) -> None:
        import requests

        state = dict(state)
        state["lastUpdate"] = int(time.time() * 1000)
        headers = {**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"}
        r = requests.post(self.base, headers=headers, timeout=15,
                          json={"id": self.row_id, "data": state,
                                "updated_at": datetime.now(timezone.utc).isoformat()})
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase {r.status_code}: {r.text[:200]}")


def _tz():
    """Zona waktu tampilan: WIB (server Streamlit Cloud berjalan di UTC)."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("Asia/Jakarta")
    except Exception:  # noqa: BLE001 - data zona waktu tidak tersedia
        return timezone(timedelta(hours=7))


def today_local() -> date:
    return datetime.now(_tz()).date()


def fmt_last_update(ms) -> str:
    if not ms:
        return "Belum ada update"
    return "Last update: " + datetime.fromtimestamp(num(ms) / 1000, _tz()).strftime("%d/%m/%Y, %H.%M.%S")
