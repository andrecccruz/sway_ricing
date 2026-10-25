#!/usr/bin/env python3
"""Gera os wallpapers dos temas (4K) só com Pillow, sem imagens de terceiros.

Uso: gerar_wallpapers.py [buraconegro|anel|neon|backrooms ...] [--saida DIR]
Sem nomes, gera todos. Saída padrão: ~/.local/share/backgrounds
"""
import argparse
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H = 3840, 2160


# ---------- utilitários ----------

def gradiente(paradas, w=W, h=H):
    """Gradiente vertical. paradas = [(posição 0-1, (r, g, b)), ...]"""
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        for (p0, c0), (p1, c1) in zip(paradas, paradas[1:]):
            if p0 <= t <= p1:
                u = (t - p0) / (p1 - p0) if p1 > p0 else 0
                cor = tuple(int(c0[i] + (c1[i] - c0[i]) * u) for i in range(3))
                break
        d.line([(0, y), (w, y)], fill=cor)
    return img.convert("RGBA")


def _desfoque(a, sigma):
    """Desfoque gaussiano aproximado (3 passadas de caixa) em float, por eixo."""
    k = max(1, int(round(sigma)))
    for _ in range(3):
        for eixo in (0, 1):
            pad = [(k + 1, k) if e == eixo else (0, 0) for e in range(a.ndim)]
            c = np.cumsum(np.pad(a, pad, mode="edge"), axis=eixo)
            n = a.shape[eixo]
            fim = np.take(c, np.arange(2 * k + 1, 2 * k + 1 + n), axis=eixo)
            ini = np.take(c, np.arange(0, n), axis=eixo)
            a = (fim - ini) / (2 * k + 1)
    return a


def _para_imagem(rgb):
    """float 0-1 -> RGBA 8 bits com dithering (evita faixas em gradientes escuros)."""
    out = np.clip(rgb * 255 + np.random.uniform(-0.5, 0.5, rgb.shape), 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([out, np.full(out.shape[:2], 255, np.uint8)]), "RGBA")


def brilho(img, desenhar, raio, escala=4):
    """Desenha numa camada reduzida, desfoca em float e compõe por cima (glow sem banding)."""
    w, h = W // escala, H // escala
    c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    desenhar(ImageDraw.Draw(c), escala)
    a = np.asarray(c, dtype=np.float32) / 255.0
    pm = np.concatenate([a[..., :3] * a[..., 3:4], a[..., 3:4]], axis=2)   # pré-multiplicado
    pm = _desfoque(pm, raio / escala)
    up = np.stack([np.asarray(Image.fromarray(pm[..., i]).resize((W, H), Image.BILINEAR))
                   for i in range(4)], axis=2)
    base = np.asarray(img, dtype=np.float32)[..., :3] / 255.0
    return _para_imagem(base * (1 - up[..., 3:4]) + up[..., :3])


def camada(img, desenhar, desfoque=0):
    """Desenha em resolução total numa camada transparente e compõe."""
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    desenhar(ImageDraw.Draw(c))
    if desfoque:
        c = c.filter(ImageFilter.GaussianBlur(desfoque))
    return Image.alpha_composite(img, c)


def estrelas(img, n, area=(0, 0, W, H), alfa=(30, 120), semente=1):
    random.seed(semente)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = area
    for _ in range(n):
        x, y = random.uniform(x0, x1), random.uniform(y0, y1)
        a = random.randint(*alfa)
        r = random.choice([0, 0, 0, 1])
        d.ellipse([x - r, y - r, x + r, y + r], fill=(220, 230, 255, a))
    return img


def granulado(img, forca):
    """Ruído leve: quebra o banding dos gradientes (e dá textura de filme)."""
    ruido = Image.effect_noise((W, H), 64).convert("RGB")
    base = img.convert("RGB")
    return Image.blend(base, ImageChops.overlay(base, ruido), forca).convert("RGBA")


def vinheta(img, forca=0.6):
    """Escurece as bordas suavemente (centro intacto), em float com dithering."""
    y, x = np.ogrid[0:H, 0:W]
    r = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
    m = 1 - forca * np.clip(r / 1.25, 0, 1) ** 2.2
    base = np.asarray(img, dtype=np.float32)[..., :3] / 255.0
    return _para_imagem(base * m[..., None])


def corredor(fundo_rect):
    """Polígonos de um corredor em perspectiva de um ponto."""
    fx0, fy0, fx1, fy1 = fundo_rect
    return {
        "teto": [(0, 0), (W, 0), (fx1, fy0), (fx0, fy0)],
        "chao": [(0, H), (W, H), (fx1, fy1), (fx0, fy1)],
        "esq": [(0, 0), (fx0, fy0), (fx0, fy1), (0, H)],
        "dir": [(W, 0), (fx1, fy0), (fx1, fy1), (W, H)],
    }


