# PRD — Control Data Stock & Production (Automotive Manufacturing MES)

## Problem Statement
Aplikasi web profesional untuk Control Data Stock & Production di perusahaan manufaktur otomotif: monitoring produksi SMT, produksi LAMP ASSY, stock SMT, kebutuhan produksi, dan variance stock. Menggantikan laporan Excel manual dengan perhitungan otomatis. Bahasa Indonesia, tema industrial dark.

## Architecture
- Backend: FastAPI + MongoDB (motor), JWT auth (Bearer token in localStorage + httpOnly cookie), all routes /api prefixed.
- Frontend: React 19 + React Router + Tailwind + shadcn/ui + Recharts. Generic CrudPage drives 5 data modules.
- Auto-calculations server-side; per-user module permissions (none/read/write) with role defaults (ROLE_DEFAULT_PERMS) + admin override (users.permissions).
- Data schema mirrors company Excel "DATA STOCK.xlsx" (columns A–AC), one row per Tanggal + ICS No. per module.

## Data Model (sesuai Excel, since 2026-09)
- smt_production: lane,type,ics_no,tt,led_rank,smt1..3 → cap_h=3600/tt, total
- lamp_production: plan_assy, assy1..3, stock_ok_prev → total, blc=stock_ok_prev−plan_assy, achievement, status
- smt_stock: stock_ok_prev, coating, belum_cutting, belum_ict, belum_fct, ok, tray → total, wip, status OK/WIP/KOSONG
- production_needs: plan_assy, stock_ok_prev → blc, fulfillment, status CUKUP/PAS/SHORTAGE
- variance: total_stock_prev, smt_total, assy_total, smt3, assy3, actual_total_stock → stok_jam=actual−smt3+assy3, stock_sistem=prev+smt−assy, variance=actual−sistem, variance_status
- Seed: /app/backend/seed/data_stock.json (141 items), guarded by db.meta seed version.

## User Personas / Roles
- admin (owner: ariyantyoni@gmail.com) — full access + Manajemen User
- management — full data write
- production_planning (PPIC) — stock, needs, variance
- production_control (PC) — SMT & LAMP production, variance
- smt — SMT production & stock
- assembly — LAMP ASSY production

## Core Requirements (static)
- Login + RBAC; Dashboard KPI + charts; SMT & LAMP production monitoring; SMT stock with auto status; needs vs stock shortage; variance vs opname; Excel/CSV import; multi-dimension filters; CSV export.

## Implemented (2026-06)
- JWT auth (login/me/logout/register), admin + 5 demo users auto-seeded.
- Dashboard: 8 KPI cards, SMT trend area chart, stock status pie, LAMP bar chart, top shortage list, date-range filter.
- 5 CRUD modules (SMT production, LAMP production, SMT stock, production needs, variance) with filters, add/edit/delete, import, export.
- Auto-calc: achievement, yield, good, stock status (AMAN/REORDER/CRITICAL), shortage balance (join stock↔needs), variance/accuracy.
- Excel/CSV import with preview + confirm. Manajemen User (admin).
- Tested: 26/26 backend pytest + full frontend playwright, 100% pass.

