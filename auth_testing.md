# Auth Testing — Control Data Stock & Production

## Credentials
- Admin: ariyantyoni@gmail.com / admin123 (role: admin)
- Demo: manager@cds.co.id / password123 (management), ppic@cds.co.id / password123 (production_planning),
  pc@cds.co.id / password123 (production_control), smt@cds.co.id / password123 (smt), assy@cds.co.id / password123 (assembly)

## Auth flow
- Login returns { token, user }. Frontend stores token in localStorage as "cds_token" and sends Authorization: Bearer <token>. Cookie also set.
- get_current_user reads cookie first, falls back to Bearer header.

## API checks
```
API=https://inventory-ops-pro-3.preview.emergentagent.com
TOKEN=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" -d '{"email":"ariyantyoni@gmail.com","password":"admin123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s "$API/api/auth/me" -H "Authorization: Bearer $TOKEN"
curl -s "$API/api/dashboard/summary" -H "Authorization: Bearer $TOKEN"
```

## Role permission notes (403 expected when role lacks write access)
- assembly can write lamp_production but NOT smt_production
- production_planning can write smt_stock, production_needs, variance but NOT smt_production/lamp_production
- only admin can access /api/users and /api/auth/register
