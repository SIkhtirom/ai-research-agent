# expose.sh — Bagikan Aplikasi ke Penguji Remote (Lokal)

Menjalankan Backend + Frontend di laptop Anda lalu membuka **jalan publik** lewat
*tunnel* lokal (ngrok / localtunnel) — **tanpa deploy ke cloud**. Hasilnya URL
publik yang bisa langsung dikirim ke rekan penguji.

---

## 1. Prasyarat (periksa dulu)

| Komponen | Cara instal / cek |
|---|---|
| Bash (Linux/WSL2) | `echo $0` harus menunjukkan bash. Di Windows gunakan **WSL2** atau Git Bash. |
| Dependensi backend | `cd backend && python -m pip install -r requirements.txt` |
| Dependensi frontend | `cd frontend && npm install` |
| **ngrok** (disarankan) | `https://ngrok.com/download` — lalu `ngrok config add-authtoken <TOKEN>` sekali saja |
| atau **localtunnel** | `npm install -g localtunnel` (perintahnya `lt`) |

Skrip **mendeteksi otomatis**: pakai ngrok kalau ada, kalau tidak pakai `lt`.
Bisa dipaksa lewat `TUNNEL_TOOL=ngrok` / `TUNNEL_TOOL=lt`.

---

## 2. Jalankan

```bash
chmod +x expose.sh
./expose.sh
```

Output: dua URL publik — **Frontend** (dikirim ke teman) dan **Backend API**.

> **Penting untuk penguji remote:** Frontend memakai `http://127.0.0.1:8000`
> secara default — itu mengacu ke **localhost si penguji**, bukan API Anda. Agar
> benar-benar bisa dipakai rekan, ekspos backend juga:

```bash
EXPOSE_BACKEND=1 ./expose.sh
```

Skrip lalu membuat tunnel backend, dan menyalakan frontend dengan
`NEXT_PUBLIC_API_URL` (= origin tunnel backend; `/api/v1` ditambahkan kode
klien) sehingga **upload dokumen dari URL publik langsung sampai ke API Anda**.
Secara otomatis skrip juga menyalakan `CORS_ALLOW_ANY_ORIGIN=1` pada backend
agar origin URL ngrok diterima (aman karena backend memakai
`allow_credentials=False`).

Punya tunnel backend sendiri (mis. sudah berjalan)? Lewati pembuatan otomatis:

```bash
EXPOSE_BACKEND=1 BACKEND_PUBLIC_URL=https://your-ngrok.ngrok.io ./expose.sh
```

---

## 3. Berhenti dengan bersih

Tekan **Ctrl+C**. Trap `cleanup` mematikan secara bertahap: tunnel → frontend →
backend (tidak ada proses yang nyangkut). Cek dengan `ps aux | grep -E 'uvicorn|next|ngrok|localtunnel'`.

---

## 4. Catatan

- Log disimpan di `/tmp/ai-research-expose/` (ngrok.log, lt-<port>.log) untuk
  pemeriksaan bila tunnel tidak muncul.
- ngrok free hanya bisa 1 agen; kalau `EXPOSE_BACKEND=1` dengan ngrok, dua tunnel
  dibuka dalam **satu proses ngrok** (URL dibaca dari admin API `:4040`).
- localtunnel kadang meminta konfirmasi/email pada browser tester untuk domain
  `.loca.lt` — itu normal.
- File ini murni lokal: tidak mengubah konfigurasi, tidak menulis `data/`,
  tidak mengekspos secret, dan `.env` tidak terlibat dalam tunnel.