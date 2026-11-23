#!/usr/bin/env bash
# Instalação no serverrobo (uma vez). Rode:  bash instalar.sh
set -euo pipefail
DIR="$HOME/robo_vereador"
CHAVE="$HOME/.ssh/sala_vereador"
REPO="git@github.com:rafaelpartelli/sala-vereador.git"
command -v git >/dev/null && command -v python3 >/dev/null || { echo "Instale git e python3 antes."; exit 1; }
mkdir -p "$HOME/.ssh"; chmod 700 "$HOME/.ssh"
if [ ! -f "$CHAVE" ]; then
  ssh-keygen -t ed25519 -N "" -C "serverrobo sala-vereador" -f "$CHAVE" >/dev/null
fi
echo
echo "1) No GitHub, abra: https://github.com/rafaelpartelli/sala-vereador/settings/keys/new"
echo "   Title: serverrobo | marque 'Allow write access' | cole a chave abaixo:"
echo
cat "$CHAVE.pub"
echo
read -r -p "Depois de salvar a chave no GitHub, tecle Enter para continuar... " _
if [ ! -d "$DIR/.git" ]; then
  GIT_SSH_COMMAND="ssh -i $CHAVE -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" git clone "$REPO" "$DIR"
fi
cd "$DIR"
git config core.sshCommand "ssh -i $CHAVE -o IdentitiesOnly=yes"
git config user.name "robo-serverrobo"
git config user.email "robo-serverrobo@users.noreply.github.com"
chmod +x robo/serverrobo/rodar.sh
LINHA="0 20 * * * cd $DIR && ./robo/serverrobo/rodar.sh >> $DIR/robo.log 2>&1"
( crontab -l 2>/dev/null | grep -v "robo/serverrobo/rodar.sh" | grep -v '^CRON_TZ='; echo "CRON_TZ=America/Sao_Paulo"; echo "$LINHA" ) | crontab -
echo
echo "Pronto. Agendado todos os dias às 20h (Brasília). Para testar agora com 3 municípios:"
echo "  cd $DIR && ./robo/serverrobo/rodar.sh colatina,linhares,iuna"