## Implemented (2026-09) — Excel alignment + User Management
- All 5 modules refactored to Excel columns/formulas above; filters by tanggal/lane/type/ICS No./status.
- Dashboard rebuilt: SMT total, Assy plan vs actual, shortage (BLC<0), variance, stock OK/total/WIP, stock composition pie, SMT per lane per shift, top shortage/variance.
- Import: downloadable Excel template per modul (1 header row, label Indonesia), preview shows invalid/unknown columns, confirm upserts by (date, ics_no).
- Manajemen User: tambah/edit/hapus, reset password, role, matrix hak akses per modul (Tidak ada/Lihat/Ubah) dengan override; nav & routes guarded; backend require_perm.
- Tested: 23/23 backend pytest + Playwright e2e (iteration_2), 100% pass.
- Nilai kemarin otomatis: GET /api/prev-values?date&ics_no → stock_ok_prev/total_stock_prev dari Stock SMT tanggal sebelumnya; RecordDialog mengisi otomatis (mode tambah) dengan hint sumber, nilai tetap bisa diubah manual.
- Master Item (modul `items`, hak akses tersendiri): CRUD + import/template, 119 item unik di-seed dari Excel; ItemPicker (combobox cari) di semua form tambah/edit mengisi Lane/Type/ICS/T-T/LED Rank/Tray otomatis.
- Login via **username + password** (email tetap diterima sebagai fallback); kotak "Akun demo" di halaman login dihapus. User punya field `username` (unik), email opsional; admin utama username `admin` (ADMIN_USERNAME).
- Bugfix Tambah User: user tanpa email gagal 500 (unique index email null) → email tidak disimpan jika kosong, partial unique index, DuplicateKeyError → 400. Teruji iteration_3 (10/10 + e2e).
- Tema diubah ke **light/putih** (CSS variables di index.css; warna aksen -400 → -600 untuk kontras); tabel CrudPage diberi garis vertikal pembatas kolom (border-r) + header abu muda.
- (2026-09-15) **Produksi LAMP ASSY digabung ke Produksi SMT & ASSY** sesuai CSV `smt-production-ISE-PRDM-29.csv`: kolom TANGGAL, LANE, PRODUCT (REGULER/SPO), TYPE, ICS NO, T/T, CAP/H, PLANING, ACT S3/S1/S2, TOTAL SMT, ACHV %, PLAN ASSY S3/S1/S2, TOTAL PLAN, BALANCE (=Total SMT − Total Plan). Endpoint/menu lamp-production dihapus; dashboard & Master Item (field product) disesuaikan; import CSV asli langsung didukung (zero-pad ICS, kolom turunan diabaikan, upsert key date+ics_no+type). Seed v3 dari /app/backend/seed/smt_production.csv (86 baris). Teruji iteration_4 (12/12 + e2e).
- (2026-09-21) **Audit Trail** (log CREATE/UPDATE/DELETE + import, before/after, IP & user agent; halaman /audit dgn filter; modul `audit` default admin write/management read; kolom Diinput oleh & Waktu Input di semua tabel), **Dark/Light mode** (ThemeContext, localStorage cds_theme, default prefers-color-scheme, CSS vars .dark), **Peringatan duplikat** (409 DUPLICATE + dialog Update Data/Batal, force=true menimpa & tercatat audit; ringkasan import baru/duplikat/dilewati), **Notifikasi in-app** (users.notify per user diatur admin; bell + badge + riwayat /notifications; polling 30 dtk; aktor tidak menerima notifikasi sendiri). Teruji iteration_5 (7/7 + e2e).
- (2026-09-22) **Produksi SMT & ASSY format CSV baru** (`smt-production.csv`): PLANING SMT, ACT SMT S3/S1/S2, TOTAL ACT SMT, ACHV %, PLAN ASSY, ACT ASSY S3/S1/S2, TOTAL ACT ASSY, BALANCE (= Total Act SMT − Total Act Assy, sesuai pilihan user). Seed v4: 84 baris 2026-09-22. **Backup & Restore** (modul `backup`, admin only): export .zip (JSON per koleksi + meta.json; .rar tidak tersedia di server → user setuju .zip), preview & restore ganti seluruh data 5 modul data (users/audit tidak ditimpa), tercatat audit RESTORE/BACKUP. **Stock OK Kemarin tertaut H-1**: list & prev-values pakai record Stock SMT tanggal H-1 (ics_no+type, fallback tanggal terakhir sebelum H); edit manual → stock_ok_manual=true tidak ditimpa. Teruji iteration_6 (7/7 + e2e).
- (2026-09-23) **Integrasi 4 modul**: filter PRODUCT (ALL PRODUCT) di Produksi/Stock/Kebutuhan/Variance/Master Item/Dashboard + baris TOTAL mengikuti filter; Stock SMT: kolom PRODUCT (record atau Master Item via ics_no; BELUM DIMAPPING), "Total Stock Hari Ini", master **Standar Stock** (koleksi stock_standards, key product+lane, menu & modul `stock_standards`), INDIKATOR PASS/MINUS/OVER/BELUM DISET; **Kebutuhan Assy VS. Stock SMT** = view otomatis dari smt_production ⨝ smt_stock ⨝ items (kondisi_produksi ON/OFF dari planing_smt, stock_ok_today = total stock hari yang sama, T/T Assy & material_per_unit dari Master Item, waktu_shortage jam = stock ÷ mpu × tt_assy ÷ 3600, N/A jika tidak valid); **Variance Stock** = view otomatis per record stock (prev total, smt_total/assy_total dari produksi, status OK / VARIANCE − / VARIANCE + / BELUM DICEK). Kolom Aksi/Diinput oleh/Waktu Input/Keterangan dihapus dari 2 view (koleksi production_needs & variance lama tetap di DB & backup). Teruji iteration_7 (18/18 + e2e).
- (2026-09-23) Standar Stock diubah ke kunci **LANE + PRODUCT + TYPE** (form select dari master); 104 record lama yang user isi dengan TYPE di kolom Product dimigrasi otomatis (type ← product, product ← Master Item), 2 record tanpa type diberi type "" untuk diedit user. Indikator Stock SMT memakai kunci baru.
- (2026-09-24) Stock SMT: kolom KONDISI PRODUKSI (paling kanan setelah Status, tertaut ke Planing SMT produksi tanggal+ICS+Type); Kebutuhan: Kondisi Produksi dipindah ke kanan Waktu Shortage, Stock OK Hari Ini = 0 bila belum ada stock; kolom TRAY dihapus dari Master Item & Stock SMT (field & template); items tanpa material_per_unit diisi default 1.
- (2026-09-24) Kebutuhan: urutan kolom setelah Material/Unit → Status, Waktu Shortage, Kondisi Produksi.


