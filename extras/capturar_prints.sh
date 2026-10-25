#!/usr/bin/env bash
# Refaz os prints do README em 1920x1080: passa por todos os temas num
# workspace vazio, tira um print de cada e monta screenshots/temas.png.
# Mexe na tela por ~1 minuto; no fim volta ao tema que estava em uso.
set -euo pipefail

cd "$(dirname "$0")/.."
SAIDA=screenshots
TEMA=~/.config/temas/tema
antes=$($TEMA atual)
ordem=(espacial buraconegro halo neon backrooms mono nord rosepine claro)

swaymsg -q workspace prints-sway-ricing
for t in "${ordem[@]}"; do
    $TEMA "$t"
    sleep 3
    grim -s 1 "$SAIDA/tema-$t.png"
done

$TEMA espacial
sleep 2
~/.config/eww/scripts/temas.sh abrir;  sleep 2; grim -s 1 "$SAIDA/seletor.png"; ~/.config/eww/scripts/temas.sh fechar
~/.config/eww/scripts/energia.sh abrir; sleep 2; grim -s 1 "$SAIDA/energia.png"; ~/.config/eww/scripts/energia.sh fechar

arquivos=()
for t in "${ordem[@]}"; do arquivos+=("$SAIDA/tema-$t.png"); done
magick montage "${arquivos[@]}" -resize 640x360 -tile 3x -geometry +6+6 \
    -background '#0b0d1f' -define png:color-type=2 "$SAIDA/temas.png"

swaymsg -q workspace back_and_forth
$TEMA "$antes"
echo "Prints atualizados em $SAIDA/"
