#!/usr/bin/env python3
"""
Gera fundos 1280x720 (16:9) para thumbnails do YouTube da igreja (PIB IPSEP).

Receita visual (inspirada nos exemplos IPP):
  1. Gradiente diagonal suave
  2. (opcional) elemento gráfico discreto em contorno fino e translúcido,
     tipo marca d'água — nunca competindo com título/foto/logo/hora
  3. Escurecimento suave na zona do texto (esquerda, por padrão)
  4. Vinheta leve nos cantos
  5. Textura de grão/ruído

Como na IPB/IPP, o verde é a cor-mãe do canal, mas cada culto tem sua
própria família de cores para ser reconhecido de relance no feed.

Uso:  python3 gerar_fundos.py
Saída: fundos/matutino/, fundos/noturno/ e fundos/oracao/ com os PNGs,
       cada pasta com uma _previa.png (folha de contato)
"""

import math
import os
import sys
from PIL import Image, ImageChops, ImageDraw, ImageFont

W, H = 1280, 720          # tamanho final
SS = 2                    # fator de supersampling (anti-aliasing)
SW, SH = W * SS, H * SS
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fundos")


# ---------------------------------------------------------------- utilidades

def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    return t * t * (3 - 2 * t)


def mix(c1, c2, t):
    return tuple(int(round(lerp(a, b, t))) for a, b in zip(c1, c2))


def grad_color(stops, t):
    """stops = [(pos, (r,g,b)), ...] ordenado; interpola com suavizacao."""
    if t <= stops[0][0]:
        return stops[0][1]
    if t >= stops[-1][0]:
        return stops[-1][1]
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if p0 <= t <= p1:
            u = (t - p0) / (p1 - p0) if p1 > p0 else 0.0
            return mix(c0, c1, smooth(u))
    return stops[-1][1]


def linear_gradient(stops, angle_deg, size=(160, 90)):
    """Gradiente linear na direcao angle_deg (0 = esquerda->direita)."""
    gw, gh = size
    img = Image.new("RGB", size)
    px = img.load()
    ang = math.radians(angle_deg)
    dx, dy = math.cos(ang), math.sin(ang)
    # projeta os 4 cantos para normalizar t em [0,1]
    projs = [x * dx + y * dy for x in (0, gw - 1) for y in (0, gh - 1)]
    pmin, pmax = min(projs), max(projs)
    for y in range(gh):
        for x in range(gw):
            t = (x * dx + y * dy - pmin) / (pmax - pmin)
            px[x, y] = grad_color(stops, t)
    return img.resize((SW, SH), Image.BICUBIC)


def radial_glow(base, center, radius, color, strength):
    """Aplica um brilho radial (mistura 'color' perto do centro)."""
    gw, gh = 160, 90
    mask = Image.new("L", (gw, gh))
    px = mask.load()
    cx, cy = center[0] * gw, center[1] * gh
    r = radius * gw
    for y in range(gh):
        for x in range(gw):
            d = math.hypot(x - cx, y - cy) / r
            v = max(0.0, 1.0 - d)
            px[x, y] = int(255 * smooth(v) * strength)
    mask = mask.resize(base.size, Image.BICUBIC)
    layer = Image.new("RGB", base.size, color)
    return Image.composite(layer, base, mask)


# ------------------------------------------------- zona de texto e vinheta

def darken_side(img, side="left", max_alpha=48, extent=0.55):
    """Gradiente preto suave na lateral onde vai o texto."""
    gw = 256
    strip = Image.new("L", (gw, 1))
    px = strip.load()
    for x in range(gw):
        t = x / (gw - 1)
        if side == "right":
            t = 1 - t
        v = max(0.0, 1.0 - t / extent)
        px[x, 0] = int(max_alpha * smooth(v))
    mask = strip.resize(img.size, Image.BICUBIC)
    black = Image.new("RGBA", img.size, (0, 0, 0, 255))
    black.putalpha(mask)
    img.alpha_composite(black)


def vignette(img, max_alpha=42):
    gw, gh = 160, 90
    mask = Image.new("L", (gw, gh))
    px = mask.load()
    cx, cy = gw / 2, gh / 2
    md = math.hypot(cx, cy)
    for y in range(gh):
        for x in range(gw):
            d = math.hypot(x - cx, y - cy) / md
            px[x, y] = int(max_alpha * (d ** 2.2))
    mask = mask.resize(img.size, Image.BICUBIC)
    black = Image.new("RGBA", img.size, (0, 0, 0, 255))
    black.putalpha(mask)
    img.alpha_composite(black)


