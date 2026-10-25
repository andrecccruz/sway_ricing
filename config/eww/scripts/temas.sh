#!/bin/sh
# Seletor de temas (janela "temas" do eww). Enquanto aberto, o sway fica no
# modo "temas" para o Esc fechar.

TEMA=~/.config/temas/tema

case "$1" in
    abrir)
        # Fecha o painel da island de onde o botão pode ter sido clicado.
        eww close ilha-painel 2>/dev/null
        eww update aberta=false
        eww update temas="$($TEMA lista)"
        eww open temas
        swaymsg -q mode temas
        ;;
    fechar)
        eww close temas
        swaymsg -q mode default
        ;;
    aplicar)
        $TEMA "$2"
        # O tema recarrega o eww, o que zera as variáveis: atualiza a lista de novo.
        eww update temas="$($TEMA lista)"
        ;;
esac
