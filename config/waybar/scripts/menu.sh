#!/bin/bash
# Menus rápidos da waybar usando wofi.
# Uso: menu.sh [principal|wifi|bluetooth|energia]

# Clicar de novo com o menu aberto fecha o menu.
pkill -x wofi && exit 0

escolher() {   # escolher "Título" < opções; falha se o menu fechar sem escolha
    local r
    r=$(wofi --dmenu \
        --cache-file=/dev/null --insensitive --width=440 --height=380 \
        --prompt="$1") && [ -n "$r" ] && printf '%s\n' "$r"
}

avisar() {
    command -v notify-send >/dev/null && notify-send -a Menu "$@"
}

menu_principal() {
    case "$(printf '%s\n' \
        $'  Wi-Fi' \
        $'  Bluetooth' \
        $'  Som' \
        $'  Energia' | escolher "Menu")" in
        *Wi-Fi)     menu_wifi ;;
        *Bluetooth) menu_bluetooth ;;
        *Som)       pavucontrol & ;;
        *Energia)   ~/.config/eww/scripts/energia.sh abrir ;;
    esac
}

menu_wifi() {
    local ligado linhas=() escolha
    declare -A ssid_de visto
    ligado=$(nmcli radio wifi)

    if [ "$ligado" = enabled ]; then
        linhas+=($'  Desligar Wi-Fi')
        # SSID por último: tudo depois do 3º ":" é o nome, mesmo se tiver ":".
        while IFS=: read -r uso sinal seg ssid; do
            [ -z "$ssid" ] && continue
            [ -n "${visto[$ssid]}" ] && continue   # mesma rede em outra frequência
            local marca="   " cadeado=""
            [ "$uso" = "*" ] && marca=$'  '
            [ -n "$seg" ] && [ "$seg" != "--" ] && cadeado=$'  '
            local linha="${marca}${ssid}   ${sinal}%${cadeado}"
            visto[$ssid]=1
            ssid_de[$linha]=$ssid
            linhas+=("$linha")
        # Usa a última busca (instantâneo); uma busca nova leva ~10 s, então
        # roda em segundo plano e fica pronta para a próxima vez.
        done < <(nmcli --escape no -t -f IN-USE,SIGNAL,SECURITY,SSID dev wifi list --rescan no)
        nmcli dev wifi rescan >/dev/null 2>&1 &
        linhas+=($'  Procurar redes' $'  Configurações avançadas')
    else
        linhas+=($'  Ligar Wi-Fi')
    fi

    escolha=$(printf '%s\n' "${linhas[@]}" | escolher "Wi-Fi") || return
    case "$escolha" in
        *"Desligar Wi-Fi") nmcli radio wifi off ;;
        *"Ligar Wi-Fi")    nmcli radio wifi on ;;
        *"Configurações avançadas") alacritty -e nmtui & ;;
        *"Procurar redes")
            avisar "Wi-Fi" "Procurando redes…"
            nmcli dev wifi list --rescan yes >/dev/null
            menu_wifi ;;
        *)
            local ssid=${ssid_de[$escolha]}
            [ -z "$ssid" ] && return
            if [[ "$escolha" == $''* ]]; then
                nmcli con down id "$ssid" && avisar "Wi-Fi" "Desconectado de $ssid"
            elif nmcli -t -f NAME con show | grep -Fxq -- "$ssid"; then
                nmcli con up id "$ssid" >/dev/null \
                    && avisar "Wi-Fi" "Conectado a $ssid" \
                    || avisar -u critical "Wi-Fi" "Falha ao conectar em $ssid"
            else
                local senha=""
                if [[ "$escolha" == *$'' ]]; then
                    senha=$(wofi --dmenu --password \
                        --cache-file=/dev/null \
                        --width=440 --height=60 --prompt="Senha de $ssid")
                    [ -n "$senha" ] || return
                fi
                if nmcli dev wifi connect "$ssid" ${senha:+password "$senha"} >/dev/null; then
                    avisar "Wi-Fi" "Conectado a $ssid"
                else
                    avisar -u critical "Wi-Fi" "Falha ao conectar em $ssid"
                fi
            fi
            ;;
    esac
}

menu_bluetooth() {
    local linhas=() escolha
    declare -A mac_de

    if bluetoothctl show | grep -q 'Powered: yes'; then
        linhas+=($'  Desligar Bluetooth')
        while read -r _ mac nome; do
            local marca="   "
            bluetoothctl info "$mac" | grep -q 'Connected: yes' && marca=$'  '
            local linha="${marca}${nome}"
            mac_de[$linha]=$mac
            linhas+=("$linha")
        done < <(bluetoothctl devices Paired)
        linhas+=($'  Parear novo dispositivo')
    else
        linhas+=($'  Ligar Bluetooth')
    fi

    escolha=$(printf '%s\n' "${linhas[@]}" | escolher "Bluetooth") || return
    case "$escolha" in
        *"Desligar Bluetooth") bluetoothctl power off >/dev/null ;;
        *"Ligar Bluetooth")    bluetoothctl power on >/dev/null ;;
        *"Parear novo dispositivo")
            alacritty -e sh -c 'echo "Comandos: scan on, pair <MAC>, trust <MAC>, connect <MAC>, quit"; bluetoothctl' & ;;
        *)
            local mac=${mac_de[$escolha]} nome=${escolha:3}
            [ -z "$mac" ] && return
            if [[ "$escolha" == $''* ]]; then
                bluetoothctl disconnect "$mac" >/dev/null && avisar "Bluetooth" "$nome desconectado"
            else
                avisar "Bluetooth" "Conectando a $nome…"
                bluetoothctl connect "$mac" >/dev/null \
                    && avisar "Bluetooth" "$nome conectado" \
                    || avisar -u critical "Bluetooth" "Falha ao conectar $nome"
            fi
            ;;
    esac
    pkill -SIGRTMIN+8 waybar
}

menu_energia() {
    case "$(printf '%s\n' \
        $'  Bloquear' \
        $'  Suspender' \
        $'  Sair do sway' \
        $'  Reiniciar' \
        $'  Desligar' | escolher "Energia")" in
        *Bloquear)  swaylock --config /etc/swaylock/openSUSEway.conf ;;
        *Suspender) systemctl suspend ;;
        *Sair*)     swaymsg exit ;;
        *Reiniciar) systemctl reboot ;;
        *Desligar)  systemctl poweroff ;;
    esac
}

case "${1:-principal}" in
    wifi)      menu_wifi ;;
    bluetooth) menu_bluetooth ;;
    energia)   exec ~/.config/eww/scripts/energia.sh abrir ;;
    *)         menu_principal ;;
esac
