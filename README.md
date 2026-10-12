# HelpDesk Mini

Aplikasi helpdesk multi-tenant untuk technical assessment SVO Connect. Customer membuat tiket dan berkomunikasi dengan Agent secara real-time; setiap bisnis memiliki pengguna dan data yang terisolasi.

## 1. Overview

**Stack:** Next.js App Router, TypeScript, Tailwind CSS, TanStack Query, FastAPI, PostgreSQL, SQLAlchemy, Alembic, dan native WebSocket.

- JWT access/refresh, registrasi bisnis beserta Admin, serta manajemen Agent/Customer oleh Admin.
- RBAC dan isolasi bisnis/Customer di backend; Admin membaca chat, Agent dan Customer dapat mengirim pesan.
- Tiket: pesan pertama, prioritas, filter status, assignment, dan lifecycle `open → in_progress → resolved → closed`; Customer dapat membuka kembali tiket `resolved` miliknya.
- Chat real-time dengan riwayat PostgreSQL dan pembaruan status tanpa refresh.
- Bonus yang diimplementasikan: Docker Compose, login rate limiting dengan countdown 429, pagination/search, notifikasi daftar tiket, unread badges, typing indicator, read receipts, dan lampiran gambar private (local/S3). Logout juga tersedia.

Implementasi tersedia tidak berarti semua skenario deployment telah diverifikasi. M0–M6 tercatat selesai; M7 masih **PENDING VERIFICATION**. Lihat [rencana dan bukti M7](exec-plans/active/M7-final-verification.md) serta [verifikasi lampiran](docs/ATTACHMENT_VERIFICATION.md).

## 2. Live Demo

