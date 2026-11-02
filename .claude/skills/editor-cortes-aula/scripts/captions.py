#!/usr/bin/env python3
"""Gera legendas dinâmicas (.ass) e .srt no tempo do vídeo final, a partir do EDL final e da transcrição.

Uso:
  python3 captions.py corte01.final.edl.json transcricao.json -o corte01.ass
         [--fix "stj=>STJ" --fix "anatocismo=>anatocismo"] [--save-fixes]

- Usa apenas as palavras mantidas pelo tighten.py (campo parts[].words).
- Estilo vem de edl["style"] (font, font_size, accent, text_color, caption_y, max_chars, mode).
- Também escreve <saída>.srt (útil para upload na plataforma ou para editores externos).
"""
import argparse
import os
import re

from common import die, load_json, norm_word, save_json
import panel_ass
import panel as P

WEAK_END = {"de", "do", "da", "dos", "das", "o", "a", "os", "as", "um", "uma", "e", "ou", "que", "em", "no",
            "na", "nos", "nas", "para", "pra", "com", "por", "pelo", "pela", "se", "ao", "aos", "mas", "nem",
            "não", "te", "me", "lhe", "seu", "sua", "meu", "minha", "the", "of", "to"}

def weak_key(w):
    """minúsculas sem pontuação, mantendo acentos ("é" verbo ≠ "e" conjunção)."""
    return re.sub(r"[^\w%$]", "", w.lower())


WEAK_NORM = {weak_key(x) for x in WEAK_END}

DEFAULT_STYLE = {"font": "Inter", "font_size": 70, "accent": "#FFC94A", "text_color": "#FFFFFF",
                 "outline_color": "#000000", "caption_y": 1330, "max_chars": 22, "mode": "ativo",
                 "hook_font_size": 76, "hook_y": 300, "overlay_y": 560, "margin_l": 100, "margin_r": 120,
                 "bold": True, "outline": 5, "outline_alpha": 0x10, "shadow": 2, "blur": 0, "highlight_words": True}

# Layout "split" (duas telas): legenda limpa e centralizada na base da tela de cima,
# Jost Medium, sem marca-texto/destaque colorido, apenas sombra suave.
SPLIT_STYLE = {"font": "Jost Medium", "font_size": 54, "mode": "estatico", "bold": False,
               "outline": 3, "outline_alpha": 0xA0, "shadow": 0, "blur": 4, "highlight_words": False,
               "max_chars": 26, "margin_l": 80, "margin_r": 80}


def ass_color(hex_color, alpha=0):
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def srt_time(t):
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def esc(text):
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def timeline_words(edl, words):
    """Lista de palavras com tempos no vídeo final."""
    out, off = [], 0.0
    for seg in edl["segments"]:
        parts = seg.get("parts") or die("EDL sem 'parts' — rode tighten.py antes.")
        for p in parts:
            dur = p["end"] - p["start"]
            for i in p["words"]:
                w = words[i]
                s = off + max(0.0, w["start"] - p["start"])
                e = off + min(dur, w["end"] - p["start"])
                if w["word"].strip():
                    out.append({"word": w["word"].strip(), "start": s, "end": max(e, s + 0.05)})
            off += dur
    return out, off


def group_cues(tw, max_chars, max_dur=2.5, gap_break=0.25):
    cues, cur = [], []
    def flush():
        if cur:
            cues.append(list(cur))
            cur.clear()
    for k, w in enumerate(tw):
        if cur:
            text_len = len(" ".join(x["word"] for x in cur)) + 1 + len(w["word"])
            prev = cur[-1]
            ends_sentence = re.search(r"[.!?:;…]$", prev["word"]) is not None
            # tolera até 6 caracteres a mais para não deixar a última palavra da frase sozinha
            closes = re.search(r"[.!?…]$", w["word"]) is not None and text_len <= max_chars + 6
            if ((text_len > max_chars and not closes) or w["start"] - prev["end"] > gap_break or ends_sentence
                    or w["end"] - cur[0]["start"] > max_dur):
                # não terminar bloco com palavra fraca: leva-a para o próximo
                moved = []
                while (not ends_sentence and len(cur) > 1 and len(moved) < 2
                       and weak_key(cur[-1]["word"]) in WEAK_NORM
                       and not re.search(r"[.,!?:;]$", cur[-1]["word"])):
                    moved.insert(0, cur.pop())
                flush()
                cur.extend(moved)
        cur.append(w)
    flush()
    return cues


