"""Cartões animados do painel inferior (layout split) em ASS — texto "sendo escrito".

Cada cartão de texto (panel[].type == "texto") vira eventos ASS com animação discreta:
  - ornamento: linha fina que se desenha do centro para as bordas;
  - kicker: surge letra a letra (efeito máquina de escrever);
  - título e subtítulo: preenchimento da esquerda para a direita (\\kf), como escrita à mão;
  - corpo: aparece suavemente, subindo alguns pixels;
  - saída: fade curto.
Rótulos de imagens/takes (label/kicker) também entram com fade + leve subida.
Usado por captions.py quando o EDL tem layout "split".
"""
from PIL import ImageDraw, Image

import panel as P

W = 1080


def _c(hex_color, alpha=0):
    h = hex_color.lstrip("#")
    return f"&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def _t(t):
    cs = int(round(max(0.0, t) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(s):
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


# o libass mede a fonte pela altura total da linha (ascendente+descendente); para ficar do mesmo
# tamanho visual dos cartões aprovados (PIL), compensamos por família
SERIF_K, SANS_K = 1.30, 1.38


def styles(th):
    tr = _c("#000000", 0xFF)
    T, K, B, L, LK = int(84 * SERIF_K), int(28 * SANS_K), int(38 * SANS_K), int(34 * SANS_K), int(24 * SANS_K)
    return [
        f"Style: PKicker,Jost,{K},{_c(th['caramelo'])},{tr},{tr},{tr},0,0,0,0,100,100,7,0,1,0,0,5,60,60,0,1",
        f"Style: PTitle,Cormorant Garamond Medium,{T},{_c(th['bordo'])},{tr},{tr},{tr},0,0,0,0,100,100,0,0,1,0,0,5,60,60,0,1",
        f"Style: PSub,Cormorant Garamond Medium,{T},{_c(th['marrom'])},{tr},{tr},{tr},0,-1,0,0,100,100,0,0,1,0,0,5,60,60,0,1",
        f"Style: PBody,Jost Light,{B},{_c(th['marrom'])},{tr},{tr},{tr},0,0,0,0,100,100,0,0,1,0,0,5,90,90,0,1",
        f"Style: PLine,Jost,10,{_c(th['caramelo'])},{tr},{tr},{tr},0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        f"Style: PLabel,Jost,{L},{_c(th['bordo'])},{tr},{tr},{tr},0,0,0,0,100,100,0,0,1,0,0,5,80,80,0,1",
        f"Style: PLabelK,Jost,{LK},{_c(th['caramelo'])},{tr},{tr},{tr},0,0,0,0,100,100,5,0,1,0,0,5,80,80,0,1",
        f"Style: PBox,Jost,10,{_c(th['creme'], 0x14)},{tr},{tr},{tr},0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
    ]


def _kf(text, dur):
    """preenchimento progressivo (\\kf) distribuído pelas palavras, proporcional ao tamanho."""
    words = text.split()
    total = sum(len(w) + 1 for w in words) or 1
    cs_total = max(1, int(dur * 100))
    parts = []
    for w in words:
        cs = max(1, int(cs_total * (len(w) + 1) / total))
        parts.append(f"{{\\kf{cs}}}{_esc(w)}")
    return " ".join(parts)


def _typewriter(text, t0, dur):
    """kicker letra a letra: cada caractere fica transparente até o seu instante."""
    n = max(1, len(text))
    out = []
    for i, ch in enumerate(text):
        ms = int(dur * 1000 * i / n)
        out.append(f"{{\\alpha&HFF&\\t({ms},{ms + 60},\\alpha&H00&)}}{_esc(ch)}")
    return "".join(out)


def events(edl, total, top):
    th = P.theme(edl)
    PH = 1920 - top
    cx = W // 2
    meas = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    ev = []
    for b in edl.get("panel", []):
        s, e = float(b["start"]), min(float(b["end"]), total)
        if e - s < 0.3:
            continue
        if b.get("type", "texto") == "texto":
            tsize = int(b.get("title_size", 84))
            ft = P.font(th["title_font"], tsize)
            fi = P.font(th["italic_font"], tsize)
            fb = P.font(th["light_font"], 36)
            tl = P.wrap(meas, b.get("title", ""), ft, W - 180) if b.get("title") else []
            sl = P.wrap(meas, b.get("subtitle", ""), fi, W - 180) if b.get("subtitle") else []
            bl = P.wrap(meas, b.get("body", ""), fb, W - 240) if b.get("body") else []
            lh = int(tsize * 1.08)
            blocks = 60 + (44 + 40 if b.get("kicker") else 0) + (len(tl) + len(sl)) * lh + (8 if sl else 0) \
                + (44 + len(bl) * 56 if bl else 0)
            y = top + max(70, (PH - blocks) // 2 - 30)
            fade = r"\fad(0,250)"
            # ornamento: linha que se desenha do centro (escala horizontal 0 → 100%)
            ev.append(f"Dialogue: 5,{_t(s)},{_t(e)},PLine,,0,0,0,,{{\\an5\\pos({cx},{y})\\bord0\\shad0{fade}"
                      f"\\fscx0\\t(0,450,\\fscx100)\\p1}}m -60 -1 l 60 -1 l 60 1 l -60 1{{\\p0}}")
            y += 60
            t_cursor = 0.15
            if b.get("kicker"):
                k = b["kicker"].upper()
                kd = min(0.9, 0.035 * len(k))
                ev.append(f"Dialogue: 5,{_t(s + t_cursor)},{_t(e)},PKicker,,0,0,0,,{{\\an5\\pos({cx},{y + 22}){fade}}}"
                          f"{_typewriter(k, 0, kd)}")
                t_cursor += kd * 0.7
                y += 44 + 40
            for lines, style in ((tl, "PTitle"), (sl, "PSub")):
                for ln in lines:
                    d = min(1.0, 0.045 * len(ln) + 0.2)
                    ev.append(f"Dialogue: 5,{_t(s + t_cursor)},{_t(e)},{style},,0,0,0,,{{\\an5\\pos({cx},{y + lh // 2})"
                              f"{fade}}}{_kf(ln, d)}")
                    t_cursor += d * 0.85
                    y += lh
                if style == "PTitle" and sl:
                    y += 8
            if bl:
                y += 44
                for ln in bl:
                    ev.append(f"Dialogue: 5,{_t(s + t_cursor)},{_t(e)},PBody,,0,0,0,,"
                              f"{{\\an5\\move({cx},{y + 28 + 14},{cx},{y + 28},0,400)\\fad(350,250)}}{_esc(ln)}")
                    y += 56
                    t_cursor += 0.15
        elif b.get("label"):
            # rótulo de imagem/take: faixa creme translúcida + texto, entrando suave
            label = b["label"]
            kick = b.get("kicker")
            fl = P.font(th["text_font"], 34)
            lines = P.wrap(meas, label, fl, W - 200)
            h = 56 * len(lines) + (44 if kick else 0) + 56
            yb = 1920 - 60 - h
            ev.append(f"Dialogue: 4,{_t(s + 0.3)},{_t(e)},PBox,,0,0,0,,{{\\an7\\pos(0,{yb})\\bord0\\shad0"
                      f"\\fad(300,250)\\p1}}m 0 0 l {W} 0 l {W} {h} l 0 {h}{{\\p0}}")
            y = yb + 28
            if kick:
                k = kick.upper()
                ev.append(f"Dialogue: 5,{_t(s + 0.45)},{_t(e)},PLabelK,,0,0,0,,{{\\an5\\pos({cx},{y + 16})\\fad(0,250)}}"
                          f"{_typewriter(k, 0, min(0.8, 0.03 * len(k)))}")
                y += 44
            for ln in lines:
                ev.append(f"Dialogue: 5,{_t(s + 0.6)},{_t(e)},PLabel,,0,0,0,,"
                          f"{{\\an5\\move({cx},{y + 28 + 12},{cx},{y + 28},0,350)\\fad(300,250)}}{_esc(ln)}")
                y += 56
    return ev
