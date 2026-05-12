#!/usr/bin/env bash
# test_auth.sh — Pruebas del sistema de autenticación JWT
# Uso: bash tests/test_auth.sh [BASE_URL]
# Ejemplo: bash tests/test_auth.sh http://localhost:8000

set -euo pipefail

BASE="${1:-http://localhost:8000}"
PASS=0
FAIL=0
ADMIN_TOKEN=""
USER_TOKEN=""
TEST_USER="testuser_ci_$$"
TEST_PASS="testpass_ci_123"

# ── Colores ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}✓${NC}  $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}✗${NC}  $1"; echo -e "     ${RED}esperado:${NC} $2  ${RED}obtenido:${NC} $3"; FAIL=$((FAIL + 1)); }
section() { echo -e "\n${CYAN}${BOLD}▸ $1${NC}"; }

# ── Verificar que el servidor esté corriendo ───────────────────────────────────
if ! curl -s --max-time 3 "$BASE/docs" > /dev/null 2>&1; then
  echo -e "${RED}ERROR: El servidor no responde en $BASE${NC}"
  echo "Ejecuta primero:  python main.py"
  exit 1
fi

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  Pruebas de Autenticación — MUA Biodiversidad${NC}"
echo -e "${BOLD}  $BASE${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# ── BLOQUE 1: Login ────────────────────────────────────────────────────────────
section "1. Login"

# 1.1 Login con credenciales válidas de admin
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/login" \
  -d "username=admin&password=changeme123" \
  -H "Content-Type: application/x-www-form-urlencoded")
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)

if [ "$CODE" = "200" ]; then
  ADMIN_TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
  ROLE=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('role',''))" 2>/dev/null)
  if [ -n "$ADMIN_TOKEN" ] && [ "$ROLE" = "admin" ]; then
    pass "Login admin → 200, token recibido, role=admin"
  else
    fail "Login admin: token o rol faltante" "access_token + role=admin" "$BODY"
  fi
else
  fail "Login con credenciales válidas" "200" "$CODE"
fi

# 1.2 Login con contraseña incorrecta
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/login" \
  -d "username=admin&password=password_equivocada" \
  -H "Content-Type: application/x-www-form-urlencoded")
[ "$CODE" = "401" ] \
  && pass "Contraseña incorrecta → 401 Unauthorized" \
  || fail "Contraseña incorrecta" "401" "$CODE"

# 1.3 Login con usuario inexistente
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/login" \
  -d "username=noexiste&password=cualquiera" \
  -H "Content-Type: application/x-www-form-urlencoded")
[ "$CODE" = "401" ] \
  && pass "Usuario inexistente → 401 Unauthorized" \
  || fail "Usuario inexistente" "401" "$CODE"

# 1.4 Login sin cuerpo
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded")
[ "$CODE" = "422" ] \
  && pass "Login sin cuerpo → 422 Unprocessable Entity" \
  || fail "Login sin cuerpo" "422" "$CODE"

# ── BLOQUE 2: Protección de endpoints ─────────────────────────────────────────
section "2. Protección de endpoints (sin token)"

for ENDPOINT in "/occurrences/" "/taxa/resumen" "/stats/calidad" "/auth/me"; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE$ENDPOINT")
  [ "$CODE" = "401" ] \
    && pass "GET $ENDPOINT sin token → 401" \
    || fail "GET $ENDPOINT sin token" "401" "$CODE"
done

# Token inválido inventado
CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer token.falso.inventado" \
  "$BASE/occurrences/")
[ "$CODE" = "401" ] \
  && pass "Token malformado → 401" \
  || fail "Token malformado" "401" "$CODE"

# ── BLOQUE 3: Acceso con token de admin ───────────────────────────────────────
section "3. Acceso con token de admin"

# 3.1 GET /auth/me
RESP=$(curl -s -w "\n%{http_code}" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$BASE/auth/me")
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)
if [ "$CODE" = "200" ]; then
  UNAME=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('username',''))" 2>/dev/null)
  UROLE=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('role',''))" 2>/dev/null)
  [ "$UNAME" = "admin" ] && [ "$UROLE" = "admin" ] \
    && pass "GET /auth/me → 200, username=admin, role=admin" \
    || fail "/auth/me devuelve datos incorrectos" "username=admin role=admin" "$BODY"
else
  fail "GET /auth/me con token válido" "200" "$CODE"
fi

# 3.2 GET /occurrences/
CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$BASE/occurrences/")
[ "$CODE" = "200" ] \
  && pass "GET /occurrences/ con token admin → 200" \
  || fail "GET /occurrences/ con token admin" "200" "$CODE"

# 3.3 GET /auth/users (admin only)
CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$BASE/auth/users")
[ "$CODE" = "200" ] \
  && pass "GET /auth/users con token admin → 200" \
  || fail "GET /auth/users con token admin" "200" "$CODE"

# ── BLOQUE 4: Gestión de usuarios (admin) ─────────────────────────────────────
section "4. Gestión de usuarios"

# 4.1 Crear usuario normal
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$TEST_USER\",\"password\":\"$TEST_PASS\",\"role\":\"user\"}")
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)
if [ "$CODE" = "201" ]; then
  TEST_UID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
  pass "Crear usuario normal → 201, id=$TEST_UID"