def build(edl, words, out_ass):
    split = edl.get("layout") == "split"
    st = {**DEFAULT_STYLE, **(SPLIT_STYLE if split else {}), **(edl.get("style") or {})}
    if split and "caption_y" not in (edl.get("style") or {}):
        st["caption_y"] = int((edl.get("split") or {}).get("top_h", 1020)) - 60
    tw, total = timeline_words(edl, words)
    if not tw:
        die("nenhuma palavra no corte — confira o EDL e a transcrição.")
    hl = {norm_word(t) for h in edl.get("highlight", []) for t in h.split()} if st["highlight_words"] else set()
    cues = group_cues(tw, int(st["max_chars"]))

    W, H = 1080, 1920
    white, accent = ass_color(st["text_color"]), ass_color(st["accent"])
    outline = ass_color(st["outline_color"], int(st["outline_alpha"]))
    bold = -1 if st["bold"] else 0
    shadow = ass_color("#000000", 0x80)
    mv = H - int(st["caption_y"])
    panel_styles = "\n".join(panel_ass.styles(P.theme(edl))) + "\n" if split and edl.get("panel_anim", True) else ""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{st['font']},{st['font_size']},{white},{white},{outline},{shadow},{bold},0,0,0,100,100,0,0,1,{st['outline']},{st['shadow']},2,{st['margin_l']},{st['margin_r']},{mv},1
Style: Hook,{st['font']},{st['hook_font_size']},{white},{white},{outline},{shadow},-1,0,0,0,100,100,0,0,1,6,3,8,{st['margin_l']},{st['margin_r']},{st['hook_y']},1
Style: HookElegant,Cormorant Garamond Medium,{int(st.get('hook_elegant_size', 104))},{white},{ass_color('#000000', 0xFF)},{ass_color('#000000', 0x90)},{ass_color('#000000', 0xFF)},0,0,0,0,100,100,0,0,1,3,0,8,{st['margin_l']},{st['margin_r']},{st['hook_y']},1
Style: HookKicker,Jost,34,{white},{ass_color('#000000', 0xFF)},{ass_color('#000000', 0xA0)},{ass_color('#000000', 0xFF)},0,0,0,0,100,100,7,0,1,2,0,8,{st['margin_l']},{st['margin_r']},{max(0, st['hook_y'] - 70)},1
Style: Overlay,{st['font']},{int(st['font_size'] * 0.72)},{ass_color('#111111')},{white},{accent},{ass_color('#000000', 0xFF)},-1,0,0,0,100,100,0,0,3,16,0,8,{st['margin_l']},{st['margin_r']},{st['overlay_y']},1

