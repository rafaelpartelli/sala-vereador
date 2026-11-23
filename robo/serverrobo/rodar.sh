#!/usr/bin/env bash
# Roda a coleta dos municípios e envia os dados ao GitHub (a Hostinger publica pelo webhook).
# Uso: ./rodar.sh            (todos os municípios)
#      ./rodar.sh colatina,linhares   (só alguns, sem acento)
set -euo pipefail
cd "$(dirname "$0")/../.."
export TZ=America/Sao_Paulo
git pull --rebase --autostash origin main
python3 robo/coletar_municipios.py "${1:-}"
git add dados
if git diff --cached --quiet; then echo "Sem mudanças."; exit 0; fi
git commit -q -m "dados: municípios $(date '+%d/%m/%Y %H:%M') (serverrobo)"
for i in 1 2 3; do
  if git pull --rebase origin main && git push origin main; then exit 0; fi
  sleep 10
done
exit 1
