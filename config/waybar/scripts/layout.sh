#!/bin/sh
# Mostra o layout de teclado ativo (US ou BR) e atualiza a cada troca.

{
    swaymsg -rt get_inputs \
        | jq -r '[.[] | select(.type == "keyboard")][0].xkb_active_layout_name'
    swaymsg -mrt subscribe '["input"]' \
        | jq -r --unbuffered 'select(.change == "xkb_layout") | .input
            | select(.type == "keyboard") | .xkb_active_layout_name'
} | jq -cR --unbuffered '
    if test("Portuguese") then {text: "BR", class: "br", tooltip: .}
    else {text: "US", class: "us", tooltip: .} end'
