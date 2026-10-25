#!/bin/sh
# Tela de energia em tela cheia (janela "energia" do eww).
# Enquanto aberta, o sway fica no modo "energia": Esc fecha e as letras
# B/S/E/R/D escolhem a ação (definido em ~/.config/sway/config.d/tema.conf).

bloquear() {
    # Usa o tema do openSUSEway se existir; senão, tela preta simples.
    if [ -f /etc/swaylock/openSUSEway.conf ]; then
        swaylock --config /etc/swaylock/openSUSEway.conf
    else
        swaylock -f -c 000000
    fi
}

fechar() {
    eww close energia
    swaymsg -q mode default
}

case "$1" in
    abrir)
        # Fecha o painel da island de onde o botão pode ter sido clicado.
        eww close ilha-painel 2>/dev/null
        eww update aberta=false
        eww open energia
        swaymsg -q mode energia
        ;;
    fechar)    fechar ;;
    bloquear)  fechar; bloquear ;;
    suspender) fechar; systemctl suspend ;;
    sair)      fechar; swaymsg exit ;;
    reiniciar) fechar; systemctl reboot ;;
    desligar)  fechar; systemctl poweroff ;;
esac
