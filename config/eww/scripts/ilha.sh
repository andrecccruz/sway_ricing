#!/bin/sh
# Abre/fecha o painel da island com animação.
# O painel é uma janela separada porque janelas do eww não encolhem no Wayland.

case "$1" in
    abrir)
        eww update aberta=false
        eww active-windows | grep -q '^ilha-painel' || eww open ilha-painel
        eww update aberta=true
        ;;
    fechar)
        eww update aberta=false
        sleep 0.3
        # Se o mouse voltou durante a animação, o painel continua aberto.
        [ "$(eww get aberta)" = false ] && eww close ilha-painel
        ;;
esac