## Implemented (2026-06) — Kebutuhan format Excel + input ala Excel
- Kebutuhan Assy VS. Stock Part Production = grid 27 kolom sesuai FORMAT Excel (TANGGAL…STATUS MESIN S2) + baris header grup, header sticky, scroll horizontal, filter Product/Lane/Proses/Group/Status Part, pencarian, ringkasan status, Export CSV.
- Baris = semua Master Item (ics_no+type) per tanggal; input disimpan di koleksi `needs_entries` (unik date+ics_no+type; ikut backup/restore). Data koleksi production_needs lama tetap aman.
- Rumus: BALANCE = (ACT STOCK − PLAN CUSTOMER) + ACTUAL S3+S1+S2; LEVEL STOCK = ACT STOCK ÷ STD MAX; BALANCE Sx = ACTUAL − PLAN; STATUS PART ≤0 SHORTAGE, ≤MID POTENSI, >MID TIDAK (MID=(MIN+MAX)/2), "STD BELUM DISET" bila std kosong. ACT STOCK JAM 01:00 = TOTAL smt_stock SHIFT 3 tanggal sama (null → "-").
- STATUS MESIN S3/S1/S2 dropdown ON/OFF/DANDORI per shift; traceability field_updated_by/at + audit log.
- Komponen ExcelGrid (Enter/Tab/Panah/Esc/F2/Delete, auto-save per cell, indikator Menyimpan/Tersimpan/Gagal + Coba lagi). Dipakai juga di Stock Part Production (GROUP 1–6, PART RAGU-RAGU) via CrudPage `inlineEdit`.
- Endpoint: GET /api/needs-grid?date, PATCH /api/needs-grid/cell, PATCH /api/smt-stock/{id}/cell (angka bulat ≥0, role read → 403).
- Teruji iteration_8 (backend 45/45 setelah fix, frontend e2e lulus).


## Implemented (2026-06, iterasi 9) — Import fix, Kebutuhan v2, Dashboard v2
- FIX import Master Item: CSV non-UTF8 (cp1252/0xA0), delimiter ';', .xls (xlrd), header nbsp, angka koma; update import hanya menimpa kolom yang ada di file; baris invalid (STD MIN>MAX) dilewati per baris.
- Kebutuhan: kolom ACTUAL CUSTOMER (ASSY) (editable), ACHIEVEMENT S3/S1/S2 = ACTUAL/PLAN×100 ('-' bila plan 0). Import Excel (mode Tambah/Update, kunci TANGGAL+ICS NO+TYPE, preview, validasi, ringkasan) + Export Excel. Endpoint /api/needs-grid/import/{template,preview,confirm}.
- Stock Part Production: kolom INDIKATOR dihapus, STATUS PART = status Kebutuhan (date+ics+type) / 'BELUM TERSEDIA'; filter Status Part.
- Dashboard /api/dashboard/summary ditulis ulang dari needs_entries + smt_stock + items: chart PLAN=ΣPLAN CUSTOMER, ACTUAL=ΣACTUAL S3+S1+S2 (pilihan user, bukan BALANCE); kartu Part (ΣPLAN/ACTUAL shift), Lamp Assy (PLAN/ACTUAL CUSTOMER); Item Shortage (TYPE unik master, status tanggal terakhir, terburuk per TYPE); Pencapaian 4 kategori >97 / >96–97 / 90–96 / <90 per TYPE (total actual/total plan); Top Shortage BALANCE terendah; Komposisi per GROUP master (TYPE unik + total stock terbaru).
- Teruji iteration_9: 64/64 backend, frontend e2e lulus.


## Implemented (2026-06, iterasi 10) — Master Item data user + Export/Import Excel
- Master Item diperbarui dari items_.xlsx user (618 item, semua update, 0 duplikat): GROUP angka → "GROUP n" (110 kosong), STD MIN/MAX terisi 508 item.
- STD MIN > MAX kini disimpan apa adanya + field `std_warning` ("STD MIN > MAX", 15 item) dengan ikon peringatan di tabel & hitungan peringatan di preview import (keputusan user).
- Export di semua halaman CrudPage kini .xlsx asli via POST /api/export/xlsx (ICS No disimpan sebagai teks agar nol di depan aman); file export bisa langsung di-import ulang (round-trip diuji: 618 duplikat, 0 invalid).
- Fix hitungan preview import ("new" tidak lagi negatif), dialog import tidak terpotong.

## Backlog / Remaining
- P1: Import Excel untuk grid Kebutuhan (PLAN CUSTOMER/PLAN/ACTUAL).
- P2: Export Excel dengan layout asli DATA STOCK; brute-force lockout; password reset; split server.py.

## Next Tasks
- Verifikasi user terhadap data hasil seed dari DATA STOCK.xlsx.