{panel_styles}
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev, srt = [], []
    for n, cue in enumerate(cues):
        c0 = cue[0]["start"]
        nxt = cues[n + 1][0]["start"] if n + 1 < len(cues) else total
        c1 = nxt if nxt - cue[-1]["end"] < 0.4 else min(nxt, cue[-1]["end"] + 0.15)
        c1 = min(c1, total)
        pop = r"{\fscx94\fscy94\t(0,90,\fscx100\fscy100)}"
        if st["blur"]:
            pop = pop[:-1] + f"\\blur{st['blur']}}}"
        blurtag = f"{{\\blur{st['blur']}}}" if st["blur"] else ""
        if split:
            pop = r"{\fad(80,0)" + (f"\\blur{st['blur']}" if st["blur"] else "") + "}"

        def render(active):
            toks = []
            for j, w in enumerate(cue):
                t = esc(w["word"])
                if (j == active and st["mode"] == "ativo") or norm_word(w["word"]) in hl:
                    toks.append(f"{{\\c{accent}}}{t}{{\\c{white}}}")
                else:
                    toks.append(t)
            return " ".join(toks)

        if st["mode"] == "ativo":
            for j, w in enumerate(cue):
                s = c0 if j == 0 else w["start"]
                e = cue[j + 1]["start"] if j + 1 < len(cue) else c1
                if e - s < 0.01:
                    continue
                ev.append(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},Caption,,0,0,0,,{(pop if j == 0 else blurtag)}{render(j)}")
        else:
            ev.append(f"Dialogue: 0,{ass_time(c0)},{ass_time(c1)},Caption,,0,0,0,,{pop}{render(-1)}")
        srt.append(f"{n + 1}\n{srt_time(c0)} --> {srt_time(c1)}\n{' '.join(w['word'] for w in cue)}\n")

    if edl.get("hook_text") and not split:  # no split o hook vai como cartão no painel
        d = float(edl.get("hook_duration", 3.0))
        if st.get("hook_style") == "elegante":
            # título de gancho "sendo escrito" (Cormorant branca, sombra suave), com kicker opcional
            if edl.get("hook_kicker"):
                ev.insert(0, f"Dialogue: 1,{ass_time(0.05)},{ass_time(min(d, total))},HookKicker,,0,0,0,,"
                             f"{{\\fad(200,300)\\blur3}}{esc(edl['hook_kicker'].upper())}")
            lines = edl["hook_text"].split("\\N")
            # palavra por palavra surgindo (alpha inclui a sombra — nada de "fantasma" antes da hora)
            out_lines, ms = [], 0
            for ln in lines:
                ws = []
                for wd in ln.split():
                    ws.append(f"{{\\alpha&HFF&\\t({ms},{ms + 220},\\alpha&H00&)}}{esc(wd)}")
                    ms += 140 + 18 * len(wd)
                out_lines.append(" ".join(ws))
            body = "\\N".join(out_lines)
            ev.insert(0, f"Dialogue: 1,{ass_time(0.15)},{ass_time(min(d, total))},HookElegant,,0,0,0,,"
                         f"{{\\fad(0,300)\\blur5}}{body}")
        else:
            ev.insert(0, f"Dialogue: 1,{ass_time(0)},{ass_time(min(d, total))},Hook,,0,0,0,,"
                         f"{{\\fad(120,250)}}{esc(edl['hook_text'])}")
    if split and edl.get("panel_anim", True):
        top = int((edl.get("split") or {}).get("top_h", 1020))
        ev.extend(panel_ass.events(edl, total, top))
    for o in edl.get("overlays", []):
        ev.append(f"Dialogue: 2,{ass_time(o['start'])},{ass_time(min(o['end'], total))},Overlay,,0,0,0,,"
                  f"{{\\fad(180,180)}}{esc(o['text'])}")

    with open(out_ass, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(ev) + "\n")
    srt_path = os.path.splitext(out_ass)[0] + ".srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt))
    return cues, total, srt_path


CPL_STYLE = {"font": "Lora", "font_size": 84, "text_color": "#FFFFFF", "accent": "#E9CF96",
             "caption_y": 600, "max_chars": 18, "max_words": 3,
             "emph_font": "Lora", "emph_size": 120, "emph2_font": "Playfair Display",
             "emph2_size": 196, "emph_y": 1180}


def cpl_text(tw):
    """Minúsculas no início de frase e sem pontuação (padrão das referências); siglas e nomes ficam."""
    out, prev_end = [], True
    for w in tw:
        raw = w["word"]
        core = re.sub(r"[.,;:!?…\"“”]+$", "", raw)
        core = re.sub(r"^[\"“”(]+", "", core)
        if prev_end and core[:1].isupper() and not core.isupper() and len(core) > 1:
            core = core[0].lower() + core[1:]
        elif prev_end and core in ("A", "O", "E", "É"):
            core = core.lower()
        prev_end = re.search(r"[.!?…]$", raw) is not None
        out.append({**w, "word": core})
    return out


