#!/usr/bin/env python3
"""Gera as artes do painel inferior do layout "split" (duas telas): cartões de texto,
rótulos para imagens/takes e o fundo padrão com a assinatura do perfil.

Usado por render.py; também pode ser chamado sozinho para pré-visualizar um cartão:
  python3 panel.py --title "Juros sobre juros" --subtitle "têm limite legal" \
      --kicker "INSIGHT 01" --body "O que o contrato diz nem sempre é o que a lei permite." -o card.png
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts")

# Identidade "clássica clean": bordô + marrom, fundo creme, sem contornos pesados.
THEME = {
    "bordo": "#6B1E2E", "marrom": "#5C4030", "caramelo": "#967058",
    "areia": "#E8DDD2", "creme": "#F5EFE9",
    "title_font": "CormorantGaramond-Medium.ttf", "italic_font": "CormorantGaramond-MediumItalic.ttf",
    "text_font": "Jost-Regular.ttf", "light_font": "Jost-Light.ttf",
}


def theme(edl=None):
    return {**THEME, **((edl or {}).get("theme") or {})}


def rgb(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for word in text.split():
        test = f"{cur} {word}".strip()
        if draw.textlength(test, font=fnt) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    # evita palavra órfã na última linha
    if len(lines) > 1 and len(lines[-1].split()) == 1:
        prev = lines[-2].split()
        if len(prev) > 2:
            lines[-2], lines[-1] = " ".join(prev[:-1]), f"{prev[-1]} {lines[-1]}"
    return lines


def ornament(d, cx, y, th, w=120):
    d.line([(cx - w // 2, y), (cx + w // 2, y)], fill=rgb(th["caramelo"]), width=2)


def text_card(beat, W, PH, out, th):
    """Cartão de texto: kicker espaçado, título serifado bordô, subtítulo itálico marrom, corpo leve."""
    im = Image.new("RGBA", (W, PH), rgb(th["creme"]))
    d = ImageDraw.Draw(im)
    cx, max_w = W // 2, W - 180
    blocks = []
    if beat.get("kicker"):
        k = " ".join(beat["kicker"].upper())
        blocks.append(("kicker", [k], font(th["text_font"], 28), th["caramelo"], 44))
    tsize = int(beat.get("title_size", 84))
    if beat.get("title"):
        f = font(th["title_font"], tsize)
        blocks.append(("title", wrap(d, beat["title"], f, max_w), f, th["bordo"], int(tsize * 1.08)))
    if beat.get("subtitle"):
        f = font(th["italic_font"], tsize)
        blocks.append(("subtitle", wrap(d, beat["subtitle"], f, max_w), f, th["marrom"], int(tsize * 1.08)))
    if beat.get("body"):
        f = font(th["light_font"], 38)
        blocks.append(("body", wrap(d, beat["body"], f, max_w - 60), f, th["marrom"], 56))
    gaps = {"kicker": 40, "title": 8, "subtitle": 44, "body": 0}
    total = 60 + sum(len(ls) * lh + gaps[k] for k, ls, _, _, lh in blocks)
    y = max(70, (PH - total) // 2 - 30)
    ornament(d, cx, y, th)
    y += 60
    for kind, lines, f, color, lh in blocks:
        for ln in lines:
            d.text((cx, y + lh // 2), ln, font=f, fill=rgb(color), anchor="mm")
            y += lh
        y += gaps[kind]
    im.save(out)
    return out


def label(text, W, out, th, kicker=None):
    """Rótulo discreto para imagem/take: faixa creme translúcida na base do painel."""
    f = font(th["text_font"], 34)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lines = wrap(tmp, text, f, W - 200)
    h = 56 * len(lines) + (44 if kicker else 0) + 56
    im = Image.new("RGBA", (W, h), rgb(th["creme"], 236))
    d = ImageDraw.Draw(im)
    y = 28
    if kicker:
        d.text((W // 2, y + 16), " ".join(kicker.upper()), font=font(th["text_font"], 24),
               fill=rgb(th["caramelo"]), anchor="mm")
        y += 44
    for ln in lines:
        d.text((W // 2, y + 28), ln, font=f, fill=rgb(th["bordo"]), anchor="mm")
        y += 56
    im.save(out)
    return out


def base_panel(W, PH, out, th, handle=None):
    """Fundo padrão do painel (quando nenhum take/cartão está ativo)."""
    im = Image.new("RGBA", (W, PH), rgb(th["creme"]))
    d = ImageDraw.Draw(im)
    ornament(d, W // 2, PH // 2 - 20, th, 80)
    if handle:
        d.text((W // 2, PH // 2 + 30), handle, font=font(th["text_font"], 30), fill=rgb(th["caramelo"]), anchor="mm")
    im.save(out)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kicker")
    ap.add_argument("--title")
    ap.add_argument("--subtitle")
    ap.add_argument("--body")
    ap.add_argument("--size", default="1080x900")
    ap.add_argument("-o", "--out", default="card.png")
    a = ap.parse_args()
    W, PH = (int(x) for x in a.size.split("x"))
    text_card(vars(a), W, PH, a.out, theme())
    print(a.out)


if __name__ == "__main__":
    main()
