#!/usr/bin/env python3
"""Analisa a gravação bruta: metadados, loudness, silêncios e frames de referência para enquadramento.

Uso:
  python3 analyze.py aula.mp4 -o proj/analise.json [--frames 4] [--silence-db -35] [--silence-min 0.4]

Gera:
  analise.json        metadados, loudness integrado, pico, lista de silêncios
  analise_frames.jpg  frames com grade vertical 0.0–1.0 (para estimar crop_x do rosto)
"""
import argparse
import os
import re

from common import find_font_file, probe, require, run, save_json, tc


def detect_silences(path, noise_db, min_dur):
    res = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af",
               f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"], capture=True)
    sil, start = [], None
    for line in res.stderr.splitlines():
        m = re.search(r"silence_start: (-?[\d.]+)", line)
        if m:
            start = max(0.0, float(m.group(1)))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            sil.append([round(start, 3), round(float(m.group(1)), 3)])
            start = None
    return sil


def loudness(path):
    res = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af",
               "ebur128=peak=true", "-f", "null", "-"], capture=True)
    txt = res.stderr[res.stderr.rfind("Summary:"):]
    get = lambda pat: (float(m.group(1)) if (m := re.search(pat, txt)) else None)
    return {"integrated_lufs": get(r"I:\s+(-?[\d.]+) LUFS"), "lra": get(r"LRA:\s+(-?[\d.]+) LU"),
            "true_peak_dbtp": get(r"Peak:\s+(-?[\d.]+) dBFS")}


def frames_sheet(path, info, n, out_jpg):
    dur = info["duration"]
    font = find_font_file("Inter", "Bold") or find_font_file("DejaVu Sans", "Bold")
    w = 640
    grid = []
    for i in range(1, 10):
        x = int(w * i / 10)
        grid.append(f"drawbox=x={x}:y=0:w=2:h=ih:color=yellow@0.7:t=fill")
        if font:
            grid.append(f"drawtext=fontfile='{font}':text='{i/10:.1f}':x={x + 4}:y=6:fontsize=18:"
                        "fontcolor=yellow:borderw=2:bordercolor=black")
    tmp = []
    for k in range(n):
        t = dur * (k + 1) / (n + 1)
        f = out_jpg.replace(".jpg", f"_{k}.jpg")
        vf = f"scale={w}:-2," + ",".join(grid)
        if font:
            vf += (f",drawtext=fontfile='{font}':text='{tc(t).replace(':', chr(92) + ':')}':x=6:y=h-30:fontsize=20:"
                   "fontcolor=white:borderw=2:bordercolor=black")
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", path,
             "-frames:v", "1", "-vf", vf, f], capture=True)
        tmp.append(f)
    inputs = sum((["-i", f] for f in tmp), [])
    cols = 2 if n > 1 else 1
    rows = (n + cols - 1) // cols
    if n > 1:
        # completa a grade com o último frame se necessário
        while len(inputs) // 2 < rows * cols:
            inputs += ["-i", tmp[-1]]
        layout = "|".join(f"{'+'.join(['w0'] * (i % cols)) or '0'}_{'+'.join(['h0'] * (i // cols)) or '0'}"
                          for i in range(rows * cols))
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex",
             f"xstack=inputs={rows * cols}:layout={layout}", "-frames:v", "1", out_jpg], capture=True)
    else:
        os.replace(tmp[0], out_jpg)
        tmp = []
    for f in tmp:
        os.remove(f)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("-o", "--out", default="analise.json")
    ap.add_argument("--frames", type=int, default=4)
    ap.add_argument("--silence-db", type=float, default=-35)
    ap.add_argument("--silence-min", type=float, default=0.4)
    a = ap.parse_args()
    require("ffmpeg", "ffprobe")

    info = probe(a.video)
    if not info["video"]:
        print("AVISO: arquivo sem vídeo (somente áudio).")
    if not info["audio"]:
        print("AVISO: arquivo sem áudio — cortes por fala não serão possíveis.")
    report = {"probe": info}
    if info["audio"]:
        report["loudness"] = loudness(a.video)
        sil = detect_silences(a.video, a.silence_db, a.silence_min)
        report["silences"] = sil
        total = sum(e - s for s, e in sil)
        report["silence_total_s"] = round(total, 2)
        report["silence_pct"] = round(100 * total / info["duration"], 1) if info["duration"] else 0
    if info["video"] and a.frames > 0:
        jpg = os.path.splitext(a.out)[0] + "_frames.jpg"
        os.makedirs(os.path.dirname(os.path.abspath(jpg)), exist_ok=True)
        frames_sheet(a.video, info, a.frames, jpg)
        report["frames_sheet"] = jpg
    save_json(report, a.out)

    v = info["video"] or {}
    print(f"Arquivo: {a.video}")
    print(f"Duração: {tc(info['duration'])}  |  {v.get('width')}x{v.get('height')} @ {v.get('fps', 0):.3f} fps"
          f"  |  vídeo {v.get('codec')}  |  áudio {(info['audio'] or {}).get('codec')}")
    if "loudness" in report:
        l = report["loudness"]
        print(f"Loudness: {l['integrated_lufs']} LUFS  |  LRA {l['lra']} LU  |  pico {l['true_peak_dbtp']} dBTP")
        print(f"Silêncios (>{a.silence_min}s, <{a.silence_db} dB): {len(report['silences'])} "
              f"= {report['silence_total_s']} s ({report['silence_pct']}%)")
    if v and v.get("height", 0) < 1080 and v.get("width", 0) < 1080:
        print("ALERTA: resolução baixa — recorte 9:16 terá nitidez limitada.")
    if "frames_sheet" in report:
        print(f"Frames de referência (grade crop_x): {report['frames_sheet']}")
    print(f"Relatório: {a.out}")


if __name__ == "__main__":
    main()
