#!/usr/bin/env bash
# Atualiza o painel online no servidor para a versão mais recente do GitHub.
# Rodar como o usuário "deploy", dentro de /opt/grupo-de-ofertas:   ./deploy/atualizar.sh
set -euo pipefail

cd /opt/grupo-de-ofertas

echo "==> Baixando a versão nova"
git pull --ff-only

echo "==> Atualizando dependências"
venv/bin/pip install --quiet -r requirements-painel.txt

echo "==> Reiniciando o painel"
sudo systemctl restart painel
sleep 2

echo "==> Conferindo"
curl --fail --silent --show-error http://127.0.0.1:8000/api/saude && echo
sudo systemctl --no-pager --lines=0 status painel | head -n 4
echo "Pronto."
