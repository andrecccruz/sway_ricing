#!/bin/sh
# Barrinhas de áudio para a waybar. Em silêncio imprime uma linha vazia
# (uma vez só), o que esconde o módulo.

command -v cava >/dev/null || exit 0

# Mata o cava junto quando a waybar reinicia o módulo.
trap 'kill 0' EXIT INT TERM

cava -p "$HOME/.config/waybar/cava.conf" | awk '
{
    gsub(/;/, "")
    if ($0 ~ /^0*$/) {
        if (!quieto) { print ""; fflush(); quieto = 1 }
        next
    }
    quieto = 0
    s = $0
    gsub(/0/, "▁", s); gsub(/1/, "▂", s); gsub(/2/, "▃", s); gsub(/3/, "▄", s)
    gsub(/4/, "▅", s); gsub(/5/, "▆", s); gsub(/6/, "▇", s); gsub(/7/, "█", s)
    print s
    fflush()
}'
