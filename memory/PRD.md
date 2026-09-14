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

## Backlog / Remaining
- P1: Auto-isi nilai "kemarin" (stock_ok_prev, total_stock_prev) dari laporan tanggal sebelumnya; master item (lane/type/ICS/T/T) untuk autocomplete form.
- P2: Export Excel dengan layout asli DATA STOCK; brute-force lockout; password reset; split server.py.

## Next Tasks
- Verifikasi user terhadap data hasil seed dari DATA STOCK.xlsx.
