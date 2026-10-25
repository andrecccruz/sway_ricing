#!/bin/bash
# Emite uma linha JSON com o estado do player (playerctl) sempre que algo muda.
# A capa do álbum é baixada para o cache, porque o eww só mostra arquivos locais.

CAPAS="$HOME/.cache/eww/capas"
mkdir -p "$CAPAS"

vazio='{"status":"","title":"","artist":"","art":"","length":0}'
echo "$vazio"

# Separador \x1f: com tab, campos vazios seguidos se juntariam no read.
playerctl --follow metadata --format \
    $'{{status}}\x1f{{title}}\x1f{{artist}}\x1f{{mpris:artUrl}}\x1f{{mpris:length}}' 2>/dev/null |
while IFS=$'\x1f' read -r status title artist url length; do
    if [ -z "$status" ]; then
        echo "$vazio"
        continue
    fi

    art=""
    case "$url" in
        file://*) art="${url#file://}" ;;
        http*)
            f="$CAPAS/$(printf '%s' "$url" | md5sum | cut -c1-16).jpg"
            [ -s "$f" ] || curl -sfL --max-time 5 -o "$f" "$url"
            [ -s "$f" ] && art="$f"
            ;;
    esac

    jq -nc --arg s "$status" --arg t "$title" --arg a "$artist" \
        --arg art "$art" --arg l "${length:-0}" \
        '{status: $s, title: $t, artist: $a, art: $art,
          length: (($l | tonumber? // 0) / 1000000 | floor)}'
done