[Buka HelpDesk Mini di Railway](https://helpdesk-frontend-production-0ce9.up.railway.app).

Target deployment adalah frontend, backend, dan PostgreSQL di Railway. Konfigurasi layanan aktual, ketersediaan demo, kredensial login Railway, dan penggunaan AWS S3 belum diverifikasi dalam pembaruan dokumentasi ini. Dukungan S3 tersedia di kode, tetapi bukan bukti bahwa deployment sedang menggunakannya. Password Docker di bawah tidak diasumsikan berlaku di Railway.

## 3. Quick Start — Docker Compose

Prasyarat: Git, Docker Desktop atau Docker Engine dengan Compose v2 yang aktif; port lokal `3000`, `8000`, dan `5433` tersedia. Ganti `<repository-url>` dengan URL repository ini.

```bash
git clone <repository-url>
cd helpdesk-mini
docker compose up --build -d
docker compose ps
```

Tidak perlu membuat `.env`, memasang Python/Node/PostgreSQL lokal, atau memasukkan password. Compose menunggu PostgreSQL sehat, menjalankan Alembic, menginisialisasi seed, lalu memulai FastAPI dan production build Next.js. Build pertama memerlukan akses internet. Target setup ±15 menit; durasi fresh clone versi final **belum diukur**.

| Layanan | URL |
|---|---|
| Frontend/login | http://localhost:3000/login |
| Backend health | http://localhost:8000/health |
| Swagger/OpenAPI | http://localhost:8000/docs |

Gunakan `localhost` secara konsisten. Browser mengakses REST di `http://localhost:8000` dan WebSocket di `ws://localhost:8000`, bukan hostname internal Docker `backend`.

```bash
# Backend tests + migrasi + pemeriksaan schema; tidak berjalan saat startup normal
docker compose --profile test run --build --rm tests

# Diagnosis, berhenti, jalankan kembali, atau restart
docker compose logs backend
docker compose stop
docker compose up -d
docker compose restart
docker compose down
```

Test profile memakai `test-db` terpisah di tmpfs, bukan database demo. Volume PostgreSQL, gambar lokal, dan JWT secret dipertahankan oleh `stop`, `restart`, serta `down` tanpa `--volumes`. **Jangan gunakan `down --volumes` untuk data yang ingin disimpan.**

Seed awal menyediakan 2 bisnis, 8 pengguna, 5 tiket, dan 7 pesan. Restart melewati seed jika identitas demo lengkap: perubahan pengguna/tiket/pesan tidak direset. Database berisi data tanpa identitas demo lengkap ditolak oleh startup otomatis. JWT secret lokal dibuat secara acak dan disimpan dalam volume.

**Khusus demo lokal:** kredensial publik dan cookie HTTP Compose bukan konfigurasi produksi. Port dibatasi ke loopback; entrypoint demo hanya menerima target database Compose yang telah ditentukan. `.env.compose` tidak diperlukan.

## 4. Manual Setup

Prasyarat: Python 3.12 (sesuai Docker; proyek mendukung 3.11+), `uv`, Node.js 24/npm, dan PostgreSQL 17 aktif. Jalankan perintah PostgreSQL sebagai role lokal yang memiliki izin membuat role/database:

```bash
createuser --pwprompt helpdesk_user
createdb --owner=helpdesk_user helpdesk_mini
```

Dari root repository, salin template, kemudian **edit `backend/.env`**: isi `DATABASE_URL` dengan role/password lokal dan ganti placeholder `JWT_SECRET` dengan nilai acak minimal 32 karakter. Contoh pembangkit secret: `openssl rand -hex 32`; jangan commit hasilnya. Salin hanya dua variabel `NEXT_PUBLIC_*` dari template ke `frontend/.env.local`.

```bash
cp .env.example backend/.env
cd backend
uv sync --frozen
uv run alembic upgrade head
```

Setelah memastikan `DATABASE_URL` menunjuk database **demo lokal**, jalankan seed dari `backend/`:

```bash
DEMO_SEED_PASSWORD='HelpdeskDemo2026!' uv run python -m app.scripts.seed_demo --confirm-demo-data
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Seed manual bersifat transaksional, menggunakan password hash, dan memeriksa konflik data; bukan perintah reset. Jangan menjalankannya pada Railway atau database berharga. Gunakan password khusus demo; jika memilih nilai lain, akun seed mengikuti nilai tersebut.

Di terminal lain, dari root repository:

```bash
cd frontend
npm ci
npm run dev
```

Buka `http://localhost:3000/login`. Setup manual tidak menjalankan migrasi/seed secara otomatis.

## 5. Environment Variables

Referensi lengkap: [`.env.example`](.env.example). Backend membaca `backend/.env` ketika dijalankan dari `backend/`; Next.js membaca `frontend/.env.local`. Jangan commit kedua file atau memasukkan secret ke variabel `NEXT_PUBLIC_*`.

| Variabel | Penggunaan |
|---|---|
| `DATABASE_URL` | PostgreSQL; format `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DB` (URL-encode karakter khusus password). `postgresql://` juga dinormalisasi oleh settings. |
| `JWT_SECRET`, `JWT_ALGORITHM` | Secret privat minimal 32 karakter; algoritma `HS256`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | Umur access/refresh; template 15 menit/7 hari. |
| `CORS_ORIGINS` | Daftar origin eksplisit dipisahkan koma, **bukan JSON atau wildcard**. |
| `REFRESH_COOKIE_SECURE`, `REFRESH_COOKIE_SAMESITE` | Lokal HTTP: `false`/`lax`; HTTPS: `true`. Untuk cross-site gunakan `none` dengan HTTPS dan origin eksplisit. Kebijakan third-party cookies browser tetap berlaku. |
| `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL` | URL backend yang dapat diakses browser; HTTPS/WSS untuk deployment. Nilai Next.js tertanam saat build, sehingga perubahan memerlukan rebuild. |
| `LOGIN_MAX_FAILED_ATTEMPTS`, `LOGIN_FAILED_WINDOW_SECONDS` | Default 5 kegagalan per email ternormalisasi + IP dalam 900 detik; upaya berikutnya mendapat 429 dan `Retry-After`. |
| `LOGIN_IP_MAX_REQUESTS`, `LOGIN_IP_WINDOW_SECONDS` | Default 30 request login per IP dalam 60 detik. |
| `STORAGE_PROVIDER`, `LOCAL_UPLOAD_DIR` | Default `local`; direktori private `.uploads/attachments` pada setup manual. |
| `AWS_REGION`, `AWS_BUCKET_NAME`, `AWS_S3_PREFIX` | Untuk `STORAGE_PROVIDER=s3`; bucket private dan prefix `helpdesk-mini/attachments/`. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Opsional jika memakai credential chain/IAM role; jangan simpan key asli dalam repository. |
| `DEMO_SEED_PASSWORD` | Input khusus seed manual; minimal 12 karakter. Compose sudah mengaturnya untuk demo lokal. |

Compose menyuplai konfigurasi sendiri dan memakai volume upload `/var/lib/helpdesk-uploads`. Railway memakai service variables, bukan file `.env` lokal: atur database privat, JWT secret unik, origin frontend yang tepat, cookie HTTPS, serta URL API/WSS sebelum build frontend. Jalankan `alembic upgrade head` sebelum backend; **jangan gunakan `start_demo` sebagai entrypoint produksi**.

S3 memerlukan bucket private, Block Public Access, dan IAM minimum `PutObject`, `GetObject`, `DeleteObject` pada prefix aplikasi. Gambar disajikan melalui endpoint terautentikasi, bukan public S3 URL. Jangan mengubah bucket/provider/root tanpa mempertimbangkan lokasi lampiran lama. Runtime S3 Railway masih perlu diverifikasi secara terpisah.

## 6. Demo Accounts

Password bersama untuk **seed Docker lokal baru**: `HelpdeskDemo2026!`. Masing-masing bisnis memiliki 1 Admin, 1 Agent, dan 2 Customer; password akun yang sudah diubah tidak direset saat restart.

| Bisnis | Nama | Role | Email |
|---|---|---|---|
| Northstar Support | Nadia Admin | Admin | admin@northstar.helpdeskmini.dev |
| Northstar Support | Andi Agent | Agent | agent@northstar.helpdeskmini.dev |
| Northstar Support | Citra Customer | Customer | customer1@northstar.helpdeskmini.dev |
| Northstar Support | Dimas Customer | Customer | customer2@northstar.helpdeskmini.dev |
| Orbit Services | Olivia Admin | Admin | admin@orbit.helpdeskmini.dev |
| Orbit Services | Raka Agent | Agent | agent@orbit.helpdeskmini.dev |
| Orbit Services | Sari Customer | Customer | customer1@orbit.helpdeskmini.dev |
| Orbit Services | Tono Customer | Customer | customer2@orbit.helpdeskmini.dev |

## 7. Skenario Demo (3–5 Menit)

1. Login sebagai Northstar Customer 1; buat tiket beserta pesan pertama.
2. Di browser/profil terpisah, login sebagai Northstar Agent, buka tiket tersebut, lalu ambil assignment sendiri. Gunakan sesi terpisah agar cookie tidak saling mengganti.
3. Kirim pesan dua arah tanpa refresh; buka kembali tiket untuk melihat riwayat tersimpan.
4. Agent mengubah status `open → in_progress → resolved`; Customer melihat perubahan langsung dan dapat reopen `resolved → open`. Tiket `closed` tidak menerima pesan atau reopen.
5. Login sebagai Orbit Agent di sesi terpisah dan buka ID tiket Northstar yang sama. Request detail harus mendapat `404`, tanpa data tiket/pesan. Periksa tab Network browser.
6. Tunjukkan search/filter, unread badge/notifikasi, typing/read receipts, dan upload gambar. Admin dapat mendemonstrasikan pembuatan pengguna serta assignment ke Agent lewat sesi sendiri.

## 8. Catatan Teknis dan Limitasi

- **Modular monolith:** router menangani HTTP, service menangani aturan bisnis/otorisasi, SQLAlchemy dan Alembic menangani data. Struktur `backend/` dan `frontend/` tetap dalam satu repository.
- **Keamanan:** Argon2 untuk password; access JWT disimpan di memori frontend, refresh JWT dalam cookie HttpOnly. Token type, expiry, RBAC, bisnis, dan kepemilikan Customer diperiksa backend, termasuk WebSocket. Refresh/logout memvalidasi origin browser. Logout membersihkan sesi lokal, tetapi salinan JWT stateless tidak langsung dicabut; refresh rotation/revocation belum tersedia.
- **Integritas:** tiket dan pesan pertama dibuat atomik; pesan disimpan sebelum broadcast. PostgreSQL adalah sumber kebenaran. TanStack Query dan refetch setelah reconnect memulihkan state yang terlewat.
- **Single process:** connection manager WebSocket dan rate limiter masih in-memory. Gunakan satu backend worker/instance. Restart menghapus state limiter; broadcast best-effort belum memakai durable outbox sehingga commit yang diikuti proses mati dapat kehilangan event langsung.
- **Proxy:** Compose menonaktifkan proxy headers. Jangan mempercayai `X-Forwarded-For` dari sembarang klien; deployment reverse proxy harus mengatur trusted proxy secara tepat agar limit per-IP tidak mengelompokkan semua pengguna.
- **Lampiran:** satu gambar JPEG/PNG/WebP per pesan, maksimal 5 MiB; backend memvalidasi dan mengenkode ulang gambar. Storage dan transaksi DB tidak atomik; orphan cleanup, malware scanning, serta quota belum tersedia. Backup database dan object storage bersama-sama.
- **Verifikasi tersisa:** rehearsal fresh clone versi final yang diukur, video demo, pemeriksaan aksesibilitas lengkap, serta browser/Docker/S3 untuk bonus sesuai catatan verifikasi. Tidak ada klaim production-ready dari build atau mocked tests saja.

Detail: [arsitektur](ARCHITECTURE.md), [requirements](docs/REQUIREMENTS.md), [API contract](docs/API_CONTRACT.md), [security](docs/SECURITY.md), dan [UI/UX](docs/FRONTEND_UIUX.md).

## 9. Testing dan Video Demo

Cara paling sederhana untuk backend adalah test profile pada bagian Docker. Untuk pytest lokal, siapkan **database PostgreSQL baru yang disposable** bernama berakhiran `_test`; jangan gunakan database demo/development berisi data. Suite mencakup perubahan schema/migration downgrade pada database test.

```bash
# Dari root; sesuaikan izin PostgreSQL lokal
createdb --owner=helpdesk_user helpdesk_verification_test
cd backend
# Ganti USER:PASSWORD sesuai role lokal, bukan kredensial produksi
export TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/helpdesk_verification_test'
export DATABASE_URL="$TEST_DATABASE_URL"
export M1_TEST_DATABASE_URL="$TEST_DATABASE_URL"
uv run alembic upgrade head
uv run pytest -q --tb=short
uv run alembic check
```

Di terminal lain, dari root:

```bash
cd frontend
npm test
npm run typecheck
npm run lint
npm run build
```

Frontend tests yang tersedia memakai Node test runner; ini **bukan** browser E2E. Gunakan dua sesi browser pada skenario demo untuk verifikasi integrasi nyata. Bukti pengujian historis ada di [execution plans](exec-plans/) dan [checklist bonus](docs/ATTACHMENT_VERIFICATION.md); bukan hasil pengujian ulang revisi dokumentasi ini.

**Video demo:** TODO: [Vidio Demo HelpDesk Mini](https://drive.google.com/file/d/1xietUkvIYXGsDzfuCSezOv9ZN3R65a-Q/view?usp=drive_link).