else
  fail "Crear usuario normal" "201" "$CODE — $BODY"
fi

# 4.2 Crear usuario con username duplicado (contraseña válida para que llegue al check de duplicado)
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$TEST_USER\",\"password\":\"password_valida_123\",\"role\":\"user\"}")
[ "$CODE" = "409" ] \
  && pass "Crear usuario duplicado → 409 Conflict" \
  || fail "Crear usuario duplicado" "409" "$CODE"

# 4.3 Contraseña demasiado corta → 422
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"usuarionuevo","password":"abc","role":"user"}')
[ "$CODE" = "422" ] \
  && pass "Contraseña < 8 chars → 422 Unprocessable Entity" \
  || fail "Contraseña corta" "422" "$CODE"

# 4.4 Username inválido (contiene espacio) → 422
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"usuario invalido","password":"password123","role":"user"}')
[ "$CODE" = "422" ] \
  && pass "Username con espacio → 422 Unprocessable Entity" \
  || fail "Username inválido" "422" "$CODE"

# 4.5 Listar usuarios incluye el nuevo
RESP=$(curl -s \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$BASE/auth/users")
COUNT=$(echo "$RESP" | python3 -c "import sys,json; data=json.load(sys.stdin); print(len([u for u in data if u.get('username')=='$TEST_USER']))" 2>/dev/null)
[ "$COUNT" = "1" ] \
  && pass "Listar usuarios contiene al usuario recién creado" \
  || fail "Listar usuarios" "1 coincidencia" "$COUNT"

# ── BLOQUE 5: RBAC — acceso con token de usuario normal ───────────────────────
section "5. Control de acceso por rol (RBAC)"

# 5.1 Login como usuario normal
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/login" \
  -d "username=$TEST_USER&password=$TEST_PASS" \
  -H "Content-Type: application/x-www-form-urlencoded")
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)
if [ "$CODE" = "200" ]; then
  USER_TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
  UROLE=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('role',''))" 2>/dev/null)
  [ "$UROLE" = "user" ] \
    && pass "Login usuario normal → 200, role=user" \
    || fail "Login usuario normal: rol incorrecto" "user" "$UROLE"
else
  fail "Login usuario normal" "200" "$CODE"
fi

# 5.2 Usuario normal puede leer
CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $USER_TOKEN" \
  "$BASE/occurrences/")
[ "$CODE" = "200" ] \
  && pass "GET /occurrences/ con token user → 200 (lectura permitida)" \
  || fail "GET /occurrences/ con token user" "200" "$CODE"

# 5.3 Usuario normal NO puede listar usuarios del sistema
CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $USER_TOKEN" \
  "$BASE/auth/users")
[ "$CODE" = "403" ] \
  && pass "GET /auth/users con token user → 403 Forbidden" \
  || fail "GET /auth/users con token user" "403" "$CODE"

# 5.4 Usuario normal NO puede eliminar occurrences
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
  -H "Authorization: Bearer $USER_TOKEN" \
  "$BASE/occurrences/ID_INEXISTENTE_RBAC_TEST")
[ "$CODE" = "403" ] \
  && pass "DELETE /occurrences/ con token user → 403 Forbidden" \
  || fail "DELETE /occurrences/ con token user" "403" "$CODE"

# 5.5 Usuario normal NO puede cargar archivos ETL
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $USER_TOKEN" \
  "$BASE/etl/cargar-directorio")
[ "$CODE" = "403" ] \
  && pass "POST /etl/cargar-directorio con token user → 403 Forbidden" \
  || fail "POST /etl/cargar-directorio con token user" "403" "$CODE"

# 5.6 Admin NO puede eliminarse a sí mismo
if [ -n "$ADMIN_TOKEN" ]; then
  ME=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE/auth/me")
  ADMIN_ID=$(echo "$ME" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    "$BASE/auth/users/$ADMIN_ID")
  [ "$CODE" = "400" ] \
    && pass "Admin intenta eliminarse a sí mismo → 400 Bad Request" \
    || fail "Admin eliminarse a sí mismo" "400" "$CODE"
fi

# ── BLOQUE 6: Limpieza ─────────────────────────────────────────────────────────
section "6. Limpieza"

if [ -n "${TEST_UID:-}" ]; then
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    "$BASE/auth/users/$TEST_UID")
  [ "$CODE" = "204" ] \
    && pass "Eliminar usuario de prueba → 204 No Content" \
    || fail "Eliminar usuario de prueba" "204" "$CODE"

  # Verificar que ya no puede hacer login
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/login" \
    -d "username=$TEST_USER&password=$TEST_PASS" \
    -H "Content-Type: application/x-www-form-urlencoded")
  [ "$CODE" = "401" ] \
    && pass "Usuario eliminado ya no puede hacer login → 401" \
    || fail "Usuario eliminado aun puede hacer login" "401" "$CODE"
fi

# ── Resumen ────────────────────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL))
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ "$FAIL" = "0" ]; then
  echo -e "  ${GREEN}${BOLD}TODAS LAS PRUEBAS PASARON${NC}  $PASS/$TOTAL"
else
  echo -e "  ${RED}${BOLD}FALLOS: $FAIL${NC}  (pasadas: ${GREEN}$PASS${NC}, total: $TOTAL)"
fi
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

[ "$FAIL" = "0" ] && exit 0 || exit 1