def profundidade(z, z_max, a=0.55):
    """Fração 0-1 entre a boca e o fundo do corredor para a distância z."""
    return (1 - 1 / (1 + a * z)) / (1 - 1 / (1 + a * z_max))


def quadro(fundo_rect, u):
    fx0, fy0, fx1, fy1 = fundo_rect
    return (fx0 * u, fy0 * u, W + (fx1 - W) * u, H + (fy1 - H) * u)


# ---------- temas ----------

def buraconegro():
    """Preto absoluto com um buraco negro discreto: disco de acreção fino e anel de fótons."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    img = estrelas(img, 260, alfa=(15, 70), semente=3)
    cx, cy, R = W * 0.66, H * 0.48, H * 0.13
    quente = (255, 196, 140)

    def halo(d, e):
        d.ellipse([(cx - R * 3) / e, (cy - R * 3) / e, (cx + R * 3) / e, (cy + R * 3) / e],
                  fill=(255, 170, 110, 14))
        d.ellipse([(cx - R * 1.6) / e, (cy - R * 1.6) / e, (cx + R * 1.6) / e, (cy + R * 1.6) / e],
                  fill=(255, 180, 120, 18))
    img = brilho(img, halo, 520)

    disco = (cx - R * 2.9, cy - R * 0.36, cx + R * 2.9, cy + R * 0.36)

    def disco_tras(d):
        for i, (lw, a) in enumerate([(int(R * 0.10), 40), (int(R * 0.04), 110), (4, 220)]):
            d.arc(disco, 180, 360, fill=quente + (a,), width=lw)
    img = camada(img, disco_tras, desfoque=6)

    # Imagem do disco curvada pela gravidade: anel em volta da sombra, mais forte em cima.
    def lente(d):
        d.ellipse([cx - R * 1.32, cy - R * 1.32, cx + R * 1.32, cy + R * 1.32],
                  outline=quente + (38,), width=int(R * 0.10))
        d.arc([cx - R * 1.25, cy - R * 1.3, cx + R * 1.25, cy + R * 1.0], 200, 340,
              fill=quente + (80,), width=int(R * 0.08))
    img = camada(img, lente, desfoque=int(R * 0.08))

    def sombra(d):
        d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(0, 0, 0, 255))
    img = camada(img, sombra)

    def foton(d):
        d.ellipse([cx - R * 1.04, cy - R * 1.04, cx + R * 1.04, cy + R * 1.04],
                  outline=(255, 235, 210, 230), width=5)
    img = camada(img, foton, desfoque=2)

    def disco_frente(d):
        for lw, a in [(int(R * 0.12), 50), (int(R * 0.05), 140), (5, 245)]:
            d.arc(disco, 0, 180, fill=quente + (a,), width=lw)
        # lado esquerdo mais brilhante (efeito Doppler)
        d.arc(disco, 100, 175, fill=(255, 240, 220, 200), width=int(R * 0.03))
    img = camada(img, disco_frente, desfoque=5)
    return granulado(img, 0.03)


def anel():
    """Estética Halo: céu escuro, planeta com atmosfera no horizonte e um anel orbital cruzando o céu."""
    img = gradiente([(0, (2, 4, 10)), (0.7, (6, 14, 26)), (1, (10, 22, 38))])
    img = estrelas(img, 420, area=(0, 0, W, H * 0.8), alfa=(25, 140), semente=11)

    # Anel: elipse enorme e inclinada cruzando o céu; o planeta esconde a parte de baixo.
    ox, oy = int(W * 0.2), int(H * 0.2)
    anel_l = Image.new("RGBA", (W + 2 * ox, H + 2 * oy), (0, 0, 0, 0))
    d = ImageDraw.Draw(anel_l)
    caixa = (ox - W * 0.30, oy + H * 0.20, ox + W * 1.30, oy + H * 2.6)
    d.arc(caixa, 180, 360, fill=(150, 200, 235, 85), width=54)    # face interna iluminada
    d.arc(caixa, 180, 360, fill=(220, 242, 255, 210), width=8)    # borda brilhante
    inner = (caixa[0] + 54, caixa[1] + 54, caixa[2] - 54, caixa[3] - 54)
    d.arc(inner, 180, 360, fill=(30, 55, 78, 150), width=26)      # lado na sombra
    anel_l = anel_l.rotate(-6, resample=Image.BICUBIC)
    anel_l = anel_l.crop((ox, oy, ox + W, oy + H)).filter(ImageFilter.GaussianBlur(1.5))
    img = Image.alpha_composite(img, anel_l)

    # Planeta: limbo curvo embaixo, com atmosfera azulada.
    pcx, pcy, pr = W * 0.42, H * 3.15, H * 2.45

    def atmosfera(d, e):
        d.ellipse([(pcx - pr - 60) / e, (pcy - pr - 60) / e, (pcx + pr + 60) / e, (pcy + pr + 60) / e],
                  fill=(60, 170, 255, 110))
    img = brilho(img, atmosfera, 90)

    def planeta(d):
        d.ellipse([pcx - pr, pcy - pr, pcx + pr, pcy + pr], fill=(4, 9, 16, 255))
        d.ellipse([pcx - pr, pcy - pr, pcx + pr, pcy + pr], outline=(140, 215, 255, 160), width=4)
    img = camada(img, planeta, desfoque=1)

    # Luz do sol nascendo atrás do planeta: faixa fina e brilhante no limbo, à esquerda.
    limbo = [pcx - pr, pcy - pr, pcx + pr, pcy + pr]

    def sol(d, e):
        d.arc([v / e for v in limbo], 246, 262, fill=(210, 238, 255, 150), width=max(1, int(18 / e)))
    img = brilho(img, sol, 45)

    def sol_nitido(d):
        d.arc(limbo, 249, 259, fill=(240, 250, 255, 255), width=6)
    img = camada(img, sol_nitido, desfoque=3)
    return granulado(vinheta(img, 0.45), 0.025)


def neon():
    """Cyberpunk liminar: corredor vazio iluminado por neon magenta e ciano, névoa no fundo."""
    fundo = (W * 0.43, H * 0.40, W * 0.57, H * 0.56)
    p = corredor(fundo)
    img = Image.new("RGBA", (W, H), (8, 4, 18, 255))
    d = ImageDraw.Draw(img)
    d.polygon(p["teto"], fill=(14, 6, 28))
    d.polygon(p["chao"], fill=(10, 5, 22))
    d.polygon(p["esq"], fill=(22, 8, 38))
    d.polygon(p["dir"], fill=(8, 14, 34))

    # Névoa luminosa no fim do corredor
    def nevoa(d, e):
        fx0, fy0, fx1, fy1 = fundo
        d.rectangle([fx0 / e, fy0 / e, fx1 / e, fy1 / e], fill=(255, 150, 240, 255))
        d.ellipse([(fx0 - 500) / e, (fy0 - 300) / e, (fx1 + 500) / e, (fy1 + 300) / e],
                  fill=(160, 70, 255, 130))
    img = brilho(img, nevoa, 170)

    z_max = 12
    magenta, ciano = (255, 43, 214), (0, 240, 255)

    # Paredes tingidas pela luz: magenta à esquerda, ciano à direita
    def tinta(d, e):
        d.polygon([(x / e, y / e) for x, y in p["esq"]], fill=magenta + (70,))
        d.polygon([(x / e, y / e) for x, y in p["dir"]], fill=ciano + (55,))
        d.polygon([(x / e, y / e) for x, y in p["teto"]], fill=(120, 40, 255, 40))
    img = brilho(img, tinta, 120)

    def tubos(d, e=1):
        # molduras de luz ao longo do corredor, alternando cores
        for z in [0.6 + 0.9 * i for i in range(13)]:
            u = profundidade(z, z_max, a=0.25)
            x0, y0, x1, y1 = quadro(fundo, u)
            cor = magenta if int(z / 0.9) % 2 == 0 else ciano
            a = int(255 * (1 - u) ** 0.35)
            d.rectangle([x0 / e, y0 / e, x1 / e, y1 / e], outline=cor + (a,),
                        width=max(1, int(12 * (1 - u) ** 0.8 / e)))
        # tubos contínuos nos quatro cantos
        fx0, fy0, fx1, fy1 = fundo
        lw = max(1, int(14 / e))
        d.line([(0, 0), (fx0 / e, fy0 / e)], fill=magenta + (255,), width=lw)
        d.line([(W / e, 0), (fx1 / e, fy0 / e)], fill=ciano + (255,), width=lw)
        d.line([(0, H / e), (fx0 / e, fy1 / e)], fill=ciano + (200,), width=lw)
        d.line([(W / e, H / e), (fx1 / e, fy1 / e)], fill=magenta + (200,), width=lw)
    img = brilho(img, lambda d, e: tubos(d, e), 50)   # halo
    img = camada(img, tubos, desfoque=2)              # núcleo nítido

    # Reflexo das luzes no chão (piso molhado)
    refl = img.crop((0, 0, W, H // 2)).transpose(Image.FLIP_TOP_BOTTOM).filter(ImageFilter.GaussianBlur(18))
    mascara = Image.new("L", (W, H // 2), 0)
    md = ImageDraw.Draw(mascara)
    for y in range(H // 2):
        md.line([(0, y), (W, y)], fill=int(70 * (y / (H // 2)) ** 1.5))
    chao = Image.new("L", (W, H), 0)
    ImageDraw.Draw(chao).polygon(p["chao"], fill=255)
    m = Image.new("L", (W, H), 0)
    m.paste(mascara, (0, H // 2))
    m = ImageChops.multiply(m, chao)
    base = img.copy()
    base.paste(refl, (0, H // 2))
    img = Image.composite(base, img, m)
    return granulado(vinheta(img, 0.55), 0.03)


def backrooms():
    """Backrooms: corredor amarelado, luz fluorescente, carpete úmido e uma porta escura no fundo."""
    fundo = (W * 0.44, H * 0.36, W * 0.60, H * 0.60)
    p = corredor(fundo)
    img = Image.new("RGBA", (W, H), (190, 172, 98, 255))
    d = ImageDraw.Draw(img)
    d.polygon(p["teto"], fill=(214, 204, 160))
    d.polygon(p["chao"], fill=(132, 112, 58))
    d.polygon(p["esq"], fill=(196, 178, 102))
    d.polygon(p["dir"], fill=(184, 166, 92))
    fx0, fy0, fx1, fy1 = fundo
    d.rectangle(fundo, fill=(170, 152, 80))
    porta = (fx0 + (fx1 - fx0) * 0.38, fy0 + (fy1 - fy0) * 0.32, fx0 + (fx1 - fx0) * 0.62, fy1)
    d.rectangle(porta, fill=(28, 24, 12))

    z_max = 18

    # Listras verticais do papel de parede
    def listras(d):
        for i in range(1, 160):
            u = profundidade(i * 0.11, z_max)
            x0, y0, x1, y1 = quadro(fundo, u)
            a = int(26 * (1 - u))
            d.line([(x0, y0), (x0, y1)], fill=(120, 100, 40, a), width=2)
            d.line([(x1, y0), (x1, y1)], fill=(120, 100, 40, a), width=2)
    img = camada(img, listras)

    # Rodapé
    def rodape(d):
        d.polygon([(0, H), (fx0, fy1), (fx0, fy1 - 8), (0, H - 70)], fill=(150, 130, 64, 255))
        d.polygon([(W, H), (fx1, fy1), (fx1, fy1 - 8), (W, H - 70)], fill=(140, 120, 58, 255))
    img = camada(img, rodape)

    # Painéis de luz fluorescente no teto
    paineis = []
    for z in range(1, z_max, 2):
        u0, u1 = profundidade(z, z_max), profundidade(z + 0.6, z_max)
        def ponto(u, lado):
            x0, y0, x1, y1 = quadro(fundo, u)
            cx = (x0 + x1) / 2
            meia = (x1 - x0) * 0.16
            return (cx + lado * meia, y0 + (y1 - y0) * 0.02)
        paineis.append([ponto(u0, -1), ponto(u0, 1), ponto(u1, 1), ponto(u1, -1)])

    def luz(d, e):
        for q in paineis:
            d.polygon([(x / e, y / e) for x, y in q], fill=(255, 250, 215, 200))
    img = brilho(img, luz, 120)

    def luz_nitida(d):
        for q in paineis:
            d.polygon(q, fill=(255, 252, 232, 255))
    img = camada(img, luz_nitida, desfoque=1)

    # Névoa amarela e sombra perto do fundo
    def ar(d, e):
        d.rectangle([0, 0, W / e, H / e], fill=(230, 210, 120, 36))
    img = brilho(img, ar, 10)
    return granulado(vinheta(img, 0.5), 0.07)


GERADORES = {"buraconegro": buraconegro, "anel": anel, "neon": neon, "backrooms": backrooms}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("nomes", nargs="*")
    ap.add_argument("--saida", default=str(Path.home() / ".local/share/backgrounds"))
    args = ap.parse_args()
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    for nome in args.nomes or GERADORES:
        if nome not in GERADORES:
            raise SystemExit(f"desconhecido: {nome} (opções: {', '.join(GERADORES)})")
        GERADORES[nome]().convert("RGB").save(saida / f"{nome}.png", optimize=True)
        print(f"{nome}.png")
