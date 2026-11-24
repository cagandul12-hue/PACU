"""Uji logika terhadap angka di PDF dashboard asli (24/11/2026)."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import core

seed = json.load(open(os.path.join(os.path.dirname(__file__), "..", "data", "seed.json")))
st = core.normalize_state(seed)
E, R, T = st["employees"], st["records"], st["productTargets"]

def test_product_cards():
    tot = core.product_realization(R)
    exp = dict(livin=12, merchant=7, mcy=0, edc=0, mtr=9, mtb=0, prioritas=1, deposito=0, kopra=0)
    assert {k: int(v) for k, v in tot.items()} == exp
    assert core.fmt_pct(core.product_achievement(12, T["livin"])) == "13,3%"
    assert core.product_status_text(70) == "Need Push"
    assert core.product_status_text(90) == "On Track"
    assert core.product_status_text(100) == "Achieved"

def test_kpi_and_leaderboard():
    k = core.kpis(E, R)
    assert k["records"] == 5 and k["points"] == 33
    assert core.fmt_pct(k["avg"]) == "550%" and k["high"] == 1
    assert k["top"] == "MHD Hendrianto"
    row = core.aggregate_by_employee(E, R)[0]
    assert row["group"] == "R01" and row["target"] == 6 and row["count"] == 5

def test_recap_includes_everyone():
    rows = core.aggregate_by_employee(E, R, include_empty=True)
    assert len(rows) == 17 and rows[0]["employeeName"] == "MHD Hendrianto"

def test_formats():
    assert core.fmt_num(1234.5) == "1.234,5"
    assert core.fmt_num(33) == "33"
    assert core.fmt_num(0.5) == "0,5"

def test_filters():
    assert len(core.filter_records(R, start="2026-11-01")) == 1
    assert len(core.filter_records(R, end="2026-07-31", group="R04")) == 3

def test_exports():
    s = core.build_report_sheets(st, "2026-07-01", "2026-11-24", list(core.EXPORT_DATASETS))
    assert len(s) == 3 and s[1]["rows"][1][1] == "MHD Hendrianto"
    assert core.build_xlsx(s)[:2] == b"PK"
    assert core.build_pdf(s, "t", "s")[:4] == b"%PDF"
    assert len(s[2]["rows"]) == 1 + 8  # header + entri produk non-nol

def test_store_roundtrip():
    d = tempfile.mkdtemp()
    store = core.JsonStore(os.path.join(d, "x.json"), os.path.join(os.path.dirname(__file__), "..", "data", "seed.json"))
    a = store.load(); assert len(a["employees"]) == 17
    a["records"].append({"id": "n", "date": "2026-11-24", "employeeName": "Muhasan", "group": "R01", "livin": 2})
    store.save(a)
    assert len(store.load()["records"]) == 6 and store.load()["lastUpdate"]

def test_period_range():
    from datetime import date
    t = date(2026, 11, 24)
    assert core.period_range("Semua waktu", t) == (None, None)
    assert core.period_range("Hari ini", t) == (t, t)
    assert core.period_range("7 hari terakhir", t) == (date(2026, 11, 18), t)
    assert core.period_range("Bulan ini", t) == (date(2026, 11, 1), t)
    assert core.period_range("Bulan lalu", t) == (date(2026, 10, 1), date(2026, 10, 31))
    assert core.period_range("Bulan lalu", date(2026, 1, 15)) == (date(2025, 12, 1), date(2025, 12, 31))

def test_group_summary_and_progress():
    g = {x["group"]: x for x in core.group_summary(E, R)}
    assert g["R01"]["members"] == 4 and g["R01"]["active"] == 1 and g["R01"]["achieved"] == 1
    assert core.fmt_pct(g["R01"]["avg"]) == "550%" and g["R02"]["avg"] == 0
    p = core.employee_progress(E, R, "MHD Hendrianto")
    assert p["point"] == 33 and core.employee_progress(E, R, "x") is None

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