def build_cpl(edl, words, out_ass):
    """Estilo CPL (referência da usuária): serifa fina branca, 2–3 palavras, acima da cabeça,
    entrada suave; frases de destaque em composição branco + itálico dourado."""
    st = {**CPL_STYLE, **(edl.get("style") or {})}
    tw, total = timeline_words(edl, words)
    # nomes próprios compostos não se separam ("Banco Central", "Conselho Monetário Nacional")
    joined = []
    for w in tw:
        if joined and w["word"][:1].isupper() and joined[-1]["word"].split()[-1][:1].isupper() \
                and w["start"] - joined[-1]["end"] < 0.25 and not joined[-1]["word"].split()[-1].isupper():
            joined[-1] = {**joined[-1], "word": joined[-1]["word"] + " " + w["word"], "end": w["end"]}
        else:
            joined.append(dict(w))
    tw = joined
    mw, mc = int(st["max_words"]), int(st["max_chars"])
    raw_cues = []
    for c in group_cues(tw, mc, max_dur=2.0, gap_break=0.3):
        while len(c) > mw:
            raw_cues.append(c[:mw]); c = c[mw:]
        raw_cues.append(c)
    # palavra sozinha na tela fica "picotada": junta com a vizinha quando cabe
    # agora sim: minúsculas/sem pontuação (a divisão acima respeitou o fim das frases)
    flat = [w for c in raw_cues for w in c]
    clean = cpl_text(flat)
    k = 0
    ends = []
    for ci, c in enumerate(raw_cues):
        ends.append(re.search(r"[.!?…]$", c[-1]["word"]) is not None)  # fim de frase (antes de limpar)
        raw_cues[ci] = [x for x in clean[k:k + len(c)] if x["word"]]
        k += len(c)
    pairs = [(c, e) for c, e in zip(raw_cues, ends) if c]
    cues, prev_end = [], True
    for c, e in pairs:
        txt = lambda cc: " ".join(x["word"] for x in cc)
        if cues and not prev_end and (len(c) == 1 or len(cues[-1]) == 1) and len(txt(cues[-1] + c)) <= mc + 4 \
                and c[0]["start"] - cues[-1][-1]["end"] < 0.35:
            cues[-1] = cues[-1] + c
        else:
            cues.append(c)
        prev_end = e
    emph = edl.get("emphasis", [])
    W, H = 1080, 1920
    white, gold = ass_color(st["text_color"]), ass_color(st["accent"])
    sh = ass_color("#000000", 0x70)
    tr = ass_color("#000000", 0xFF)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{st['font']},{st['font_size']},{white},{tr},{sh},{tr},0,0,0,0,100,100,0,0,1,3,0,2,60,60,0,1
