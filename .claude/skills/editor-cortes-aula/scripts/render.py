#!/usr/bin/env python3
"""Renderiza o corte final: cortes + reenquadramento 9:16 + tratamento de imagem e áudio + legendas.

Uso:
  python3 render.py corte01.final.edl.json --subs corte01.ass -o corte01.mp4 [--preview] [--size 1080x1920]

--preview  render rápido (veryfast/CRF 23) para conferência; a entrega usa o padrão (slow/CRF 17).
Loudness: normalização em duas passagens para -14 LUFS / -1.5 dBTP.
"""
import argparse
import json
import os
import re
import shutil
import tempfile

from common import die, load_json, output_fps, probe, require, resolve_source, run

AUDIO_PRESETS = {
    "leve":   dict(hp=70, nr=8, nf=-30, mud=-1.5, pres=1.5, air=0.5, ratio=2, thr=-20),
    "padrao": dict(hp=80, nr=12, nf=-28, mud=-2.5, pres=2.5, air=1.0, ratio=3, thr=-22),
    "forte":  dict(hp=90, nr=18, nf=-25, mud=-3.0, pres=3.0, air=1.0, ratio=4, thr=-24),
    # "limpo": remoção de ruído por rede neural (RNNoise, modelo de fala em gravação) + FFT leve.
    # Pausas ficam em silêncio real, timbre preservado (testado por bandas de frequência).
    "limpo":  dict(hp=80, nr=6, nf=-40, mud=-2.0, pres=2.0, air=1.0, ratio=3, thr=-24, rnn=True),
    # "limpo_plus": para gravações baixas/com chiado — FFT antes e depois da rede neural, corte de
    # agudos acima de 11 kHz (onde mora o chiado) e expansor que silencia o ruído nas pausas.
    "limpo_plus": dict(hp=90, nr=10, nf=-48, mud=-2.0, pres=2.0, air=0.0, ratio=3, thr=-24, rnn=True,
                       pre_nr=18, lowpass=11000, gate=True),
}
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
VIDEO_PRESETS = {
    "nenhum": None,
    "leve":   dict(contrast=1.03, saturation=1.04, brightness=0.0, dn="1:1:4:4", sharp=0.3),
    "padrao": dict(contrast=1.06, saturation=1.07, brightness=0.01, dn="1.5:1.5:6:6", sharp=0.45),
}
TARGET_I, TARGET_TP, TARGET_LRA = -14.0, -1.5, 9.0


def parts_of(edl):
    out = []
    for seg in edl["segments"]:
        for p in seg.get("parts") or [{"start": seg["start"], "end": seg["end"]}]:
            if p["end"] - p["start"] > 0.02:
                out.append((p["start"], p["end"], float(seg.get("zoom", 1.0)),
                            p.get("crop_x", seg.get("crop_x")), p.get("crop_y", seg.get("crop_y")),
                            p.get("track")))
    if not out:
        die("EDL sem trechos.")
    return out


