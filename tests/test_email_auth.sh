#!/usr/bin/env bash
# test_email_auth.sh — Pruebas de verificación de correo y recuperación de contraseña
# Requiere que el servidor esté corriendo con TEST_MODE=true
# Uso: TEST_MODE=true python main.py   →   bash tests/test_email_auth.sh [BASE_URL]

set -euo pipefail

BASE="${1:-http://localhost:8000}"
PASS=0
FAIL=0
ADMIN_TOKEN=""
TEST_USER="ci_email_$$"
TEST_EMAIL="ci_email_$$@test.local"
NEW_EMAIL="ci_email_new_$$@test.local"
TEST_UID=""
VERIFY_TOKEN=""
TEMP_PASSWORD=""
USER_TOKEN=""
RESET_TOKEN=""

# ── Colores ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

pass() { echo -e "  ${GREEN}✓${NC}  $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}✗${NC}  $1"; echo -e "     ${RED}esperado:${NC} $2  ${RED}obtenido:${NC} $3"; FAIL=$((FAIL + 1)); }
section() { echo -e "\n${CYAN}${BOLD}▸ $1${NC}"; }

if ! curl -s --max-time 3 "$BASE/docs" > /dev/null 2>&1; then
  echo -e "${RED}ERROR: El servidor no responde en $BASE${NC}"
  echo "Ejecuta:  TEST_MODE=true python main.py"
  exit 1
fi

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  Pruebas de Email Auth — MUA Biodiversidad${NC}"
echo -e "${BOLD}  $BASE${NC}"
echo -e "${BOLD}  (requiere TEST_MODE=true en el servidor)${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# ── BLOQUE 1: Login admin ──────────────────────────────────────────────────────
section "1. Login admin"

RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/login" \
  -d "username=admin&password=changeme123" \
  -H "Content-Type: application/x-www-form-urlencoded")
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)

if [ "$CODE" = "200" ]; then
  ADMIN_TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
  [ -n "$ADMIN_TOKEN" ] \
    && pass "Login admin → 200, token recibido" \
    || fail "Token admin vacío" "access_token presente" "$BODY"
else
  fail "Login admin" "200" "$CODE — $BODY"
  echo "¿Está corriendo el servidor con TEST_MODE=true?"
  exit 1
fi

# ── BLOQUE 2: Creación de usuario con email ────────────────────────────────────
section "2. Creación de usuario (email + contraseña generada)"

# 2.1 Crear usuario → debe recibir verify_token y temp_password en TEST_MODE
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$TEST_USER\",\"email\":\"$TEST_EMAIL\",\"role\":\"user\"}")
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)

if [ "$CODE" = "201" ]; then
  TEST_UID=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
  VERIFY_TOKEN=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('verify_token',''))" 2>/dev/null)
  TEMP_PASSWORD=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('temp_password',''))" 2>/dev/null)
  if [ -n "$VERIFY_TOKEN" ] && [ -n "$TEMP_PASSWORD" ]; then
    pass "Crear usuario → 201, verify_token y temp_password presentes (TEST_MODE)"
  else
    fail "Crear usuario: tokens faltantes" "verify_token + temp_password" "$BODY"
    # Sin TEST_MODE los bloques siguientes fallarán en cascada — abortar limpiamente
    [ -n "${TEST_UID:-}" ] && curl -s -o /dev/null -X DELETE \
      -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE/auth/users/$TEST_UID" || true
    echo ""
    echo -e "${RED}${BOLD}  ✗  ABORTANDO: reinicia el servidor con TEST_MODE=true${NC}"
    echo -e "     Ejemplo:  ${BOLD}TEST_MODE=true python main.py${NC}"
    echo ""
    FAIL=$((FAIL + 1))
    TOTAL=$((PASS + FAIL))
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${RED}${BOLD}FALLOS: $FAIL${NC}  (pasadas: ${GREEN}$PASS${NC}, total: $TOTAL)"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 1
  fi
else
  fail "Crear usuario" "201" "$CODE — $BODY"
fi

# 2.2 Email duplicado → 409
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"otro_user_$$\",\"email\":\"$TEST_EMAIL\",\"role\":\"user\"}")
[ "$CODE" = "409" ] \
  && pass "Email duplicado → 409 Conflict" \
  || fail "Email duplicado" "409" "$CODE"

# 2.3 Email inválido → 422
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"valido123","email":"no-es-un-email","role":"user"}')
[ "$CODE" = "422" ] \
  && pass "Email inválido → 422 Unprocessable Entity" \
  || fail "Email inválido" "422" "$CODE"

# 2.4 Username inválido (espacio) → 422
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"usuario invalido","email":"ok@ok.com","role":"user"}')
[ "$CODE" = "422" ] \
  && pass "Username inválido → 422 Unprocessable Entity" \
  || fail "Username inválido" "422" "$CODE"

# ── BLOQUE 3: Login bloqueado antes de verificar ───────────────────────────────
section "3. Cuenta no verificada → login bloqueado"

# Usa la contraseña temporal real (disponible gracias a TEST_MODE)
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/login" \
  -d "username=${TEST_USER}&password=${TEMP_PASSWORD}" \
  -H "Content-Type: application/x-www-form-urlencoded")
[ "$CODE" = "400" ] \
  && pass "Login antes de verificar → 400 (cuenta pendiente)" \
  || fail "Login antes de verificar" "400" "$CODE"

# ── BLOQUE 4: Verificación de correo ──────────────────────────────────────────
section "4. Verificación de correo electrónico"

