#!/bin/sh
# Resumo do widget de boas-vindas: bateria, espaço livre no / e tempo ligado (JSON).

bat=$(cat /sys/class/power_supply/BAT*/capacity 2>/dev/null | head -1)
disco=$(df -h --output=avail / | tail -1 | tr -d ' ')
seg=$(cut -d. -f1 /proc/uptime)
h=$((seg / 3600))
m=$((seg % 3600 / 60))
if [ "$h" -gt 0 ]; then ligado="${h} h ${m} min"; else ligado="${m} min"; fi

printf '{"bateria":"%s","disco":"%s","ligado":"%s"}\n' "${bat:-?}" "$disco" "$ligado"
