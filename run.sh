#!/usr/bin/env bash
# One command for demo day: fresh demo data for both restaurants, then the app.
set -e
cd "$(dirname "$0")"
[ -f .env ] && source .env
PY=$(command -v python3 || command -v python)
$PY -m scripts.seed_demo --profile sushi  ${LOBSTA_TODAY:+--today $LOBSTA_TODAY}
$PY -m scripts.seed_demo --profile hotpot ${LOBSTA_TODAY:+--today $LOBSTA_TODAY}
echo
echo "Phone page:     http://$(hostname -I 2>/dev/null | awk '{print $1}'):8080/"
echo "Projector page: http://localhost:8080/sheet"
exec $PY -m uvicorn app.server:app --host 0.0.0.0 --port 8080
