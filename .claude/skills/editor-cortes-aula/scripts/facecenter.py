#!/usr/bin/env python3
"""Centraliza o rosto: detecta a posição do rosto em cada trecho do EDL final e grava
crop_x/crop_y por trecho (parts), para que o professor fique sempre no centro da tela de cima.

Uso:
  python3 facecenter.py corte.final.edl.json [--step 0.5] [--face-y 0.42]

--face-y: altura desejada do rosto dentro do recorte (0 = topo, 1 = base). 0.42 deixa respiro
acima da cabeça e espaço para a legenda embaixo.
Requer OpenCV 4.x com Haar cascades: pip install "opencv-python-headless<5".
"""
import argparse
import subprocess

import numpy as np

from common import die, load_json, probe, resolve_source, save_json


def frames(src, t0, t1, step, w=540):
    info = probe(src)["video"]
    h = int(round(w * info["height"] / info["width"] / 2) * 2)
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{max(0.1, t1 - t0):.3f}", "-i", src,
                          "-vf", f"fps={1 / step},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         stdout=subprocess.PIPE, check=True).stdout
    n = len(out) // (w * h)
    return [np.frombuffer(out[i * w * h:(i + 1) * w * h], dtype=np.uint8).reshape(h, w) for i in range(n)], w, h


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edl")
    ap.add_argument("--step", type=float, default=0.5)
    ap.add_argument("--face-y", type=float, default=0.42)
    ap.add_argument("--smooth", type=float, default=2.5, help="janela de suavização da trilha (s)")
    ap.add_argument("--head-shift", type=float, default=0.2,
                    help="desloca o centro p/ a nuca, em frações da largura do rosto (+ = esquerda). "
                         "Use negativo se a pessoa olhar para a esquerda do quadro.")
    ap.add_argument("--static", action="store_true", help="sem acompanhamento: um centro fixo por trecho")
    a = ap.parse_args()
    try:
        import cv2
    except ImportError:
        die("instale: pip install \"opencv-python-headless<5\"")
    edl = load_json(a.edl)
    src = resolve_source(edl, a.edl)
    info = probe(src)["video"]
    front = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    prof = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    # tamanho do recorte da tela de cima em frações da fonte (para converter "rosto a 42%" em centro)
    top_h = int((edl.get("split") or {}).get("top_h", 1920)) if edl.get("layout") == "split" else 1920
    target = 1080 / top_h
    zoom = float(edl.get("base_zoom", 1.0))
    sw, sh = info["width"], info["height"]
    cw = (sw / zoom) if sw / sh <= target else (sh / zoom) * target
    ch = cw / target
    last = (float(edl.get("crop_x", 0.5)), float(edl.get("crop_y", 0.5)))
    for seg in edl["segments"]:
        for p in seg.get("parts", []):
            imgs, w, h = frames(src, p["start"], p["end"], a.step)
            xs, ys, track_x = [], [], []
            for g in imgs:
                found = list(front.detectMultiScale(g, 1.1, 5, minSize=(w // 12, w // 12)))
                if not found:
                    found = list(prof.detectMultiScale(g, 1.1, 4, minSize=(w // 12, w // 12)))
                    if not found:
                        found = [(w - x - fw, y, fw, fh) for x, y, fw, fh in
                                 prof.detectMultiScale(cv2.flip(g, 1), 1.1, 4, minSize=(w // 12, w // 12))]
                if found:
                    x, y, fw, fh = max(found, key=lambda r: r[2] * r[3])
                    hx = (x + fw / 2 - a.head_shift * fw) / w  # centro da cabeça (inclui cabelo/nuca)
                    xs.append(hx)
                    ys.append((y + fh / 2) / h)
                    track_x.append(hx)
                else:
                    track_x.append(np.nan)
            # trilha suave do rosto ao longo do trecho (auto-reframe), em tempo relativo ao trecho
            n = len(imgs)
            if not a.static and n >= 3 and len(xs) >= max(2, n // 3):
                tx = np.full(n, np.nan)
                k = 0
                tx = np.array(track_x)
                ok = ~np.isnan(tx)
                tx = np.interp(np.arange(n), np.flatnonzero(ok), tx[ok])
                win = max(1, int(round(a.smooth / a.step)))
                ker = np.ones(win) / win
                pad = np.pad(tx, (win // 2, win - 1 - win // 2), mode="edge")
                sm = np.convolve(pad, ker, mode="valid")
                p["track"] = [[round(i * a.step, 3), round(float(v), 4)] for i, v in enumerate(sm)]
            else:
                p.pop("track", None)
            if xs:
                fx, fy = float(np.median(xs)), float(np.median(ys))
                cx = fx
                cy = fy + (0.5 - a.face_y) * (ch / sh)  # desloca o centro para o rosto ficar em face_y
                last = (round(cx, 4), round(cy, 4))
            p["crop_x"], p["crop_y"] = last
            print(f"{p['start']:8.2f}-{p['end']:8.2f}  rosto detectado em {len(xs)}/{len(imgs)} quadros  "
                  f"→ crop_x={last[0]:.3f} crop_y={last[1]:.3f}")
    save_json(edl, a.edl)
    print(f"EDL atualizado: {a.edl}")


if __name__ == "__main__":
    main()
