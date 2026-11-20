#!/usr/bin/env sh
# Executa o uv. Na máquina local usa o uv instalado; no runner do CI
# compartilhado, que só tem Node, cai para `pipx run` com a versão fixada
# abaixo. Sem nenhum dos dois, falha com uma mensagem em vez de pular os
# checks do pipeline.
set -e

UV_VERSION="0.11.7"

if command -v uv >/dev/null 2>&1; then
  exec uv "$@"
fi

if command -v pipx >/dev/null 2>&1; then
  exec pipx run --spec "uv==${UV_VERSION}" uv "$@"
fi

echo "sim-poa: uv não encontrado e pipx indisponível." >&2
echo "Instale o uv (https://docs.astral.sh/uv/) e tente de novo." >&2
exit 1
