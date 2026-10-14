#!/usr/bin/env python3
"""Revisão técnica do vídeo exportado + frames de controle com guia de área segura.

Uso:
  python3 qa.py corte01.mp4 [--edl corte01.final.edl.json] [--subs corte01.ass] -o corte01_qa

Gera <saída>/relatorio.json e <saída>/controle.jpg (6 frames com zonas de risco em vermelho).
Código de saída 1 se houver FALHA.
"""
import argparse
import os
import re

from common import load_json, output_fps, probe, require, resolve_source, run, save_json, tc

SAFE = {"top": 220, "bottom": 1500, "right": 140, "left": 90}


def ebur(path):
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "ebur128=peak=true",
             "-f", "null", "-"], capture=True).stderr
    s = r[r.rfind("Summary:"):]
    g = lambda p: (float(m.group(1)) if (m := re.search(p, s)) else None)
    return g(r"I:\s+(-?[\d.]+) LUFS"), g(r"Peak:\s+(-?[\d.inf]+) dBFS")


def gaps(path, min_d=0.7):
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af",
             f"silencedetect=noise=-40dB:d={min_d}", "-f", "null", "-"], capture=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r)]
    return [(max(0, s), e) for s, e in zip(st, en)]


def check_ass(path):
    issues = []
    txt = open(path, encoding="utf-8").read()
    pr = re.search(r"PlayResY:\s*(\d+)", txt)
    H = int(pr.group(1)) if pr else 1920
    for m in re.finditer(r"^Style: Caption,[^,]*,(\d+),(?:[^,]*,){16}(\d+),(\d+),(\d+)", txt, flags=re.M):
        size, ml, mr, mv = map(int, m.groups())
        base = H - mv
        if base > SAFE["bottom"] * H / 1920:
            issues.append(f"legenda abaixo da área segura (base y={base}, limite {SAFE['bottom']})")
        if base - 2 * size * 1.2 < 1000 * H / 1920:
            issues.append("legenda de 2 linhas pode alcançar a região do rosto — confira os frames")
    lines = re.findall(r"^Dialogue: [^\n]*", txt, flags=re.M)
    for l in lines:
        if l.count("\\N") >= 2:
            issues.append(f"bloco com mais de 2 linhas: {l[-60:]}")
    return issues, len(lines)


def contact_sheet(path, dur, outdir):
    times = [0.3, min(1.5, dur * 0.1), dur * 0.25, dur * 0.5, dur * 0.75, max(0, dur - 0.5)]
    guide = (f"drawbox=x=0:y=0:w=iw:h={SAFE['top']}:color=red@0.25:t=fill,"
             f"drawbox=x=0:y={SAFE['bottom']}:w=iw:h=ih-{SAFE['bottom']}:color=red@0.25:t=fill,"
             f"drawbox=x=iw-{SAFE['right']}:y=0:w={SAFE['right']}:h=ih:color=red@0.25:t=fill,scale=360:640")
    files = []
    for k, t in enumerate(times):
        f = os.path.join(outdir, f"f{k}_{t:.1f}s.jpg")
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", path,
             "-frames:v", "1", "-vf", guide, f], capture=True)
        files.append(f)
    ins = sum((["-i", f] for f in files), [])
    out = os.path.join(outdir, "controle.jpg")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *ins, "-filter_complex",
         "xstack=inputs=6:layout=0_0|w0_0|w0+w0_0|0_h0|w0_h0|w0+w0_h0", "-frames:v", "1", out], capture=True)
    return out, [(round(t, 2), f) for t, f in zip(times, files)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--edl")
    ap.add_argument("--subs")
    ap.add_argument("-o", "--out", default="qa")
    a = ap.parse_args()
    require("ffmpeg", "ffprobe")
    os.makedirs(a.out, exist_ok=True)

    info = probe(a.video)
    v, au = info["video"], info["audio"]
    fails, warns, ok = [], [], []
    (ok if (v["width"], v["height"]) == (1080, 1920) else warns).append(f"resolução {v['width']}x{v['height']}")
    (ok if v["codec"] == "h264" else fails).append(f"codec de vídeo {v['codec']}")
    (ok if v["pix_fmt"] == "yuv420p" else fails).append(f"pix_fmt {v['pix_fmt']}")
    (ok if au and au["codec"] == "aac" and au["sample_rate"] == 48000 else fails).append(
        f"áudio {au and au['codec']} {au and au['sample_rate']} Hz")
    d = info["duration"]
    (ok if 15 <= d <= 90 else warns).append(f"duração {d:.1f}s (alvo 30–60 s)")

    if a.edl:
        edl = load_json(a.edl)
        try:
            src_fps = output_fps(probe(resolve_source(edl, a.edl)), edl.get("fps"))
            from fractions import Fraction
            same = abs(float(Fraction(src_fps)) - v["fps"]) < 0.05
            (ok if same else fails).append(f"fps {v['fps']:.3f} (fonte {src_fps})")
        except SystemExit:
            warns.append("fonte do EDL inacessível — fps não comparado")

    I, tp = ebur(a.video)
    if I is None:
        fails.append("loudness não medido")
    else:
        (ok if -15.0 <= I <= -13.0 else fails).append(f"loudness {I} LUFS (alvo -14)")
        (ok if tp is not None and tp <= -1.0 else fails).append(f"true peak {tp} dBTP (máx -1.0)")
    g = gaps(a.video)
    for s, e in g:
        if s > 0.5 and e < d - 0.5:
            warns.append(f"silêncio de {e - s:.2f}s em {tc(s)} — é pausa estratégica?")
        elif s <= 0.3:
            fails.append(f"silêncio de {e - s:.2f}s no início — o hook deve começar imediatamente")

    if a.subs:
        issues, n = check_ass(a.subs)
        warns.extend(issues)
        ok.append(f"{n} eventos de legenda")

    sheet, frames = contact_sheet(a.video, d, a.out)
    rep = {"video": a.video, "probe": info, "ok": ok, "alertas": warns, "falhas": fails,
           "loudness_lufs": I, "true_peak_dbtp": tp, "controle": sheet, "frames": frames}
    save_json(rep, os.path.join(a.out, "relatorio.json"))
    for x in ok:
        print(f"  OK      {x}")
    for x in warns:
        print(f"  ALERTA  {x}")
    for x in fails:
        print(f"  FALHA   {x}")
    print(f"\nFrames de controle (abra e inspecione): {sheet}")
    print("Zonas vermelhas = áreas cobertas pela interface do app. Legenda e rosto devem ficar fora delas.")
    print("Resultado:", "REPROVADO — corrija e re-renderize." if fails else "APROVADO tecnicamente — faça a revisão visual/conteúdo.")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
