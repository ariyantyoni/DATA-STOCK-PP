# PRD — Control Data Stock & Production (Automotive Manufacturing MES)

## Problem Statement
Aplikasi web profesional untuk Control Data Stock & Production di perusahaan manufaktur otomotif: monitoring produksi SMT, produksi LAMP ASSY, stock SMT, kebutuhan produksi, dan variance stock. Menggantikan laporan Excel manual dengan perhitungan otomatis. Bahasa Indonesia, tema industrial dark.

## Architecture
- Backend: FastAPI + MongoDB (motor), JWT auth (Bearer token in localStorage + httpOnly cookie), all routes /api prefixed.
- Frontend: React 19 + React Router + Tailwind + shadcn/ui + Recharts. Generic CrudPage drives 5 data modules.
- Auto-calculations server-side; role-based write permissions (WRITE_ROLES).

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

## Backlog / Remaining
- P1: Adapt data model to user's real Excel report format (awaiting file upload).
- P2: Brute-force login lockout, password reset UI, per-plant filter, PDF/Excel export, split server.py into routers.

## Next Tasks
- Incorporate uploaded Excel structure & formulas when provided.