def geometry(edl, info, zoom, W, H, cx=None, cy=None, track=None):
    """Filtro de enquadramento de um trecho -> WxH."""
    sw, sh = info["video"]["width"], info["video"]["height"]
    # base_zoom: aproximação fixa para centralizar o rosto (fonte 4K permite sem perder nitidez)
    zoom = min(max(zoom * float(edl.get("base_zoom", 1.0)), 1.0), 1.5)  # zoom<1 no trecho = abrir o plano
    layout = edl.get("layout", "crop")
    cx = float(cx if cx is not None else edl.get("crop_x", 0.5))
    cy = float(cy if cy is not None else edl.get("crop_y", 0.5))
    target = W / H
    if layout == "blur":
        fg_w, fg_h = sw / zoom, sh / zoom
        x = min(max(cx * sw - fg_w / 2, 0), sw - fg_w)
        y = min(max(cy * sh - fg_h / 2, 0), sh - fg_h)
        pre = f"crop={int(fg_w)//2*2}:{int(fg_h)//2*2}:{int(x)}:{int(y)}," if zoom > 1.0 else ""
        return (f"{pre}split=2[bg][fg];"
                f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"gblur=sigma=40,eq=brightness=-0.08:saturation=0.9[bgb];"
                f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos[fgs];"
                f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2")
    if sw / sh > target:          # fonte mais larga que o destino: recorta a largura
        ch = sh / zoom
        cw = ch * target
    else:                          # fonte mais estreita/igual: recorta a altura
        cw = sw / zoom
        ch = cw / target
    cw, ch = int(cw) // 2 * 2, int(ch) // 2 * 2
    x = int(min(max(cx * sw - cw / 2, 0), sw - cw))
    y = int(min(max(cy * sh - ch / 2, 0), sh - ch))
    if track and len(track) >= 2:
        # acompanhamento suave do rosto: x(t) linear por partes entre os pontos da trilha
        pts = [(t, int(min(max(v * sw - cw / 2, 0), sw - cw))) for t, v in track]
        expr = str(pts[-1][1])
        for (t0, x0), (t1, x1) in reversed(list(zip(pts, pts[1:]))):
            expr = f"if(lt(t,{t1}),{x0}+({x1 - x0})*(t-{t0})/{max(t1 - t0, 0.001)},{expr})"
        return f"crop={cw}:{ch}:'{expr}':{y},scale={W}:{H}:flags=lanczos"
    return f"crop={cw}:{ch}:{x}:{y},scale={W}:{H}:flags=lanczos"


def hdr_to_sdr(info):
    """iPhone grava em HDR HLG (BT.2020). O HLG já é compatível com telas SDR; convertemos só as
    primárias/matriz para BT.709 — testado: tons de pele naturais. (Tonemap Hable/Mobius
    deixava a pele alaranjada.) Para PQ (HDR10), aplica tonemap leve."""
    v = info["video"]
    if v.get("color_transfer") == "arib-std-b67":
        return ("colorspace=all=bt709:iprimaries=bt2020:itrc=bt2020-10:ispace=bt2020ncl:"
                "irange=tv:format=yuv420p,")
    if v.get("color_transfer") == "smpte2084":
        return ("zscale=tin=smpte2084:pin=bt2020:min=bt2020nc:t=linear:npl=203,format=gbrpf32le,"
                "zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")
    return ""


def video_post(edl):
    vp = VIDEO_PRESETS.get(edl.get("video_preset", "padrao"), VIDEO_PRESETS["padrao"])
    adj = edl.get("video_adjust") or {}
    f = []
    if vp:
        f.append(f"hqdn3d={vp['dn']}")
    c = adj.get("contrast", vp["contrast"] if vp else 1.0)
    s = adj.get("saturation", vp["saturation"] if vp else 1.0)
    b = adj.get("brightness", vp["brightness"] if vp else 0.0)
    g = adj.get("gamma", 1.0)
    if (c, s, b, g) != (1.0, 1.0, 0.0, 1.0):
        f.append(f"eq=contrast={c}:saturation={s}:brightness={b}:gamma={g}")
    if adj.get("curves"):  # ex.: recuperar altas luzes estouradas
        f.append(f"curves=master='{adj['curves']}'")
    temp = float(adj.get("temperature", 0))
    if temp:
        f.append(f"colortemperature=temperature={int(6500 + 1500 * max(-1, min(1, -temp)))}")
    if vp:
        f.append(f"unsharp=5:5:{vp['sharp']}:5:5:0")
    return f


def audio_chain(edl):
    p = AUDIO_PRESETS.get(edl.get("audio_preset", "padrao"), AUDIO_PRESETS["padrao"])
    rnn = ""
    if p.get("rnn"):
        model = os.path.abspath(os.path.join(ASSETS, "rnnoise", "sh.rnnn"))
        rnn = f"aresample=48000,arnndn=m={model}:mix={float(edl.get('rnn_mix', 0.9))},"
    pre = f"afftdn=nr={p['pre_nr']}:nf=-45:tn=1," if p.get("pre_nr") else ""
    lp = f"lowpass=f={p['lowpass']}," if p.get("lowpass") else ""
    gate = ""
    if p.get("gate") and edl.get("_input_lufs") is not None:
        # limiar ~24 dB abaixo do nível médio da fala: só as pausas são atenuadas
        thr = 10 ** ((float(edl["_input_lufs"]) - 24) / 20)
        gate = f"agate=threshold={thr:.5f}:ratio=2:attack=5:release=200:range=0.25:knee=4,"
    return (f"highpass=f={p['hp']},{pre}{rnn}afftdn=nr={p['nr']}:nf={p['nf']}:tn=1,{lp}{gate}"
            f"equalizer=f=250:t=q:w=1.0:g={p['mud']},equalizer=f=3000:t=q:w=1.2:g={p['pres']},"
            f"equalizer=f=10000:t=h:w=0.7:g={p['air']},deesser=i=0.4,"
            f"acompressor=threshold={p['thr']}dB:ratio={p['ratio']}:attack=10:release=150:makeup=2")


FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts")


def split_top(edl, H):
    return int((edl.get("split") or {}).get("top_h", 1020)) // 2 * 2 if edl.get("layout") == "split" else H


def panel_graph(edl, total, fps, W, H, tmpdir, first_idx, base_dir):
    """Painel inferior do layout split: fundo + cartões de texto, imagens (Ken Burns) e takes de vídeo."""
    import panel as P
    th = P.theme(edl)
    top = split_top(edl, H)
    PH = H - top
    cfg = edl.get("split") or {}
    inputs, fc = [], []
    idx = first_idx
    fc.append(f"[vbase]pad={W}:{H}:0:0:color={th['creme']}[p0]")
    base = P.base_panel(W, PH, os.path.join(tmpdir, "panel_base.png"), th, cfg.get("handle"),
                        minimal=edl.get("panel_anim", True))
    inputs += ["-loop", "1", "-framerate", fps, "-t", f"{total:.3f}", "-i", base]
    fc.append(f"[{idx}:v]format=rgba[pb];[p0][pb]overlay=0:{top}:shortest=1[p1]")
    idx += 1
    cur = "p1"
    fade = 0.35
    for k, b in enumerate(edl.get("panel", [])):
        s, e = float(b["start"]), min(float(b["end"]), total)
        d = e - s
        if d <= 0.2:
            continue
        kind = b.get("type", "texto")
        anim = edl.get("panel_anim", True)  # cartões/rótulos animados vêm no .ass (panel_ass.py)
        if kind == "texto" and anim:
            continue
        if kind == "texto":
            png = P.text_card(b, W, PH, os.path.join(tmpdir, f"card{k}.png"), th)
            inputs += ["-loop", "1", "-framerate", fps, "-t", f"{d:.3f}", "-i", png]
            chain = f"[{idx}:v]format=rgba"
        else:
            path = b["path"] if os.path.isabs(b["path"]) else os.path.join(base_dir, b["path"])
            if not os.path.exists(path):
                die(f"arquivo do painel não encontrado: {path}")
            if kind == "imagem":
                inputs += ["-loop", "1", "-framerate", fps, "-t", f"{d:.3f}", "-i", path]
                z = float(b.get("zoom", 1.12))
                zw, zh = int(W * z) // 2 * 2, int(PH * z) // 2 * 2
                # Ken Burns lento: leve deslocamento ao longo do take
                chain = (f"[{idx}:v]scale={zw}:{zh}:force_original_aspect_ratio=increase:flags=lanczos,"
                         f"crop={zw}:{zh},crop={W}:{PH}:x='(iw-{W})*t/{d:.3f}':y='(ih-{PH})/2',"
                         f"eq=saturation={b.get('saturation', 0.9)},format=rgba")
            else:  # video
                ss = float(b.get("source_start", 0))
                inputs += ["-ss", f"{ss:.3f}", "-t", f"{d:.3f}", "-i", path]
                # take pode ser um close recortado da própria gravação: "crop": [x, y, w, h] em frações
                cr = ""
                if b.get("crop"):
                    x, y, w, h = (float(c) for c in b["crop"])
                    cr = f"crop=trunc(iw*{w}/2)*2:trunc(ih*{h}/2)*2:trunc(iw*{x}):trunc(ih*{y}),"
                hdr = hdr_to_sdr(probe(path))
                drift = float(b.get("zoom", 1.0))  # aproximação lenta opcional (1.0 = parado)
                zoom_f = ""
                if drift > 1.0:
                    zw, zh = int(W * drift) // 2 * 2, int(PH * drift) // 2 * 2
                    zoom_f = (f"scale={zw}:{zh}:flags=lanczos,"
                              f"crop={W}:{PH}:x='(iw-{W})/2*(1-t/{d:.3f})':y='(ih-{PH})/2*(1-t/{d:.3f})',")
                chain = (f"[{idx}:v]fps={fps},{hdr}{cr}scale={W}:{PH}:force_original_aspect_ratio=increase:"
                         f"flags=lanczos,crop={W}:{PH},{zoom_f}eq=saturation={b.get('saturation', 0.92)},format=rgba")
            idx += 1
            if b.get("label") and not anim:
                lp = P.label(b["label"], W, os.path.join(tmpdir, f"label{k}.png"), th, b.get("kicker"))
                inputs += ["-loop", "1", "-framerate", fps, "-t", f"{d:.3f}", "-i", lp]
                fc.append(f"{chain}[b{k}raw]")
                chain = f"[b{k}raw][{idx}:v]overlay=0:H-h-60:shortest=1,format=rgba"
            else:
                idx -= 1  # mantém a contagem coerente com o incremento abaixo
        idx += 1
        fc.append(f"{chain},trim=duration={d:.3f},setpts=PTS-STARTPTS,"
                  f"fade=t=in:st=0:d={fade}:alpha=1,fade=t=out:st={max(0, d - fade):.3f}:d={fade}:alpha=1,"
                  f"setpts=PTS+{s:.3f}/TB[b{k}]")
        fc.append(f"[{cur}][b{k}]overlay=0:{top}:eof_action=pass[q{k}]")
        cur = f"q{k}"
    return inputs, fc, cur


def sfx_events(edl, total):
    """Efeitos sonoros discretos. Manual: edl["sfx"] = [{"t": s, "file": "whoosh", "db": -20}].
    Automático (edl["sfx_auto"]): soft_hit na abertura, whoosh nas trocas do painel, tick nos cartões."""
    ev = list(edl.get("sfx", []))
    if edl.get("sfx_auto") and edl.get("layout") != "split":
        ev.append({"t": 0.0, "file": "soft_hit", "db": -24})
        off = 0.0
        for k, seg in enumerate(edl["segments"]):
            if k > 0 and off < total - 0.5:
                ev.append({"t": max(0, off - 0.18), "file": "whoosh", "db": float(edl.get("whoosh_db", -25))})  # transição no corte
            off += sum(p["end"] - p["start"] for p in seg.get("parts") or [seg])
        for o in edl.get("overlays", []):
            ev.append({"t": float(o["start"]) + 0.1, "file": "tick", "db": -30})
    elif edl.get("sfx_auto"):
        ev.append({"t": 0.0, "file": "soft_hit", "db": -24})
        for b in edl.get("panel", []):
            t = float(b["start"])
            if 0.3 < t < total - 0.5:
                ev.append({"t": max(0, t - 0.25), "file": "whoosh", "db": -26})
            if b.get("type") == "texto" and t < total - 0.5:
                ev.append({"t": t + 0.35, "file": "tick", "db": -30})
    return [e for e in ev if 0 <= e["t"] < total]


def build_graph(edl, info, src, subs, fps, W, H, with_video, loudnorm, tmpdir=None, base_dir="."):
    parts = parts_of(edl)
    VH = split_top(edl, H)
    inputs, fc = [], []
    for k, (s, e, zoom, pcx, pcy, ptr) in enumerate(parts):
        inputs += ["-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", src]
        d = e - s
        fade = min(0.01, d / 4)
        fc.append(f"[{k}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                  f"asetpts=PTS-STARTPTS,afade=t=in:d={fade:.3f},afade=t=out:st={d - fade:.3f}:d={fade:.3f}[a{k}]")
        if with_video:
            fc.append(f"[{k}:v]setpts=PTS-STARTPTS,fps={fps},{hdr_to_sdr(info)}{geometry(edl, info, zoom, W, VH, pcx, pcy, ptr)},"
                      f"fps={fps},setsar=1,format=yuv420p,trim=duration={d:.3f}[v{k}]")
    n = len(parts)
    if with_video:
        fc.append("".join(f"[v{k}][a{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac]")
    else:
        fc.append("".join(f"[a{k}]" for k in range(n)) + f"concat=n={n}:v=0:a=1[ac]")
    fc.append(f"[ac]{audio_chain(edl)},{loudnorm}[voice]")
    total = sum(p[1] - p[0] for p in parts)

    music = edl.get("music")
    if music and with_video:
        mpath = music["path"]
        if not os.path.isabs(mpath):
            mpath = os.path.join(os.path.dirname(src), mpath)
        if not os.path.exists(mpath):
            die(f"trilha não encontrada: {mpath}")
        mi = n
        inputs += ["-stream_loop", "-1", "-i", mpath]
        db = float(music.get("db", -24))
        fc.append(f"[voice]asplit=2[vmix][vsc]")
        fc.append(f"[{mi}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                  f"atrim=duration={total:.3f},volume={db}dB,afade=t=in:d=0.5,"
                  f"afade=t=out:st={max(0, total - 1.5):.3f}:d=1.5[mus]")
        fc.append("[mus][vsc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck]")
        fc.append("[vmix][duck]amix=inputs=2:duration=first:normalize=0[mixed]")
        last_a = "mixed"
    else:
        last_a = "voice"
    sfx = sfx_events(edl, total) if with_video else []
    if sfx:
        labels = []
        for j, ev in enumerate(sfx):
            path = os.path.abspath(os.path.join(ASSETS, "sfx", f"{ev['file']}.wav"))
            if not os.path.exists(path):
                die(f"efeito sonoro não encontrado: {path}")
            inputs += ["-i", path]
            si = inputs.count("-i") - 1
            ms = int(max(0, ev["t"]) * 1000)
            fc.append(f"[{si}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                      f"volume={ev.get('db', -20)}dB,adelay={ms}|{ms}[sfx{j}]")
            labels.append(f"[sfx{j}]")
        fc.append(f"[{last_a}]{''.join(labels)}amix=inputs={len(labels) + 1}:duration=first:normalize=0[withsfx]")
        last_a = "withsfx"
    fc.append(f"[{last_a}]alimiter=limit=0.89:level=0:attack=5:release=50,"
              f"aformat=sample_rates=48000:channel_layouts=stereo[aout]")

    if with_video:
        post = video_post(edl) or ["null"]
        last_v = "vc"
        if edl.get("layout") == "split":
            fc.append(f"[vc]{','.join(post)}[vbase]")
            pin, pfc, last_v = panel_graph(edl, total, fps, W, H, tmpdir, inputs.count("-i"), base_dir)
            inputs += pin
            fc += pfc
            post = []
        if subs:
            post.append(f"ass={subs}:fontsdir={os.path.abspath(FONTS_DIR)}")
        post.append("format=yuv420p")
        fc.append(f"[{last_v}]{','.join(post)}[vout]")
    return inputs, ";".join(fc), total


def make_proxy(edl, src, info, tmpdir, fps, W):
    """Fontes pesadas (4K/HEVC/HDR do iPhone): extrai cada trecho, um por vez, para um intermediário
    1080p SDR e concatena na ordem final. Evita estouro de memória (vários decodificadores 4K em
    paralelo) e acelera prévias e render final. Os takes do painel também viram intermediários."""
    import copy
    parts = parts_of(edl)
    v = info["video"]
    # intermediário com folga de resolução (1,5×) para permitir aproximação/centralização sem perda
    base = min(v["width"], int(W * 1.5)) if v["width"] <= v["height"] else int(W * v["width"] / v["height"])
    pw = int(base) // 2 * 2
    ph = int(pw * v["height"] / v["width"]) // 2 * 2
    files, new_parts, off = [], [], 0.0
    for k, (s0, e0, zoom, pcx, pcy, ptr) in enumerate(parts):
        out = os.path.join(tmpdir, f"px{k:02d}.mkv")
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{s0:.3f}", "-t", f"{e0 - s0:.3f}",
             "-i", src, "-map", "0:v:0", "-map", "0:a:0",
             "-vf", f"fps={fps},{hdr_to_sdr(info)}scale={pw}:{ph}:flags=lanczos,format=yuv420p",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "10", "-c:a", "pcm_s16le", "-ar", "48000", out])
        files.append(out)
        new_parts.append({"start": off, "end": off + (e0 - s0), "zoom": zoom, "crop_x": pcx, "crop_y": pcy, "track": ptr})
        off += e0 - s0
    lst = os.path.join(tmpdir, "px.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{x}'\n" for x in files)
    mezz = os.path.join(tmpdir, "mezz.mkv")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
         "-c", "copy", mezz])
    for x in files:
        os.remove(x)
    e2 = copy.deepcopy(edl)
    e2["segments"] = [{"start": p["start"], "end": p["end"], "zoom": p["zoom"],
                       "parts": [{"start": p["start"] + 0.0005, "end": p["end"] - 0.0005, "words": [],
                                  "crop_x": p["crop_x"], "crop_y": p["crop_y"], "track": p.get("track")}]}
                      for p in new_parts]
    # takes do painel
    PH = H_PANEL = None
    for k, b in enumerate(e2.get("panel", [])):
        if b.get("type") != "video":
            continue
        top = split_top(e2, 1920)
        PH = 1920 - top
        d = float(b["end"]) - float(b["start"])
        tin = b["path"]
        tinfo = probe(tin)
        cr = ""
        if b.get("crop"):
            x, y, w, h = (float(c) for c in b["crop"])
            cr = f"crop=trunc(iw*{w}/2)*2:trunc(ih*{h}/2)*2:trunc(iw*{x}):trunc(ih*{y}),"
        out = os.path.join(tmpdir, f"take{k:02d}.mkv")
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{float(b.get('source_start', 0)):.3f}",
             "-t", f"{d + 0.5:.3f}", "-i", tin, "-map", "0:v:0", "-an",
             "-vf", f"fps={fps},{hdr_to_sdr(tinfo)}{cr}scale={W}:{PH}:force_original_aspect_ratio=increase:"
                    f"flags=lanczos,crop={W}:{PH},format=yuv420p",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "10", out])
        b["path"], b["source_start"] = out, 0
        b.pop("crop", None)
    return e2, mezz