# 4.1 Token inválido → HTML con error
RESP=$(curl -s -w "\n%{http_code}" "$BASE/auth/verify-email?token=token_inventado_invalido")
CODE=$(echo "$RESP" | tail -1)
[ "$CODE" = "200" ] \
  && pass "verify-email token inválido → 200 (HTML de error)" \
  || fail "verify-email token inválido" "200" "$CODE"

# 4.2 Token válido → activa la cuenta
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/auth/verify-email?token=$VERIFY_TOKEN")
[ "$CODE" = "200" ] \
  && pass "verify-email token válido → 200 (HTML de éxito)" \
  || fail "verify-email token válido" "200" "$CODE"

# 4.3 Reusar el mismo token → error (ya usado)
RESP=$(curl -s "$BASE/auth/verify-email?token=$VERIFY_TOKEN")
echo "$RESP" | grep -qi "ya verificado\|ya fue utilizado\|Ya verificado" \
  && pass "Reusar token → HTML indica 'ya utilizado'" \
  || fail "Reusar token" "mensaje 'ya utilizado'" "$(echo "$RESP" | head -c 200)"

# ── BLOQUE 5: Login después de verificar ──────────────────────────────────────
section "5. Login con contraseña temporal (post-verificación)"

RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/login" \
  -d "username=$TEST_USER&password=$TEMP_PASSWORD" \
  -H "Content-Type: application/x-www-form-urlencoded")
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)

if [ "$CODE" = "200" ]; then
  USER_TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
  [ -n "$USER_TOKEN" ] \
    && pass "Login post-verificación → 200, token recibido" \
    || fail "Token vacío post-verificación" "access_token" "$BODY"
else
  fail "Login post-verificación" "200" "$CODE — $BODY"
fi

# ── BLOQUE 6: Recuperación de contraseña ──────────────────────────────────────
section "6. Flujo de recuperación de contraseña"

# 6.1 forgot-password con email registrado → devuelve reset_token en TEST_MODE
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/forgot-password" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEST_EMAIL\"}")
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)

if [ "$CODE" = "200" ]; then
  RESET_TOKEN=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('reset_token',''))" 2>/dev/null)
  if [ -n "$RESET_TOKEN" ]; then
    pass "forgot-password → 200, reset_token presente (TEST_MODE)"
  else
    fail "Reset token faltante" "reset_token en respuesta" "$BODY"
    # La cuenta puede no estar activa (is_active=False) si algo falló antes
    echo -e "     ${RED}Nota: forgot-password solo genera token si is_active=True${NC}"
    RESET_TOKEN="token_invalido_para_forzar_fallo"
  fi
else
  fail "forgot-password" "200" "$CODE — $BODY"
fi

# 6.2 forgot-password con email inexistente → 200 (no revela info)
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/forgot-password" \
  -H "Content-Type: application/json" \
  -d '{"email":"noexiste@noexiste.com"}')
[ "$CODE" = "200" ] \
  && pass "forgot-password email inexistente → 200 (sin revelar info)" \
  || fail "forgot-password email inexistente" "200" "$CODE"

# 6.3 reset-password token inválido → 400
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/reset-password" \
  -H "Content-Type: application/json" \
  -d '{"token":"token_inventado_invalido","new_password":"nueva1234"}')
[ "$CODE" = "400" ] \
  && pass "reset-password token inválido → 400" \
  || fail "reset-password token inválido" "400" "$CODE"

# 6.4 reset-password contraseña corta → 422
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/reset-password" \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$RESET_TOKEN\",\"new_password\":\"corta\"}")
[ "$CODE" = "422" ] \
  && pass "reset-password contraseña < 8 → 422" \
  || fail "reset-password contraseña corta" "422" "$CODE"

# 6.5 reset-password correcto → 200
NEW_PASS="nueva_pass_ci_$$_123"
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/reset-password" \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$RESET_TOKEN\",\"new_password\":\"$NEW_PASS\"}")
CODE=$(echo "$RESP" | tail -1)
[ "$CODE" = "200" ] \
  && pass "reset-password correcto → 200" \
  || fail "reset-password correcto" "200" "$CODE — $(echo "$RESP" | head -n -1)"

# 6.6 Reusar reset token → 400
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/reset-password" \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$RESET_TOKEN\",\"new_password\":\"otra_pass_1234\"}")
[ "$CODE" = "400" ] \
  && pass "Reusar reset token → 400 (ya utilizado)" \
  || fail "Reusar reset token" "400" "$CODE"

# 6.7 Login con contraseña nueva → 200
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/login" \
  -d "username=$TEST_USER&password=$NEW_PASS" \
  -H "Content-Type: application/x-www-form-urlencoded")
[ "$CODE" = "200" ] \
  && pass "Login con contraseña restablecida → 200" \
  || fail "Login con contraseña restablecida" "200" "$CODE"

# 6.8 Login con contraseña anterior (temporal) → 401
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/login" \
  -d "username=$TEST_USER&password=$TEMP_PASSWORD" \
  -H "Content-Type: application/x-www-form-urlencoded")
[ "$CODE" = "401" ] \
  && pass "Login con contraseña temporal tras reset → 401" \
  || fail "Contraseña temporal debería estar inválida" "401" "$CODE"

# ── BLOQUE 7: Limpieza ─────────────────────────────────────────────────────────
section "7. Limpieza"

if [ -n "${TEST_UID:-}" ]; then
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    "$BASE/auth/users/$TEST_UID")
  [ "$CODE" = "204" ] \
    && pass "Eliminar usuario de prueba → 204" \
    || fail "Eliminar usuario de prueba" "204" "$CODE"
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