def add_grain(img, sigma=16, amount=0.45):
    """Grao aplicado na resolucao final para ficar nitido como nos exemplos."""
    noise = Image.effect_noise(img.size, sigma).convert("RGB")
    overlaid = ImageChops.overlay(img, noise)
    return Image.blend(img, overlaid, amount)


# ------------------------------------------------------------------ receita

def make_bg(name, stops, angle, out_dir, glow=None, text_side="left",
            text_alpha=48):
    base = linear_gradient(stops, angle).convert("RGBA")
    if glow:
        rgb = radial_glow(base.convert("RGB"), *glow)
        base = rgb.convert("RGBA")

    if text_side:
        darken_side(base, text_side, max_alpha=text_alpha)
    vignette(base)

    final = base.convert("RGB").resize((W, H), Image.LANCZOS)
    final = add_grain(final)
    path = os.path.join(out_dir, name + ".png")
    final.save(path, optimize=True)
    print("ok:", path)
    return final


CULTOS = {
    # ------------------------------------------------ Culto Matutino (dom.)
    # Manhã: cores claras, frescas, "luz nascendo". Verde é a base.
    "matutino": [
        dict(name="matutino_01_verde_amarelo",       # sol da manhã (ref. 08h00 IPP)
             stops=[(0.0, hex_rgb("1C5B34")), (0.55, hex_rgb("4E9A3C")),
                    (1.0, hex_rgb("C9D64B"))],
             angle=-35),
        dict(name="matutino_02_verde_classico",      # verde puro (ref. 11h00 IPP)
             stops=[(0.0, hex_rgb("6FB93F")), (0.55, hex_rgb("2E7D46")),
                    (1.0, hex_rgb("14381F"))],
             angle=55),
        dict(name="matutino_03_agua",                # teal fresco (ref. EBD 09h30 IPP)
             stops=[(0.0, hex_rgb("1FA98C")), (0.5, hex_rgb("4FAE6E")),
                    (1.0, hex_rgb("A6D488"))],
             angle=-25, text_alpha=40),
        dict(name="matutino_04_amanhecer",           # âmbar -> verde, nascer do sol
             stops=[(0.0, hex_rgb("E9C25F")), (0.45, hex_rgb("86B054")),
                    (1.0, hex_rgb("2E7D46"))],
             angle=40),
        dict(name="matutino_05_verde_claro",         # claro; usar TEXTO ESCURO
             stops=[(0.0, hex_rgb("E4F0D6")), (0.5, hex_rgb("A9D48F")),
                    (1.0, hex_rgb("5FA352"))],
             angle=50, text_alpha=26),
    ],
    # ------------------------------------------------- Culto Noturno (dom.)
    # Noite: fundos profundos e ricos; verde pode encontrar outra cor.
    "noturno": [
        dict(name="noturno_01_verde_profundo",       # sóbrio, só verde
             stops=[(0.0, hex_rgb("0B2B1C")), (0.6, hex_rgb("174D33")),
                    (1.0, hex_rgb("0A2418"))],
             angle=35,
             glow=((0.72, 0.38), 0.85, hex_rgb("2C7A52"), 0.55)),
        dict(name="noturno_02_verde_roxo",           # ref. Culto Noturno IPP
             stops=[(0.0, hex_rgb("4E9A3C")), (0.45, hex_rgb("2E6155")),
                    (1.0, hex_rgb("5B2A86"))],
             angle=30),
        dict(name="noturno_03_marinho_laranja",      # ref. Conexão com Deus 20h
             stops=[(0.0, hex_rgb("D8792F")), (0.45, hex_rgb("64405A")),
                    (1.0, hex_rgb("101E38"))],
             angle=35),
        dict(name="noturno_04_violeta",              # ref. programas roxos IPP
             stops=[(0.0, hex_rgb("9B4FBF")), (0.5, hex_rgb("5B2A86")),
                    (1.0, hex_rgb("241448"))],
             angle=45),
        dict(name="noturno_05_holofote",             # facho de luz sobre verde
             stops=[(0.0, hex_rgb("11351F")), (1.0, hex_rgb("0D2A19"))],
             angle=90,
             glow=((0.68, 0.42), 0.75, hex_rgb("3E9E63"), 0.75)),
        dict(name="noturno_06_vinho",                # noite especial / ceia
             stops=[(0.0, hex_rgb("8A2536")), (0.55, hex_rgb("4A1220")),
                    (1.0, hex_rgb("1E0A10"))],
             angle=40,
             glow=((0.7, 0.35), 0.8, hex_rgb("B4453A"), 0.4)),
    ],
    # ---------------------------------------------- Culto de Oração (qua.)
    # Oração: sereno, intimista; teal/petróleo e brilhos suaves.
    "oracao": [
        dict(name="oracao_01_sereno",                # ref. Oração da Manhã IPP
             stops=[(0.0, hex_rgb("57AFA0")), (0.55, hex_rgb("3E8E75")),
                    (1.0, hex_rgb("1F5B41"))],
             angle=80),
        dict(name="oracao_02_esmeralda",
             stops=[(0.0, hex_rgb("083326")), (0.55, hex_rgb("0F5C46")),
                    (1.0, hex_rgb("199578"))],
             angle=-30),
        dict(name="oracao_03_vigilia",               # verde escuro + luz dourada
             stops=[(0.0, hex_rgb("123B28")), (1.0, hex_rgb("0C2517"))],
             angle=90,
             glow=((0.68, 0.40), 0.8, hex_rgb("C9A23F"), 0.45)),
        dict(name="oracao_04_petroleo",              # azul-petróleo contemplativo
             stops=[(0.0, hex_rgb("0A2E3D")), (0.55, hex_rgb("145A66")),
                    (1.0, hex_rgb("071B25"))],
             angle=35,
             glow=((0.7, 0.4), 0.8, hex_rgb("1F7F86"), 0.5)),
        dict(name="oracao_05_verde_dourado",         # calor acolhedor
             stops=[(0.0, hex_rgb("C99B3F")), (0.45, hex_rgb("6E8039")),
                    (1.0, hex_rgb("143D26"))],
             angle=40),
    ],
    # ---------------------------------------- Ceia do Senhor (1º domingo)
    # Memorial, comunhao e autoexame: vinho/bordo, pao/dourado e a ponte
    # verde -> vinho.
    "ceia": [
        dict(name="ceia_01_vinho",                   # o classico: vinho profundo
             stops=[(0.0, hex_rgb("8A2536")), (0.55, hex_rgb("4A1220")),
                    (1.0, hex_rgb("1E0A10"))],
             angle=40,
             glow=((0.7, 0.35), 0.8, hex_rgb("B4453A"), 0.4)),
        dict(name="ceia_02_verde_vinho",             # identidade da igreja + Ceia
             stops=[(0.0, hex_rgb("2E6B45")), (0.5, hex_rgb("34222E")),
                    (1.0, hex_rgb("711F31"))],
             angle=30),
        dict(name="ceia_03_pao",                     # mesa, pao partido (manha)
             stops=[(0.0, hex_rgb("D9A85C")), (0.5, hex_rgb("8A6A33")),
                    (1.0, hex_rgb("3A2A16"))],
             angle=40),
        dict(name="ceia_04_memorial",                # sobrio, autoexame (noite)
             stops=[(0.0, hex_rgb("2A1220")), (0.6, hex_rgb("4A1524")),
                    (1.0, hex_rgb("120609"))],
             angle=35,
             glow=((0.68, 0.42), 0.75, hex_rgb("8E3A44"), 0.5)),
    ],
    # ------------------------------------- Páscoa (Domingo da Ressurreição)
    # Ressurreicao, cruz e vitoria sobre a morte — contado so com luz:
    # a madrugada que amanhece, a escuridao vencida, a vida nova.
    "pascoa": [
        dict(name="pascoa_01_alvorada",              # Culto da Alvorada
             stops=[(0.0, hex_rgb("1B1F3A")), (0.5, hex_rgb("7A3D52")),
                    (1.0, hex_rgb("E8B84B"))],
             angle=-40,
             glow=((0.75, 0.25), 0.7, hex_rgb("F2C75C"), 0.5)),
        dict(name="pascoa_02_vitoria",               # luminoso; usar TEXTO ESCURO
             stops=[(0.0, hex_rgb("F7F0DC")), (0.5, hex_rgb("EAD79E")),
                    (1.0, hex_rgb("C9A23F"))],
             angle=45, text_alpha=22),
        dict(name="pascoa_03_gloria",                # realeza + luz dourada
             stops=[(0.0, hex_rgb("2A1846")), (0.6, hex_rgb("55307F")),
                    (1.0, hex_rgb("1C0F33"))],
             angle=35,
             glow=((0.72, 0.32), 0.55, hex_rgb("E8BC55"), 0.4)),
        dict(name="pascoa_04_vida",                  # da morte para a vida
             stops=[(0.0, hex_rgb("060D08")), (0.5, hex_rgb("123B24")),
                    (1.0, hex_rgb("3FA45C"))],
             angle=-35,
             glow=((0.72, 0.3), 0.7, hex_rgb("58C878"), 0.5)),
        dict(name="pascoa_05_manha",                 # cantata; usar TEXTO ESCURO
             stops=[(0.0, hex_rgb("BFD9E8")), (0.5, hex_rgb("D9E4C9")),
                    (1.0, hex_rgb("8FBF7A"))],
             angle=45, text_alpha=24),
    ],
    # ------------------------------------------- Natal (25/12 ou domingo)
    # Encarnacao: a luz entrando na noite do mundo. Nada de vermelho
    # comercial — noite de Belem, candeia, verde festivo, estrela.
    "natal": [
        dict(name="natal_01_belem",                  # noite + luz dourada
             stops=[(0.0, hex_rgb("0A1428")), (0.55, hex_rgb("14294F")),
                    (1.0, hex_rgb("060D1A"))],
             angle=35,
             glow=((0.75, 0.22), 0.42, hex_rgb("E8C566"), 0.45)),
        dict(name="natal_02_candeia",                # luz quente de vela
             stops=[(0.0, hex_rgb("3A2208")), (0.55, hex_rgb("6E4416")),
                    (1.0, hex_rgb("1C1004"))],
             angle=40,
             glow=((0.68, 0.40), 0.75, hex_rgb("F2C75C"), 0.55)),
        dict(name="natal_03_festa_verde",            # o verde da igreja + ouro
             stops=[(0.0, hex_rgb("1C5B34")), (0.55, hex_rgb("0E3D26")),
                    (1.0, hex_rgb("082517"))],
             angle=55,
             glow=((0.72, 0.28), 0.5, hex_rgb("E8C566"), 0.35)),
        dict(name="natal_04_estrela",                # noite fria, brilho prata
             stops=[(0.0, hex_rgb("16294D")), (0.5, hex_rgb("2A4A7A")),
                    (1.0, hex_rgb("0C1730"))],
             angle=-35,
             glow=((0.75, 0.25), 0.5, hex_rgb("D9E4F5"), 0.5)),
        dict(name="natal_05_manha",                  # manha de Natal; TEXTO ESCURO
             stops=[(0.0, hex_rgb("F7EBE0")), (0.5, hex_rgb("EDC9A8")),
                    (1.0, hex_rgb("C98B5C"))],
             angle=45, text_alpha=22),
    ],
}


def contact_sheet(imgs, names, path):
    cols, tw, th, pad, cap = 2, 620, 349, 16, 34
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + pad) + pad,
                              rows * (th + cap + pad) + pad), (24, 26, 24))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
    for i, (im, nm) in enumerate(zip(imgs, names)):
        r, c = divmod(i, cols)
        x = pad + c * (tw + pad)
        y = pad + r * (th + cap + pad)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y))
        d.text((x + 2, y + th + 6), nm, fill=(230, 230, 230), font=font)
    sheet.save(path, optimize=True)
    print("ok:", path)


if __name__ == "__main__":
    # opcional: gerar so uma categoria, ex.: python3 gerar_fundos.py ceia
    pedidos = [a for a in sys.argv[1:] if a in CULTOS] or list(CULTOS)
    for culto in pedidos:
        variantes = CULTOS[culto]
        out_dir = os.path.join(OUT, culto)
        os.makedirs(out_dir, exist_ok=True)
        imgs, names = [], []
        for v in variantes:
            imgs.append(make_bg(out_dir=out_dir, **v))
            names.append(v["name"])
        contact_sheet(imgs, names, os.path.join(out_dir, "_previa.png"))