def measure_loudness(edl, info, src, fps, W, H):
    probe_ln = f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json"
    inputs, fc, _ = build_graph(edl, info, src, None, fps, W, H, False, probe_ln)
    res = run(["ffmpeg", "-hide_banner", "-nostats", *inputs, "-filter_complex", fc,
               "-map", "[aout]", "-f", "null", "-"], capture=True)
    m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", res.stderr, flags=re.S)
    if not m:
        die("não foi possível medir o loudness (passagem 1).")
    return json.loads(m[-1])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edl")
    ap.add_argument("--subs", help="arquivo .ass gerado por captions.py")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--crf", type=int)
    ap.add_argument("--proxy", action="store_true", help="força intermediários 1080p")
    ap.add_argument("--no-proxy", action="store_true", help="nunca usa intermediários")
    a = ap.parse_args()
    require("ffmpeg", "ffprobe")

    edl = load_json(a.edl)
    src = resolve_source(edl, a.edl)
    info = probe(src)
    if not info["video"] or not info["audio"]:
        die("a fonte precisa ter vídeo e áudio.")
    W, H = (int(x) for x in a.size.lower().split("x"))
    fps = output_fps(info, edl.get("fps"))


    tmpdir = tempfile.mkdtemp(prefix="corte_", dir=os.environ.get("CORTE_TMP"))
    v = info["video"]
    if a.proxy or (not a.no_proxy and (v["width"] * v["height"] > 2_500_000 or v.get("hdr"))):
        print("Gerando intermediários 1080p (fonte 4K/HDR)...")
        edl, src = make_proxy(edl, src, info, tmpdir, fps, W)
        info = probe(src)
    m = measure_loudness(edl, info, src, fps, W, H)
    if AUDIO_PRESETS.get(edl.get("audio_preset"), {}).get("gate"):
        edl["_input_lufs"] = float(m["input_i"])
        m = measure_loudness(edl, info, src, fps, W, H)  # remede já com o expansor
    ln = (f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:measured_I={m['input_i']}:"
          f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
          f"offset={m['target_offset']}:linear=true,aresample=48000")
    subs = None
    if a.subs:
        if not os.path.exists(a.subs):
            die(f"legenda não encontrada: {a.subs}")
        subs = os.path.join(tmpdir, "legendas.ass")   # caminho sem caracteres especiais para o filtro
        shutil.copy(a.subs, subs)
    inputs, fc, total = build_graph(edl, info, src, subs, fps, W, H, True, ln, tmpdir,
                                    os.path.dirname(os.path.abspath(a.edl)))

    from fractions import Fraction
    gop = max(1, round(float(Fraction(fps)) * 2))
    if a.preview:
        venc = ["-preset", "veryfast", "-crf", str(a.crf or 23)]
    else:
        venc = ["-preset", "slow", "-crf", str(a.crf or 17), "-maxrate", "20M", "-bufsize", "40M"]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    cmd = ["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-nostats", *inputs,
           "-filter_complex", fc, "-map", "[vout]", "-map", "[aout]",
           "-c:v", "libx264", *venc, "-profile:v", "high", "-level:v", "4.2", "-pix_fmt", "yuv420p",
           "-r", fps, "-g", str(gop), "-colorspace", "bt709", "-color_primaries", "bt709",
           "-color_trc", "bt709", "-color_range", "tv",
           "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-ac", "2",
           "-movflags", "+faststart", "-t", f"{total:.3f}", a.out]
    with open(os.path.join(tmpdir, "ffmpeg_cmd.txt"), "w") as f:
        f.write(" ".join(cmd))
    run(cmd)
    if not os.environ.get("KEEP_TMP"):
        shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"\nExportado: {a.out}  |  {W}x{H} @ {fps} fps  |  {total:.2f}s  |  "
          f"loudness de entrada {m['input_i']} LUFS → alvo {TARGET_I} LUFS"
          + ("  |  PRÉVIA (não é a versão final)" if a.preview else ""))


if __name__ == "__main__":
    main()
