"""Smoke test: jalankan app.py dengan stub 'streamlit' (hanya cek tidak ada error, HTML terbentuk, callback jalan)."""
import os, sys, types, tempfile, runpy, datetime
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.environ["PACU_DATA_FILE"] = os.path.join(tempfile.mkdtemp(), "d.json")

class SS(dict):
    __getattr__ = dict.get
    def __setattr__(self, k, v): self[k] = v

calls = {"md": [], "widgets": [], "toast": [], "press": (lambda key: False)}
class Ctx:
    def __enter__(s): return s
    def __exit__(s, *a): return False
    def __getattr__(s, name): return lambda *a, **k: stub_widget(name, *a, **k)

class Event:
    class selection: rows = []

st = types.ModuleType("streamlit")
def stub_widget(name, *a, **k):
    key = k.get("key"); calls["widgets"].append((name, key))
    if name == "markdown": calls["md"].append(a[0]); return None
    if name == "button": return calls["press"](key or "")
    if name in ("download_button", "form_submit_button"): return False
    if name == "toast": calls["toast"].append(a[0]); return None
    if key and key in st.session_state: return st.session_state[key]
    if name == "text_input": return k.get("value", "")
    if name == "number_input": return k.get("value", 0)
    if name == "date_input": return k.get("value")
    if name == "selectbox": return a[1][0] if len(a) > 1 else None
    if name == "multiselect": return k.get("default")
    if name == "radio": return a[1][0]
    if name == "columns":
        n = a[0] if isinstance(a[0], int) else len(a[0]); return [Ctx() for _ in range(n)]
    if name == "tabs": return [Ctx() for _ in a[0]]
    return None
st.session_state = SS(); st.secrets = {}; st.query_params = {}; st.context = types.SimpleNamespace(theme=types.SimpleNamespace(type='light'))
st.fragment = lambda *a, **k: (lambda f: f)
st.cache_resource = lambda f: f; st.cache_data = lambda f: f
st.set_page_config = lambda **k: None
st.dialog = lambda *a, **k: (lambda f: f)
st.rerun = lambda: None
st.expander = lambda *a, **k: Ctx()
st.code = lambda *a, **k: None
st.form = lambda *a, **k: Ctx()
st.markdown = lambda s, **k: calls["md"].append(s)
st.dataframe = lambda *a, **k: Event()
st.column_config = types.SimpleNamespace(NumberColumn=lambda **k: None)
st.columns = lambda spec, **k: stub_widget("columns", spec)
st.tabs = lambda labels: stub_widget("tabs", labels)
for n in ["date_input","selectbox","text_input","number_input","button","download_button","checkbox","multiselect",
          "radio","file_uploader","toast","error","info","warning","success","write","form_submit_button"]:
    setattr(st, n, (lambda n: lambda *a, **k: stub_widget(n, *a, **k))(n))
sys.modules["streamlit"] = st

if __name__ == "__main__":
    runpy.run_path(os.path.join(ROOT, "app.py"), run_name="__main__")
    html = "\n".join(calls["md"])
    for needle in ["13,3%", "550%", "MHD Hendrianto", "Need Push", "On Track", "Capaian per Group", "PACU"]:
        assert needle in html, needle
    for banned in ["Radio Dalam", "SENATOR", "Senator", "RACE", "race-by", "KCP"]:
        assert banned not in html, banned
    print("widgets:", len(calls["widgets"]), "| html chunks:", len(calls["md"]))
    print("OK: app.py berjalan sampai akhir dengan stub")

    ns = runpy.run_path(os.path.join(ROOT, "app.py"), run_name="smoke")
    ss = st.session_state
    ss["f_emp"] = "emp-09"; ss["f_group"] = "R01"; ss["f_date"] = datetime.date(2026, 11, 24)
    for k in ["livin","merchant","mcy","edc","mtr","mtb","prioritas","deposito","kopra"]: ss[f"f_{k}"] = 0
    ns["cb_save_record"](); assert len(ns["load_state"]()["records"]) == 5   # produk kosong ditolak
    ss["f_prioritas"] = 1; ss["f_livin"] = 2; ss["f_remarks"] = " tes "
    ns["cb_save_record"]()
    s_ = ns["load_state"]()
    assert len(s_["records"]) == 6 and s_["records"][-1]["remarks"] == "tes"
    assert ss["f_livin"] == 0 and ss["f_emp"] == "emp-09" and ss["f_date"] == datetime.date(2026, 11, 24)
    # dialog edit & hapus (fungsi langsung, tombol dianggap ditekan)
    rid = s_["records"][-1]["id"]
    calls["press"] = lambda key: key.startswith("ed_save")
    ss[f"ed_prioritas_{rid}"] = 3
    st.date_input = lambda *a, **k: k["value"]
    st.text_input = lambda *a, **k: k.get("value", "")
    st.selectbox = lambda label, opts, **k: opts[k.get("index", 0)]
    ns["edit_dialog"](rid)
    assert ns["load_state"]()["records"][-1]["prioritas"] == 3 and len(ns["load_state"]()["records"]) == 6
    calls["press"] = lambda key: key.startswith("del_ok")
    ns["delete_record_dialog"](rid); assert len(ns["load_state"]()["records"]) == 5
    # employee
    st2 = ns["load_state"](); st2["employees"].append({"id": "x", "name": "Budi", "group": "R02"}); ns["commit"](st2)
    calls["press"] = lambda key: key == "demp_ok"
    ns["delete_employee_dialog"]("Budi"); assert len(ns["load_state"]()["employees"]) == 17
    ss["tgt_livin"] = 100; ns["cb_update_target"]("livin"); assert ns["load_state"]()["productTargets"]["livin"] == 100
    ss["tgt_livin"] = 0; ns["cb_update_target"]("livin"); assert ss["tgt_livin"] == 100
    print("OK: callback & dialog simpan/edit/hapus/employee/target")
