#!/usr/bin/env bash
# Commite data/ (relevés append-only) et pousse sur main, en reprenant les commits arrivés entre-temps.
set -euo pipefail
message="${1:-Données}"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add data
if git diff --cached --quiet; then
  echo "Aucune donnée nouvelle."
  exit 0
fi
git commit -q -m "$message"
for essai in 1 2 3 4 5; do
  if git pull -q --rebase origin main && git push -q origin HEAD:main; then
    echo "Données publiées."
    exit 0
  fi
  sleep $((essai * 5))
done
echo "::error::Impossible de pousser les données après 5 essais."
exit 1
