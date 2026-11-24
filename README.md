# PACU – Pantau Akuisisi & Capaian Unit

Dashboard Streamlit untuk memantau akuisisi harian, target produk, dan capaian karyawan.

## Fitur
- **Filter periode global** (Semua waktu, Hari ini, 7 hari terakhir, Bulan ini, Bulan lalu, Kustom) – berlaku untuk KPI, ringkasan, leaderboard, rekap, dan detail.
- **📊 Ringkasan** – KPI, capaian per group (R01–R04), kartu target & realisasi 9 produk (status Achieved / On Track / Need Push, sisa menuju target), pengaturan target cabang.
- **✍️ Input Harian** – form cepat (tanggal & karyawan tetap tersimpan setelah simpan), perhitungan poin otomatis, kartu capaian karyawan, daftar input terbaru.
- **🏆 Leaderboard** – podium 3 teratas + tabel ranking dengan filter group/karyawan.
- **👥 Karyawan** – tambah karyawan, rekap per produk, hapus karyawan (dengan konfirmasi).
- **🗂️ Detail Input** – klik baris untuk **Edit** (dialog) atau **Hapus** (konfirmasi).
- **⬇️ Export & Backup** – XLSX/PDF dengan pilihan dataset (file berawalan `pacu-`), backup & restore JSON.

Aturan hitung: `base point = Σ(jumlah × bobot)`; `achievement = base point ÷ target group × 100`
(target group: R01=6, R02=10, R03=15, R04=20). Bobot: Livin 1, Merchant 1, MCY/MTI 0,5, EDC 1, MTR 1, MTB 5, Prioritas 5, Deposito 5, Kopra 2.
Group karyawan di leaderboard/rekap mengikuti group pada input terakhirnya.

## Menjalankan lokal
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
Data tersimpan di `data/pacu_data.json`. Saat pertama kali jalan, file ini dibuat dari `data/seed.json`
(17 karyawan, target produk, dan 5 input contoh). Ubah `seed.json` bila ingin memulai dari data kosong.

## Deploy
- **Streamlit Community Cloud**: push folder ini ke GitHub, pilih `app.py`. **Perhatian:** disk di sana tidak permanen
  (data bisa hilang saat restart). Pakai Firebase (di bawah) atau rutin unduh backup JSON.
- **Server/VPS/Docker sendiri**: data di `data/` permanen selama folder dipertahankan. Lokasi file bisa diubah dengan env `PACU_DATA_FILE`.

## Opsi: Firebase Realtime Database (data bersama & permanen)
Buat `.streamlit/secrets.toml` (jangan di-commit):
```toml
firebase_db_url = "https://<project-id>-default-rtdb.<region>.firebasedatabase.app"
firebase_auth = ""                 # opsional: database secret / token bila Rules tidak terbuka
firebase_node = "raceDashboard"    # opsional: nama node data (default ini agar data lama tetap terbaca)
```
Database Rules harus mengizinkan akses REST dari aplikasi ini.

## Struktur
```
app.py          tampilan Streamlit
core.py         logika hitung, export XLSX/PDF, penyimpanan (JSON / Firebase)
data/seed.json  data awal
assets/         logo & ikon
tests/          python tests/test_core.py   (logika)
                python tests/smoke_stub.py  (menjalankan app.py dengan Streamlit tiruan)
```

## Penyimpanan Supabase (data tersimpan permanen & sinkron antar perangkat)

1. Jalankan `supabase_setup.sql` sekali di Supabase (SQL Editor).
2. Isi `supabase_url` dan `supabase_key` (Secret key) di Streamlit Cloud -> Settings -> Secrets
   (lihat `.streamlit/secrets.toml.example`). Tanpa secrets, app memakai file lokal sementara.
3. Perangkat lain memperbarui tampilan otomatis sekitar 8 detik setelah ada data baru.

Mode gelap: toggle "Mode gelap" di bagian atas (pilihan diingat lewat `?tema=gelap` di alamat).
