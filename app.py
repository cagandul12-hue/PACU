"""PACU – Pantau Akuisisi & Capaian Unit (Streamlit)

Dashboard akuisisi harian: input, target produk, leaderboard, rekap karyawan,
detail input, dan export XLSX/PDF.
"""
from __future__ import annotations

import base64
import html as _html
import inspect
import json
import os
from datetime import date

import streamlit as st

import core
from core import (GROUPS, PRODUCT_KEYS, PRODUCT_LABELS, PRODUCT_POINTS, TARGETS,
                  fmt_num, fmt_pct)

APP_NAME = "PACU"
APP_TAGLINE = "Pantau Akuisisi & Capaian Unit"
FILE_PREFIX = "pacu"

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets")

st.set_page_config(page_title=f"{APP_NAME} · {APP_TAGLINE}",
                   page_icon=os.path.join(ASSETS, "icon.png"), layout="wide")


# ----------------------------------------------------------------------------
# Penyimpanan (JSON lokal, atau Firebase bila dikonfigurasi di secrets)
# ----------------------------------------------------------------------------
@st.cache_resource
def get_store():
    db_url = auth = None
    node = "raceDashboard"  # nama node default dipertahankan agar data lama tetap terbaca
    try:
        db_url = st.secrets.get("firebase_db_url")  # type: ignore[attr-defined]
        auth = st.secrets.get("firebase_auth")  # type: ignore[attr-defined]
        node = st.secrets.get("firebase_node", node)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - secrets tidak ada
        pass
    if db_url:
        return core.FirebaseStore(db_url, auth or None, node)
    path = os.environ.get("PACU_DATA_FILE", os.path.join(BASE, "data", "pacu_data.json"))
    return core.JsonStore(path, os.path.join(BASE, "data", "seed.json"))


store = get_store()


def load_state() -> dict:
    return store.load()


def commit(state: dict) -> None:
    store.save(state)


def flash(msg: str) -> None:
    st.session_state["_flash"] = msg


# ----------------------------------------------------------------------------
# Util HTML
# ----------------------------------------------------------------------------
def esc(x) -> str:
    return _html.escape(str(x if x is not None else ""))


def flat(s: str) -> str:
    """Rapatkan HTML ke satu baris agar tidak dibaca sebagai code block Markdown."""
    return " ".join(line.strip() for line in s.splitlines() if line.strip())


def md(s: str) -> None:
    st.markdown(flat(s), unsafe_allow_html=True)


def spacer(px: int = 28) -> str:
    return f"<div style='height:{px}px'></div>"


@st.cache_data
def logo_b64() -> str:
    with open(os.path.join(ASSETS, "logo.png"), "rb") as f:
        return base64.b64encode(f.read()).decode()


def bar(rate: float) -> str:
    return f'<div class="bar"><span style="width:{min(max(rate, 0), 100):.1f}%"></span></div>'


def status_pill(rate: float, text: str | None = None) -> str:
    return f'<span class="status {core.status_class(rate)}">{esc(text or fmt_pct(rate))}</span>'


def table(headers: list[str], rows: list[list], empty: str, min_width: int = 860) -> None:
    if not rows:
        md(f'<div class="empty">{empty}</div>')
        return
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    md(f'<div class="table-wrap"><table style="min-width:{min_width}px"><thead><tr>{th}</tr></thead>'
       f"<tbody>{body}</tbody></table></div>")


def section(title: str, sub: str = "") -> None:
    subtitle = f'<span>{esc(sub)}</span>' if sub else ""
    md(f'<div class="sec-head"><h3>{esc(title)}</h3>{subtitle}</div>')


def iso(d) -> str | None:
    return d.isoformat() if d else None


def show_dataframe(df, **kw):
    """st.dataframe selebar kontainer, kompatibel lintas versi Streamlit."""
    try:
        stretch = "stretch" in str(inspect.signature(st.dataframe))
    except (TypeError, ValueError):
        stretch = False
    if stretch:
        return st.dataframe(df, width="stretch", **kw)
    return st.dataframe(df, use_container_width=True, **kw)


