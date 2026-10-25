# Créditos dos wallpapers

| Arquivo | Origem | Licença |
|---|---|---|
| `carina-webb.jpg` | "Cosmic Cliffs" na Nebulosa de Carina, telescópio James Webb. Crédito: **NASA, ESA, CSA e STScI** ([esawebb.org/images/weic2205a](https://esawebb.org/images/weic2205a/)). Reduzida para 3840×2160 e escurecida em 20%. | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `buraconegro.png`, `anel.png`, `neon.png`, `backrooms.png` | Gerados do zero por `config/temas/gerar_wallpapers.py` (Pillow + numpy), sem imagens de terceiros. | MIT, como o resto do repositório |

Para regenerar os wallpapers gerados (leva cerca de 1 minuto e meio):

```sh
python3 ~/.config/temas/gerar_wallpapers.py              # todos
python3 ~/.config/temas/gerar_wallpapers.py neon anel    # só alguns
```