Style: Emph1,{st['emph_font']},{st['emph_size']},{white},{tr},{sh},{tr},0,0,0,0,100,100,-1,0,1,3,0,2,40,40,0,1
Style: Emph2,{st['emph2_font']},{st['emph2_size']},{gold},{tr},{ass_color('#000000', 0x80)},{tr},-1,-1,0,0,100,100,-2,0,1,3,0,2,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev, srt = [], []
    y = int(st["caption_y"])
    for n, cue in enumerate(cues):
        c0 = cue[0]["start"]
        nxt = cues[n + 1][0]["start"] if n + 1 < len(cues) else total
        c1 = min(nxt if nxt - cue[-1]["end"] < 0.35 else cue[-1]["end"] + 0.12, total)
        mid = (c0 + c1) / 2
        txt = " ".join(esc(w["word"]) for w in cue)
        srt.append(f"{n + 1}\n{srt_time(c0)} --> {srt_time(c1)}\n{' '.join(w['word'] for w in cue)}\n")
        if any(float(e["start"]) <= mid <= float(e["end"]) for e in emph):
            continue  # durante o destaque, só a composição grande aparece
        ev.append(f"Dialogue: 0,{ass_time(c0)},{ass_time(c1)},Cap,,0,0,0,,"
                  f"{{\\an2\\move(540,{y + 16},540,{y},0,170)\\fad(110,70)\\blur6}}{txt}")
    ey = int(st["emph_y"])
    fdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts")

    def fit(text, fname, size, max_w=930):
        """reduz o corpo da fonte até a linha caber na largura útil (libass ≈ métrica do PIL × 1.0)"""
        try:
            from PIL import ImageFont
            f = ImageFont.truetype(os.path.join(fdir, fname), size)
            w = f.getlength(text) * 0.71  # libass desenha ~71% da largura medida pelo PIL no mesmo corpo
            return int(size * min(1.0, max_w / w)) if w else size
        except Exception:
            return size
    for e in emph:
        s0, s1 = float(e["start"]), min(float(e["end"]), total)
        l1, l2 = esc(e.get("line1", "")), esc(e.get("line2", ""))
        f1 = fit(l1, "Lora-Regular.ttf", int(st["emph_size"]))
        f2 = fit(l2, "PlayfairDisplay-BoldItalic.ttf", int(st["emph2_size"]))
        if l1:
            ev.append(f"Dialogue: 2,{ass_time(s0)},{ass_time(s1)},Emph1,,0,0,0,,"
                      f"{{\\an2\\move(540,{ey - int(f2 * 0.76) + 18},540,{ey - int(f2 * 0.76)},0,220)"
                      f"\\fs{f1}\\fad(150,150)\\blur6}}{l1}")
        if l2:
            ev.append(f"Dialogue: 3,{ass_time(s0 + 0.18)},{ass_time(s1)},Emph2,,0,0,0,,"
                      f"{{\\an2\\pos(540,{ey + 20})\\fs{f2}\\fscx86\\fscy86\\t(0,260,\\fscx100\\fscy100)"
                      f"\\fad(140,150)\\blur5}}{l2}")
    with open(out_ass, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(ev) + "\n")
    srt_path = os.path.splitext(out_ass)[0] + ".srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt))
    return cues, total, srt_path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edl")
    ap.add_argument("transcript")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--fix", action="append", default=[], help='correção "errado=>certo" (palavra inteira)')
    ap.add_argument("--save-fixes", action="store_true", help="grava as correções na transcrição")
    a = ap.parse_args()

    edl = load_json(a.edl)
    tr = load_json(a.transcript)
    words = tr["words"]
    fixes = []
    for fx in a.fix:
        if "=>" not in fx:
            die(f'--fix inválido: {fx} (use "errado=>certo")')
        wrong, right = fx.split("=>", 1)
        fixes.append((wrong.strip(), right.strip()))
    changed = 0
    for w in words:
        for wrong, right in fixes:
            m = re.fullmatch(rf"([\"“(]*){re.escape(wrong)}([.,!?:;…\"”)]*)", w["word"], flags=re.I)
            if m:
                w["word"] = f"{m.group(1)}{right}{m.group(2)}"
                changed += 1
    if changed and a.save_fixes:
        save_json(tr, a.transcript)

    if (edl.get("style") or {}).get("preset") == "cpl":
        cues, total, srt_path = build_cpl(edl, words, a.out)
    else:
        cues, total, srt_path = build(edl, words, a.out)
    print(f"Legendas: {a.out} e {srt_path}  |  {len(cues)} blocos  |  duração do corte {total:.2f}s"
          + (f"  |  {changed} correções aplicadas" if changed else ""))
    long = [" ".join(w["word"] for w in c) for c in cues if len(" ".join(w["word"] for w in c)) > 30]
    if long:
        print("ALERTA: blocos longos (podem quebrar em 2 linhas):", *long[:5], sep="\n  ")


if __name__ == "__main__":
    main()
