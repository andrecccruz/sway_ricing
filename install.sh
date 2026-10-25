#!/usr/bin/env bash
# Instala o sway_ricing: copia as configs para ~/.config (fazendo backup do que
# já existir), copia os wallpapers e aplica um tema.
#
# Uso: ./install.sh [tema]      (padrão: espacial; veja config/temas/*.toml)
set -euo pipefail

cd "$(dirname "$0")"
TEMA="${1:-espacial}"
PASTAS=(sway waybar wofi eww alacritty temas)
BACKUP="$HOME/.config/sway_ricing-backup-$(date +%Y%m%d-%H%M%S)"

if [ ! -f "config/temas/$TEMA.toml" ]; then
    echo "Tema '$TEMA' não existe. Opções: $(ls config/temas/*.toml | xargs -n1 basename | sed 's/\.toml$//' | tr '\n' ' ')" >&2
    exit 1
fi

for p in "${PASTAS[@]}"; do
    if [ -e "$HOME/.config/$p" ]; then
        mkdir -p "$BACKUP"
        cp -a "$HOME/.config/$p" "$BACKUP/"
    fi
    mkdir -p "$HOME/.config/$p"
    cp -a "config/$p/." "$HOME/.config/$p/"
done
[ -d "$BACKUP" ] && echo "Backup das configs anteriores: $BACKUP"

mkdir -p "$HOME/.local/share/backgrounds"
cp -a wallpapers/*.png wallpapers/*.jpg "$HOME/.local/share/backgrounds/"

chmod +x "$HOME"/.config/{waybar/scripts,eww/scripts}/*.sh \
         "$HOME/.config/temas/tema" "$HOME/.config/temas/gerar_wallpapers.py"

# Gera cores.conf (sway), cores.toml (alacritty) e os blocos de cor dos estilos.
"$HOME/.config/temas/tema" "$TEMA"

echo "Pronto. Se o sway estiver aberto, recarregue com Win+Shift+C."
