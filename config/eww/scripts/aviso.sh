#!/bin/sh
# Aviso rápido na island: aplica a ação e mostra o valor por ~1,5 s no lugar da hora.
# Uso: aviso.sh volume-mais|volume-menos|mudo|brilho-mais|brilho-menos|teclado

ICONE_VOL=$(printf '\357\200\250')    # f028 volume-high
ICONE_MUDO=$(printf '\357\232\251')   # f6a9 volume-xmark
ICONE_SOL=$(printf '\357\206\205')    # f185 sun
ICONE_TECLADO=$(printf '\357\204\234') # f11c keyboard

volume() {
    if [ "$(pamixer --get-mute)" = true ]; then
        mostrar "$ICONE_MUDO" 0 "mudo"
    else
        v=$(pamixer --get-volume)
        mostrar "$ICONE_VOL" "$v" "$v%"
    fi
}

brilho() {
    b=$(brightnessctl -m | cut -d, -f4 | tr -d %)
    mostrar "$ICONE_SOL" "$b" "$b%"
}

mostrar() {   # mostrar ícone valor(0-100, ou -1 sem barra) texto
    eww update aviso_icone="$1" aviso_valor="$2" aviso_texto="$3" aviso=true
    # Cada aviso grava um id; só o último esconde a island ao final do tempo.
    id=$$
    echo "$id" > "${XDG_RUNTIME_DIR:-/tmp}/eww-aviso"
    sleep 1.5
    [ "$(cat "${XDG_RUNTIME_DIR:-/tmp}/eww-aviso" 2>/dev/null)" = "$id" ] && eww update aviso=false
}

case "$1" in
    volume-mais)  pamixer -u -i 5; volume ;;
    volume-menos) pamixer -u -d 5; volume ;;
    mudo)         pamixer -t; volume ;;
    brilho-mais)  brightnessctl -q set +5%; brilho ;;
    brilho-menos) brightnessctl -q set 5%-; brilho ;;
    teclado)
        swaymsg -q input type:keyboard xkb_switch_layout next
        nome=$(swaymsg -rt get_inputs | jq -r '[.[] | select(.type == "keyboard")][0].xkb_active_layout_name')
        case "$nome" in *Portuguese*) t=BR ;; *) t=US ;; esac
        mostrar "$ICONE_TECLADO" -1 "$t"
        ;;
esac