# ----------------------------------------------------------------------------
# CSS
# ----------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
:root{--navy:#062b63;--blue:#0055b8;--blue2:#0d67d8;--light-blue:#eaf3ff;--yellow:#f9b400;--green:#14a44d;
--orange:#f59e0b;--red:#d93025;--gray:#6b7280;--soft:#f5f7fb;--line:#dbe3ef;}
html,body,[class*="css"],.stApp{font-family:"Inter","Segoe UI",Roboto,Arial,sans-serif;}
.stApp{background:radial-gradient(circle at top right,rgba(0,85,184,.08),transparent 30%),
linear-gradient(180deg,#f5f8fc 0%,#ffffff 52%,#f6f9ff 100%);}
.block-container{max-width:1500px;padding-top:1.2rem;padding-bottom:3rem;}
header[data-testid="stHeader"]{background:transparent;}
#MainMenu,footer{visibility:hidden;}

/* header */
.topbar{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:10px;flex-wrap:wrap}
.topbar img{height:74px;width:auto}
.last-update{display:flex;align-items:center;gap:10px;color:var(--gray);font-size:13px;font-weight:600;
background:rgba(255,255,255,.85);border:1px solid var(--line);padding:9px 14px;border-radius:999px;
box-shadow:0 6px 18px rgba(6,43,99,.06);white-space:nowrap}
.pulse{width:9px;height:9px;border-radius:50%;background:var(--green);box-shadow:0 0 0 5px rgba(20,164,77,.14)}
.pulse.off{background:var(--red);box-shadow:0 0 0 5px rgba(217,48,37,.14)}

/* tabs */
.stTabs [data-baseweb="tab-list"]{gap:8px;flex-wrap:wrap;border-bottom:none;margin-bottom:6px}
.stTabs [data-baseweb="tab"]{background:#fff;border:1px solid var(--line);border-radius:999px;padding:8px 18px;
height:auto;font-weight:800;box-shadow:0 4px 12px rgba(6,43,99,.05)}
.stTabs [data-baseweb="tab"] p{color:var(--navy);font-weight:800;font-size:14px;margin:0}
.stTabs [aria-selected="true"]{background:linear-gradient(135deg,#0a2f73,#0f57b7);border-color:transparent;
box-shadow:0 10px 22px rgba(15,87,183,.28)}
.stTabs [aria-selected="true"] p{color:#fff}
.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{display:none}

/* section heading */
.sec-head{display:flex;align-items:baseline;gap:12px;margin:18px 0 10px;flex-wrap:wrap}
.sec-head h3{margin:0;color:var(--navy);font-size:19px;font-weight:900;letter-spacing:-.3px}
.sec-head span{color:var(--gray);font-size:13px}
.panel{background:#fff;border:1px solid #dfe7f2;border-radius:20px;box-shadow:0 10px 26px rgba(15,23,42,.06);padding:18px}
.note{color:var(--gray);font-size:13px;line-height:1.55;background:#f3f5fa;border:1px solid #e3e8f1;
border-radius:14px;padding:12px 15px;margin:6px 0 12px}

/* KPI */
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin:12px 0 6px}
.kpi{background:#fff;border:1px solid #dfe7f2;box-shadow:0 10px 24px rgba(15,23,42,.06);border-radius:20px;
padding:16px 18px;position:relative;overflow:hidden;transition:transform .15s}
.kpi:hover{transform:translateY(-2px)}
.kpi:after{content:"";position:absolute;right:-26px;bottom:-26px;width:76px;height:76px;border-radius:26px;
background:rgba(0,85,184,.08);transform:rotate(20deg)}
.kpi .l{color:var(--gray);font-size:11.5px;font-weight:800;text-transform:uppercase;letter-spacing:.6px}
.kpi .v{color:var(--navy);font-weight:900;font-size:27px;margin-top:6px;letter-spacing:-.5px;word-break:break-word}
.kpi .h{color:var(--gray);font-size:12px;margin-top:4px}
.kpi .acc{width:34px;height:4px;background:var(--yellow);border-radius:8px;margin-top:8px}

/* group & product cards */
.cards4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.gcard{background:#fff;border:1px solid #dfe7f2;border-radius:20px;padding:16px 18px;box-shadow:0 10px 24px rgba(15,23,42,.05)}
.gcard .top{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.gcard .big{font-size:28px;font-weight:900;color:var(--navy);letter-spacing:-.5px}
.gcard .sub{color:var(--gray);font-size:12px;margin:2px 0 10px;line-height:1.5}
.cards3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.ptc{background:#fff;border:1px solid #dfe7f2;border-top:5px solid var(--line);border-radius:20px;padding:16px 18px;
box-shadow:0 10px 24px rgba(15,23,42,.06);position:relative;overflow:hidden;transition:transform .15s}
.ptc:hover{transform:translateY(-2px)}
.ptc.green{border-top-color:var(--green)}.ptc.orange{border-top-color:var(--orange)}.ptc.red{border-top-color:var(--red)}
.ptc .row{display:flex;justify-content:space-between;align-items:center;gap:8px}
.ptc .label{color:var(--navy);font-weight:900;font-size:14px;letter-spacing:.3px}
.chip{background:var(--light-blue);color:var(--navy);border:1px solid #cfe4ff;border-radius:999px;padding:4px 10px;font-size:12px;font-weight:800;white-space:nowrap}
.ptc .main{color:var(--navy);font-weight:900;font-size:32px;margin:6px 0 2px;letter-spacing:-.6px}
.ptc .main span{font-size:16px;color:var(--gray);font-weight:700}
.ptc .hint{color:var(--gray);font-size:12px;margin-bottom:10px}
.meta{display:flex;gap:8px;margin:0 0 10px;flex-wrap:wrap}

/* podium */
.podium{display:grid;grid-template-columns:1fr 1.15fr 1fr;gap:14px;align-items:end;margin:6px 0 16px}
.pod{background:#fff;border:1px solid #dfe7f2;border-radius:22px;padding:16px 16px 18px;text-align:center;
box-shadow:0 10px 24px rgba(15,23,42,.06)}
.pod.p1{background:linear-gradient(180deg,#fff8e1,#fff);border-color:#ffe08a;padding-top:22px;padding-bottom:24px}
.pod .medal{font-size:30px;line-height:1}
.pod .name{font-weight:900;color:var(--navy);font-size:16px;margin:8px 0 2px;word-break:break-word}
.pod .rate{font-size:26px;font-weight:900;letter-spacing:-.5px}
.pod .pts{color:var(--gray);font-size:12px;margin-top:2px}

/* tabel */
.table-wrap{overflow:auto;border-radius:16px;border:1px solid var(--line);margin:6px 0 12px;background:#fff}
table{width:100%;border-collapse:collapse;background:#fff}
th{background:#f5f8fc;color:#12356c;text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.5px;
padding:12px 14px;border-bottom:1px solid #dfe7f2;white-space:nowrap;font-weight:800;position:sticky;top:0}
td{padding:12px 14px;border-bottom:1px solid #edf2f7;font-size:13px;vertical-align:middle;line-height:1.45;color:#0f172a}
tbody tr:hover td{background:#f8fbff}
tr:last-child td{border-bottom:none}
.small{color:var(--gray);font-size:12px}
.rank{display:inline-flex;align-items:center;justify-content:center;min-width:28px;height:28px;border-radius:999px;
font-weight:900;color:#fff;background:var(--navy)}
.rank.r1{background:#f4b400;color:#111827}.rank.r2{background:#9ca3af}.rank.r3{background:#b87333}
.gp{display:inline-flex;padding:5px 10px;border-radius:999px;font-weight:800;font-size:12px;background:var(--light-blue);
color:var(--navy);border:1px solid #cfe4ff;white-space:nowrap}
.status{display:inline-flex;align-items:center;padding:5px 10px;border-radius:999px;font-weight:800;font-size:12px;white-space:nowrap}
.status.green{background:#e9f8ef;color:var(--green)}
.status.orange{background:#fff7e6;color:#b76200}
.status.red{background:#fff1f0;color:var(--red)}
.bar{height:9px;width:100%;min-width:80px;background:#edf1f7;border-radius:999px;overflow:hidden}
.bar>span{display:block;height:100%;background:linear-gradient(90deg,var(--blue),var(--green));border-radius:999px}
.empty{text-align:center;color:var(--gray);padding:26px;background:var(--soft);border-radius:16px;border:1px dashed var(--line);line-height:1.6}
.preview{background:linear-gradient(135deg,#eaf3ff,#f6faff);border:1px solid #cfe4ff;border-radius:14px;padding:12px 16px;color:var(--navy);font-weight:800}
.ctx .name{color:var(--navy);font-weight:900;font-size:17px}
.ctx .big{font-size:30px;font-weight:900;color:var(--navy);letter-spacing:-.5px;margin:6px 0}

/* widget */
label,.stWidgetLabel p{color:var(--navy)!important;font-weight:700!important;font-size:12.5px!important}
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{border-radius:12px;font-weight:800;padding:.5rem 1rem}
.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{
background:linear-gradient(135deg,#062b63,#0055b8);border:none;color:#fff;box-shadow:0 8px 18px rgba(0,85,184,.22)}
div[data-testid="stExpander"]{background:#fff;border:1px solid #dfe7f2!important;border-radius:16px}

@media (max-width:1000px){
 .kpis{grid-template-columns:repeat(2,1fr)}.cards4{grid-template-columns:repeat(2,1fr)}
 .cards3{grid-template-columns:1fr}.podium{grid-template-columns:1fr}
}
@media (max-width:640px){
 .topbar img{height:56px}.block-container{padding-left:.8rem;padding-right:.8rem}
 .cards4{grid-template-columns:1fr}.kpi .v{font-size:22px}
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Callback & dialog
# ----------------------------------------------------------------------------
def _reset_numbers() -> None:
    ss = st.session_state
    for k in PRODUCT_KEYS:
        ss[f"f_{k}"] = 0
    ss["f_remarks"] = ""


def _init_form(state: dict) -> None:
    ss = st.session_state
    ss["f_date"] = date.today()
    _reset_numbers()
    if state["employees"]:
        ss["f_emp"] = state["employees"][0]["id"]
        ss["f_group"] = state["employees"][0]["group"]


def cb_employee_changed() -> None:
    state = load_state()
    emp = next((e for e in state["employees"] if e["id"] == st.session_state.get("f_emp")), None)
    if emp:
        st.session_state["f_group"] = emp["group"]


def cb_save_record() -> None:
    ss = st.session_state
    state = load_state()
    emp = next((e for e in state["employees"] if e["id"] == ss.get("f_emp")), None)
    if not emp or not ss.get("f_date"):
        flash("⚠️ Pilih karyawan dan tanggal terlebih dahulu.")
        return
    rec = {"id": core.uid(), "date": ss["f_date"].isoformat(), "employeeName": emp["name"],
           "group": ss["f_group"], "remarks": (ss.get("f_remarks") or "").strip()}
    for k in PRODUCT_KEYS:
        rec[k] = int(ss.get(f"f_{k}") or 0)
    if not any(rec[k] for k in PRODUCT_KEYS):
        flash("⚠️ Isi minimal satu produk (jumlah lebih dari 0).")
        return
    state["records"].append(rec)
    commit(state)
    _reset_numbers()  # tanggal & karyawan dipertahankan agar input berikutnya cepat
    flash(f"✅ Tersimpan: {emp['name']} · {fmt_num(core.point_of(rec))} poin")


def cb_update_target(key: str) -> None:
    val = st.session_state.get(f"tgt_{key}")
    state = load_state()
    if not val or val <= 0:
        st.session_state[f"tgt_{key}"] = int(state["productTargets"][key])
        flash("⚠️ Target cabang tidak boleh 0 atau kosong (minimal 1).")
        return
    state["productTargets"][key] = int(val)
    commit(state)
    flash(f"✅ Target {PRODUCT_LABELS[key]} diperbarui menjadi {int(val)}.")


def cb_focus_employee() -> None:
    st.session_state["d_emp"] = st.session_state.get("e_pick")
    flash("🔎 Filter Karyawan di tab Detail Input sudah diarahkan ke karyawan ini.")


def cb_import() -> None:
    f = st.session_state.get("import_file")
    if f is None:
        flash("⚠️ Pilih file JSON terlebih dahulu.")
        return
    try:
        data = json.loads(f.getvalue().decode("utf-8"))
        if isinstance(data.get("raceDashboard"), dict):
            data = data["raceDashboard"]  # ekspor Firebase penuh dari dashboard lama
        new = core.normalize_state(data)
    except Exception as exc:  # noqa: BLE001
        flash(f"⚠️ File tidak valid: {exc}")
        return
    commit(new)
    _init_form(new)
    flash(f"✅ Data diimpor: {len(new['employees'])} karyawan, {len(new['records'])} input.")


@st.dialog("Edit Input Harian", width="large")
def edit_dialog(rid: str) -> None:
    state = load_state()
    rec = next((r for r in state["records"] if r["id"] == rid), None)
    if not rec:
        st.warning("Data tidak ditemukan.")
        return
    names = [e["name"] for e in state["employees"]]
    if rec["employeeName"] not in names:
        names.append(rec["employeeName"])
    c1, c2, c3 = st.columns([1, 1.6, 1])
    d = c1.date_input("Tanggal", value=date.fromisoformat(rec["date"]), format="DD/MM/YYYY", key=f"ed_d_{rid}")
    name = c2.selectbox("Karyawan", names, index=names.index(rec["employeeName"]), key=f"ed_n_{rid}")
    group = c3.selectbox("Group Target", GROUPS,
                         index=GROUPS.index(rec["group"]) if rec.get("group") in GROUPS else 0,
                         format_func=lambda g: f"{g} · Target {TARGETS[g]}", key=f"ed_g_{rid}")
    vals = {}
    cols = st.columns(5)
    for i, k in enumerate(PRODUCT_KEYS):
        vals[k] = cols[i % 5].number_input(PRODUCT_LABELS[k], min_value=0, step=1,
                                           value=int(core.num(rec.get(k))), key=f"ed_{k}_{rid}")
    remarks = st.text_input("Remark / Status", value=rec.get("remarks", ""), key=f"ed_r_{rid}")
    new_rec = {"id": rid, "date": d.isoformat(), "employeeName": name, "group": group,
               "remarks": remarks.strip(), **{k: int(v) for k, v in vals.items()}}
    p = core.point_of(new_rec)
    md(f'<div class="preview">{fmt_num(p)} base point · {fmt_pct(core.achievement_rate(p, group))}</div>')
    b1, b2, _ = st.columns([1, 1, 2])
    if b1.button("Simpan Perubahan", type="primary", key=f"ed_save_{rid}"):
        state["records"] = [new_rec if r["id"] == rid else r for r in state["records"]]
        commit(state)
        flash("✅ Input berhasil diperbarui.")
        st.rerun()
    if b2.button("Batal", key=f"ed_cancel_{rid}"):
        st.rerun()


@st.dialog("Hapus Input Harian")
def delete_record_dialog(rid: str) -> None:
    state = load_state()
    rec = next((r for r in state["records"] if r["id"] == rid), None)
    if not rec:
        st.warning("Data tidak ditemukan.")
        return
    st.write(f"Hapus input **{rec['employeeName']}** tanggal **{rec['date']}** "
             f"({fmt_num(core.point_of(rec))} poin)? Tindakan ini tidak dapat dibatalkan.")
    b1, b2 = st.columns(2)
    if b1.button("Ya, hapus", type="primary", key=f"del_ok_{rid}"):
        state["records"] = [r for r in state["records"] if r["id"] != rid]
        commit(state)
        flash("🗑️ Input berhasil dihapus.")
        st.rerun()
    if b2.button("Batal", key=f"del_no_{rid}"):
        st.rerun()


@st.dialog("Hapus Employee")
def delete_employee_dialog(name: str) -> None:
    state = load_state()
    n_rec = sum(1 for r in state["records"] if r["employeeName"] == name)
    st.write(f"Hapus **{name}** beserta **{n_rec} input harian** miliknya? "
             "Nama juga akan hilang dari rekap dan leaderboard. Tindakan ini tidak dapat dibatalkan.")
    b1, b2 = st.columns(2)
    if b1.button("Ya, hapus permanen", type="primary", key="demp_ok"):
        state["employees"] = [e for e in state["employees"] if e["name"] != name]
        state["records"] = [r for r in state["records"] if r["employeeName"] != name]
        commit(state)
        _init_form(state)
        flash(f"🗑️ {name} dan {n_rec} input hariannya dihapus.")
        st.rerun()
    if b2.button("Batal", key="demp_no"):
        st.rerun()


# ----------------------------------------------------------------------------
# Muat data
# ----------------------------------------------------------------------------
try:
    state = load_state()
    store_error = None
except Exception as exc:  # noqa: BLE001
    state = core.normalize_state({})
    store_error = str(exc)

employees, all_records, targets = state["employees"], state["records"], state["productTargets"]
emp_by_id = {e["id"]: e for e in employees}
emp_names = [e["name"] for e in employees]

ss = st.session_state
if "f_date" not in ss:
    _init_form(state)
if employees and ss.get("f_emp") not in emp_by_id:
    ss["f_emp"] = employees[0]["id"]
    ss["f_group"] = employees[0]["group"]

if "_flash" in ss:
    st.toast(ss.pop("_flash"))
if store_error:
    st.error(f"Penyimpanan data belum terhubung: {store_error}")

# ----------------------------------------------------------------------------
# Header + filter periode global
# ----------------------------------------------------------------------------
dot = "pulse off" if store_error else "pulse"
live = "Menunggu penyimpanan" if store_error else store.label
md(f"""
<div class="topbar">
  <img src="data:image/png;base64,{logo_b64()}" alt="{APP_NAME} – {APP_TAGLINE}">
  <div class="last-update"><span class="{dot}"></span>
    <span>{esc(core.fmt_last_update(state.get("lastUpdate")))} · {esc(live)}</span></div>
</div>""")

fp1, fp2, fp3, fp4 = st.columns([1.3, 1, 1, 1])
preset = fp1.selectbox("Periode data", core.PERIOD_PRESETS, key="p_preset",
                       help="Berlaku untuk KPI, ringkasan, leaderboard, rekap, dan detail input.")
today = date.today()
c_start = fp2.date_input("Dari", value=today.replace(day=1), key="p_start",
                         format="DD/MM/YYYY") if preset == "Kustom" else None
c_end = fp3.date_input("Sampai", value=today, key="p_end",
                       format="DD/MM/YYYY") if preset == "Kustom" else None
p_start, p_end = core.period_range(preset, today, (c_start, c_end))
if p_start and p_end and p_start > p_end:
    st.warning("Tanggal 'Dari' tidak boleh melewati 'Sampai'. Filter periode diabaikan.")
    p_start = p_end = None
records = core.filter_records(all_records, iso(p_start), iso(p_end))
period_label = ("Semua waktu" if not p_start else
                f"{p_start.strftime('%d/%m/%Y')} – {p_end.strftime('%d/%m/%Y')}")

# KPI
k = core.kpis(employees, records)
active_n = sum(1 for r in core.aggregate_by_employee(employees, records, False))
md(f"""
<div class="kpis">
  <div class="kpi"><div class="l">Total Input</div><div class="v">{k['records']}</div>
    <div class="h">Periode: {esc(period_label)}</div><div class="acc"></div></div>
  <div class="kpi"><div class="l">Base Point</div><div class="v">{fmt_num(k['points'])}</div>
    <div class="h">Akumulasi poin produk</div><div class="acc"></div></div>
  <div class="kpi"><div class="l">Rata-rata Achievement</div><div class="v">{fmt_pct(k['avg'])}</div>
    <div class="h">Dari {active_n} karyawan aktif</div><div class="acc"></div></div>
  <div class="kpi"><div class="l">High Achievers</div><div class="v">{k['high']}</div>
    <div class="h">Achievement ≥ 100%</div><div class="acc"></div></div>
  <div class="kpi"><div class="l">Top Performer</div><div class="v" style="font-size:20px;padding-top:4px">{esc(k['top'])}</div>
    <div class="h">Berdasarkan achievement rate</div><div class="acc"></div></div>
</div>""")

tab_sum, tab_in, tab_lb, tab_emp, tab_det, tab_exp = st.tabs(
    ["📊 Ringkasan", "✍️ Input Harian", "🏆 Leaderboard", "👥 Karyawan", "🗂️ Detail Input", "⬇️ Export & Backup"])

# ----------------------------------------------------------------------------
# Tab Ringkasan
# ----------------------------------------------------------------------------
with tab_sum:
    section("Capaian per Group", "Rata-rata achievement karyawan aktif di tiap group")
    cards = ""
    for g in core.group_summary(employees, records):
        cards += f"""
        <div class="gcard">
          <div class="top"><span class="gp">{g['group']}</span><span class="small">Target {g['target']} poin/orang</span></div>
          <div class="big">{fmt_pct(g['avg'])}</div>
          <div class="sub">{g['active']} dari {g['members']} karyawan aktif · {g['achieved']} mencapai target<br>
            Total {fmt_num(g['points'])} poin</div>
          {bar(g['avg'])}
        </div>"""
    md(f'<div class="cards4">{cards}</div>')

    section("Target & Realisasi Produk", "Realisasi dihitung dari seluruh input pada periode terpilih")
    totals = core.product_realization(records)
    cards = ""
    for key in PRODUCT_KEYS:
        target = core.num(targets.get(key))
        real = totals[key]
        rate = core.product_achievement(real, target)
        remain = ("Target tercapai 🎉" if real >= target else f"Kurang {fmt_num(target - real)} lagi")
        cards += f"""
        <div class="ptc {core.status_class(rate)}">
          <div class="row"><div class="label">{esc(PRODUCT_LABELS[key].upper())}</div>
            <div class="chip">Bobot {fmt_num(PRODUCT_POINTS[key])}</div></div>
          <div class="main">{fmt_num(real)} <span>/ {fmt_num(target)}</span></div>
          <div class="hint">Realisasi / Target Cabang · {remain}</div>
          <div class="meta">{status_pill(rate)}{status_pill(rate, core.product_status_text(rate))}</div>
          {bar(rate)}
        </div>"""
    md(f'<div class="cards3">{cards}</div>')

    with st.expander("⚙️ Ubah Target Cabang per Produk"):
        md("""<div class="note">Target cabang wajib lebih dari 0 dan tersimpan otomatis begitu angka diubah.
        Produk Kopra bernilai 2 poin per akuisisi.</div>""")
        for row_keys in (PRODUCT_KEYS[0:3], PRODUCT_KEYS[3:6], PRODUCT_KEYS[6:9]):
            cols = st.columns(3)
            for col, key in zip(cols, row_keys):
                col.number_input(f"{PRODUCT_LABELS[key]} (bobot {fmt_num(PRODUCT_POINTS[key])})",
                                 min_value=1, step=1, value=int(core.num(targets.get(key))),
                                 key=f"tgt_{key}", on_change=cb_update_target, args=(key,))

# ----------------------------------------------------------------------------
# Tab Input Harian
# ----------------------------------------------------------------------------
with tab_in:
    section("Input Daily Acquisition", "Tanggal dan karyawan dipertahankan setelah simpan agar input berikutnya cepat")
    if not employees:
        md('<div class="empty">Belum ada karyawan.<br>Tambahkan karyawan terlebih dahulu di tab <b>👥 Karyawan</b>.</div>')
    else:
        left, right = st.columns([1.8, 1])
        with left:
            c1, c2, c3 = st.columns([1, 1.6, 1])
            c1.date_input("Tanggal", key="f_date", format="DD/MM/YYYY")
            c2.selectbox("Karyawan", options=list(emp_by_id), key="f_emp",
                         format_func=lambda i: f"{emp_by_id[i]['name']} · {emp_by_id[i]['group']}",
                         on_change=cb_employee_changed)
            c3.selectbox("Group Target", options=GROUPS, key="f_group",
                         format_func=lambda g: f"{g} · Target {TARGETS[g]}")
            pcols = st.columns(3)
            for i, key in enumerate(PRODUCT_KEYS):
                pcols[i % 3].number_input(f"{PRODUCT_LABELS[key]} (×{fmt_num(PRODUCT_POINTS[key])})",
                                          min_value=0, step=1, key=f"f_{key}")
            st.text_input("Remark / Status", key="f_remarks",
                          placeholder="Contoh: pending dokumen / follow-up ulang")
            draft = {k_: int(ss.get(f"f_{k_}") or 0) for k_ in PRODUCT_KEYS}
            p_draft = core.point_of(draft)
            md(f'<div class="preview">Perhitungan otomatis: {fmt_num(p_draft)} base point · '
               f'{fmt_pct(core.achievement_rate(p_draft, ss.get("f_group", "")))} dari target group</div>')
            st.button("💾 Simpan Input", type="primary", on_click=cb_save_record)
        with right:
            cur = emp_by_id.get(ss.get("f_emp"))
            prog = core.employee_progress(employees, records, cur["name"]) if cur else None
            if prog:
                md(f"""
                <div class="panel ctx">
                  <div class="small">Capaian saat ini · {esc(period_label)}</div>
                  <div class="name">{esc(prog['employeeName'])}</div>
                  <div class="big">{fmt_pct(prog['rate'])}</div>
                  <div class="small" style="margin-bottom:8px">{fmt_num(prog['point'])} dari {prog['target']} poin
                    · {prog['count']} input</div>
                  {bar(prog['rate'])}
                  <div style="margin-top:10px">{status_pill(prog['rate'], core.status_text(prog['rate']))}</div>
                </div>""")
            section("Input Terbaru")
            recent = list(reversed(all_records[-5:]))
            table(["Tanggal", "Nama", "Poin"],
                  [[esc(r["date"]), esc(r["employeeName"]), f"<b>{fmt_num(core.point_of(r))}</b>"] for r in recent],
                  "Belum ada input.", 280)

# ----------------------------------------------------------------------------
# Tab Leaderboard
# ----------------------------------------------------------------------------
with tab_lb:
    f1, f2, _ = st.columns([1, 1.4, 1.6])
    lb_group = f1.selectbox("Group", ["Semua Group"] + GROUPS, key="lb_group")
    lb_emp = f2.selectbox("Karyawan", ["Semua Karyawan"] + emp_names, key="lb_emp")
    lb_group_v = None if lb_group == "Semua Group" else lb_group
    lb_emp_v = None if lb_emp == "Semua Karyawan" else lb_emp
    ranking = core.aggregate_by_employee(
        employees, core.filter_records(records, group=lb_group_v, employee=lb_emp_v), False)

    if not ranking:
        md('<div class="empty">Belum ada data untuk filter ini.<br>Coba ubah periode atau filter, '
           'atau tambahkan input di tab <b>✍️ Input Harian</b>.</div>')
    else:
        def pod(i: int, cls: str) -> str:
            if i >= len(ranking):
                return "<div></div>"
            r = ranking[i]
            color = "var(--green)" if r["rate"] >= 100 else "var(--orange)" if r["rate"] >= 80 else "var(--red)"
            medal = ["🥇", "🥈", "🥉"][i]
            return (f'<div class="pod {cls}"><div class="medal">{medal}</div>'
                    f'<div class="name">{esc(r["employeeName"])}</div>'
                    f'<span class="gp">{esc(r["group"])}</span>'
                    f'<div class="rate" style="color:{color}">{fmt_pct(r["rate"])}</div>'
                    f'<div class="pts">{fmt_num(r["point"])} / {r["target"]} poin</div></div>')
        md(f'<div class="podium">{pod(1, "p2")}{pod(0, "p1")}{pod(2, "p3")}</div>')

        rows = []
        for i, r in enumerate(ranking, 1):
            cls = {1: "r1", 2: "r2", 3: "r3"}.get(i, "")
            color = "var(--green)" if r["rate"] >= 100 else "var(--orange)" if r["rate"] >= 80 else "var(--red)"
            rows.append([
                f'<span class="rank {cls}">{i}</span>',
                f'<b>{esc(r["employeeName"])}</b><div class="small">{r["count"]} input</div>',
                f'<span class="gp">{esc(r["group"])}</span>', f'{r["target"]} poin',
                f'<b>{fmt_num(r["point"])}</b>', f'<b style="color:{color}">{fmt_pct(r["rate"])}</b>',
                bar(r["rate"]), status_pill(r["rate"], core.status_text(r["rate"])),
            ])
        table(["Rank", "Nama", "Group", "Target", "Base Point", "Achievement", "Progress", "Status"],
              rows, "", 820)

# ----------------------------------------------------------------------------
# Tab Karyawan
# ----------------------------------------------------------------------------
with tab_emp:
    section("Tambah Karyawan")
    with st.form("add_emp", clear_on_submit=True):
        a1, a2, a3 = st.columns([2, 1.2, 1])
        new_name = a1.text_input("Nama Karyawan", placeholder="Contoh: Andi Pratama")
        new_group = a2.selectbox("Default Group", GROUPS, format_func=lambda g: f"{g} · Target {TARGETS[g]}")
        a3.markdown(spacer(), unsafe_allow_html=True)
        submitted = a3.form_submit_button("➕ Tambah", type="primary")
    if submitted:
        name = " ".join((new_name or "").split())
        if not name:
            st.warning("Nama karyawan wajib diisi.")
        elif any(e["name"].casefold() == name.casefold() for e in employees):
            st.warning(f"Karyawan “{name}” sudah ada.")
        else:
            state["employees"].append({"id": core.uid(), "name": name, "group": new_group})
            commit(state)
            flash(f"✅ Karyawan {name} ditambahkan.")
            st.rerun()

    section("Rekap Karyawan & Target", f"Periode: {period_label}")
    rows = []
    for r in core.aggregate_by_employee(employees, records, True):
        rows.append([
            f'<b>{esc(r["employeeName"])}</b><div class="small">{r["count"]} input</div>',
            f'<span class="gp">{esc(r["group"])}</span>', r["target"],
            *[fmt_num(r[key]) for key in PRODUCT_KEYS],
            f'<b>{fmt_num(r["point"])}</b>', status_pill(r["rate"]),
        ])
    table(["Nama", "Group", "Target", *[esc(PRODUCT_LABELS[x]) for x in PRODUCT_KEYS], "Base Point", "Achievement"],
          rows, "Belum ada karyawan. Tambahkan lewat form di atas.", 1100)

    if employees:
        section("Aksi Karyawan")
        d1, d2, d3, _ = st.columns([2, 1.2, 1, 1.4])
        d1.selectbox("Pilih karyawan", emp_names, key="e_pick")
        d2.markdown(spacer(), unsafe_allow_html=True)
        d2.button("🔎 Lihat Input", on_click=cb_focus_employee)
        d3.markdown(spacer(), unsafe_allow_html=True)
        if d3.button("🗑️ Hapus"):
            delete_employee_dialog(ss.get("e_pick"))

# ----------------------------------------------------------------------------
# Tab Detail Input
# ----------------------------------------------------------------------------
with tab_det:
    g1, g2, g3, _ = st.columns([.8, 1.4, 1.1, 1.2])
    d_group = g1.selectbox("Group", ["Semua Group"] + GROUPS, key="d_group")
    if ss.get("d_emp") not in (["Semua Karyawan"] + emp_names):
        ss["d_emp"] = "Semua Karyawan"
    d_emp = g2.selectbox("Karyawan", ["Semua Karyawan"] + emp_names, key="d_emp")
    d_sort = g3.selectbox("Urutkan Tanggal", ["Terbaru ke Terlama", "Terlama ke Terbaru"], key="d_sort")
    recs = core.filter_records(records, group=None if d_group == "Semua Group" else d_group,
                               employee=None if d_emp == "Semua Karyawan" else d_emp)
    recs = sorted(recs, key=lambda r: (r["date"], r["employeeName"]), reverse=(d_sort == "Terbaru ke Terlama"))

    if not recs:
        md('<div class="empty">Belum ada detail input untuk filter ini.</div>')
    else:
        md(f'<div class="small" style="margin:4px 0 6px">{len(recs)} input · klik satu baris untuk '
           f'mengedit atau menghapus</div>')
        import pandas as pd

        df = pd.DataFrame([{
            "Tanggal": r["date"], "Nama": r["employeeName"], "Group": r.get("group", ""),
            **{PRODUCT_LABELS[key]: int(core.num(r.get(key))) for key in PRODUCT_KEYS},
            "Base Point": core.point_of(r),
            "Achievement (%)": round(core.achievement_rate(core.point_of(r), r.get("group", "")), 1),
            "Remark": r.get("remarks") or "",
        } for r in recs])
        event = show_dataframe(
            df, hide_index=True, on_select="rerun", selection_mode="single-row", key="detail_df",
            column_config={
                "Achievement (%)": st.column_config.NumberColumn(format="%.1f%%"),
                "Base Point": st.column_config.NumberColumn(format="%.1f"),
            })
        rows_sel = []
        try:
            rows_sel = list(event.selection.rows)
        except Exception:  # noqa: BLE001
            pass
        if rows_sel and rows_sel[0] < len(recs):
            sel = recs[rows_sel[0]]
            md(f'<div class="panel" style="padding:12px 16px;margin:8px 0">Dipilih: <b>{esc(sel["employeeName"])}</b> · '
               f'{esc(sel["date"])} · {fmt_num(core.point_of(sel))} poin</div>')
            b1, b2, _ = st.columns([1, 1, 4])
            if b1.button("✏️ Edit", type="primary"):
                edit_dialog(sel["id"])
            if b2.button("🗑️ Hapus", key="del_rec_btn"):
                delete_record_dialog(sel["id"])

# ----------------------------------------------------------------------------
# Tab Export & Backup
# ----------------------------------------------------------------------------
with tab_exp:
    section("Export Laporan")
    x1, x2, x3 = st.columns([1, 1, 1.2])
    ex_start = x1.date_input("Period Start", value=today.replace(day=1), key="x_start", format="DD/MM/YYYY")
    ex_end = x2.date_input("Period End", value=today, key="x_end", format="DD/MM/YYYY")
    fmt = x3.radio("Format", ["XLSX", "PDF"], horizontal=True, key="x_fmt")
    chosen = st.multiselect("Dataset yang diexport", list(core.EXPORT_DATASETS),
                            default=list(core.EXPORT_DATASETS), key="x_sets",
                            format_func=lambda d: core.EXPORT_DATASETS[d])
    md(f"""<div class="note">XLSX hanya memuat sheet yang dipilih; PDF menampilkan tiap dataset sebagai bagian
    laporan terpisah. Leaderboard mengikuti filter Group/Karyawan di tab Leaderboard. Nama file diawali
    <b>{FILE_PREFIX}-</b>.</div>""")
    if ex_start and ex_end and ex_start > ex_end:
        st.error("Period Start tidak boleh melewati Period End.")
    elif not chosen:
        st.info("Pilih minimal satu dataset yang akan diexport.")
    elif ex_start and ex_end:
        s_iso, e_iso = ex_start.isoformat(), ex_end.isoformat()
        sheets = core.build_report_sheets(state, s_iso, e_iso, chosen, lb_group_v, lb_emp_v)
        slug = ("".join(("-" + c.lower() if c.isupper() else c) for c in chosen[0]).lstrip("-")
                if len(chosen) == 1 else "report")
        fname = f"{FILE_PREFIX}-{slug}-{s_iso}-{e_iso}"
        if fmt == "XLSX":
            data, mime, ext = (core.build_xlsx(sheets),
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx")
        else:
            data, mime, ext = (core.build_pdf(sheets, f"Laporan {APP_NAME} – {APP_TAGLINE}",
                                              f"Periode: {s_iso} s.d. {e_iso}"), "application/pdf", "pdf")
        st.download_button(f"⬇️ Download {fmt}", data=data, file_name=f"{fname}.{ext}", mime=mime, type="primary")

    section("Backup & Restore Data")
    md("""<div class="note">Unduh cadangan seluruh data (JSON) secara berkala, terutama bila aplikasi dijalankan di
    layanan dengan disk sementara. Ekspor Firebase dari dashboard lama (node <b>raceDashboard</b>) juga bisa
    diunggah di sini. <b>Mengimpor akan menimpa semua data saat ini.</b></div>""")
    st.download_button("⬇️ Download backup JSON",
                       data=json.dumps({k_: state[k_] for k_ in ("employees", "records", "productTargets")},
                                       ensure_ascii=False, indent=2),
                       file_name=f"{FILE_PREFIX}-backup-{today.isoformat()}.json", mime="application/json")
    st.file_uploader("Impor JSON", type=["json"], key="import_file")
    st.button("Impor & Timpa Data", on_click=cb_import)
