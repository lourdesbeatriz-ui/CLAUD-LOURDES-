#!/usr/bin/env python3
"""Refina os cortes do EDL: encaixa em fronteiras de palavra, remove hesitações/palavras marcadas
e encurta pausas longas, preservando pausas estratégicas.

Uso:
  python3 tighten.py corte01.edl.json transcricao.json -o corte01.final.edl.json
         [--max-pause 0.45] [--pad 0.12] [--no-fillers]

Cada segmento ganha "parts": [{"start", "end", "words": [índices]}] — os trechos efetivamente usados.
"""
import argparse
import copy
import subprocess

from common import load_json, norm_word, save_json, tc

# atenção: "um"/"uma" são artigos em português — nunca tratar como hesitação
FILLERS = {"ahn", "aham", "han", "hum", "hmm", "hm", "uhm", "eh", "ee", "eee", "ehh", "ããã", "aa", "aaa"}
MIN_PART = 0.30


def is_filler(word):
    raw = word.strip().lower()
    if raw.startswith(("é...", "éé", "ée", "e...", "ã...", "ah...")):
        return True
    return norm_word(raw) in FILLERS


def overlaps(a0, a1, ranges):
    return any(a0 < r1 and a1 > r0 for r0, r1 in ranges)


def within(a0, a1, ranges, tol=0.05):
    return any(a0 >= r0 - tol and a1 <= r1 + tol for r0, r1 in ranges)


def tighten(edl, words, max_pause, pad, remove_fillers):
    drop = [tuple(r) for r in edl.get("drop_words", [])]
    keep = [tuple(r) for r in edl.get("keep_pauses", [])]
    out_segments, report = [], []
    for si, seg in enumerate(edl["segments"]):
        s0, s1 = float(seg["start"]), float(seg["end"])
        # palavras cujo centro cai dentro do segmento
        idx = [w["i"] for w in words if s0 - 0.05 <= (w["start"] + w["end"]) / 2 <= s1 + 0.05]
        if not idx:
            # sem palavras (ex.: segmento só de imagem) — mantém como está
            out_segments.append({**seg, "parts": [{"start": s0, "end": s1, "words": []}]})
            continue
        removed = []
        kept = []
        for i in idx:
            w = words[i]
            mid = (w["start"] + w["end"]) / 2
            if overlaps(mid - 0.001, mid + 0.001, drop) or (remove_fillers and is_filler(w["word"])):
                removed.append(i)
            else:
                kept.append(i)
        # agrupa palavras mantidas em trechos contínuos
        runs, cur = [], []
        for i in kept:
            if cur:
                prev = cur[-1]
                gap = words[i]["start"] - words[prev]["end"]
                removed_between = any(prev < r < i for r in removed)
                long_gap = gap > max_pause and not within(words[prev]["end"], words[i]["start"], keep)
                if removed_between or long_gap:
                    runs.append(cur)
                    cur = []
            cur.append(i)
        if cur:
            runs.append(cur)

        parts = []
        for run in runs:
            first, last = words[run[0]], words[run[-1]]
            # limites: não invadir a palavra anterior/posterior da fonte (mantida ou removida)
            lo = words[run[0] - 1]["end"] if run[0] > 0 else 0.0
            hi = words[run[-1] + 1]["start"] if run[-1] + 1 < len(words) else last["end"] + 1e9
            # margem "pad", mas nunca além do meio do intervalo até a palavra vizinha
            start = max(first["start"] - pad, (lo + first["start"]) / 2, 0.0)
            end = min(last["end"] + pad, (last["end"] + hi) / 2)
            # o primeiro/último trecho respeita o recorte pedido, sem cortar sílabas
            if run is runs[0]:
                start = max(start, min(s0, first["start"] - 0.02))
            if run is runs[-1]:
                end = min(end, max(s1, last["end"] + 0.02))
            if end - start < MIN_PART:  # estende para dentro do silêncio, sem invadir vizinhos
                need = (MIN_PART - (end - start)) / 2
                start = max((lo + first["start"]) / 2, start - need, 0.0)
                end = min((last["end"] + hi) / 2, end + need)
            parts.append({"start": round(start, 3), "end": round(end, 3), "words": run})

        # evita sobreposição entre trechos consecutivos
        for a, b in zip(parts, parts[1:]):
            if b["start"] < a["end"]:
                m = round((a["end"] + b["start"]) / 2, 3)
                a["end"], b["start"] = m, m
        merged = []
        for p in parts:
            if merged and abs(p["start"] - merged[-1]["end"]) < 0.005:
                merged[-1]["end"] = p["end"]
                merged[-1]["words"] += p["words"]
            else:
                merged.append(p)

        new = copy.deepcopy(seg)
        new["parts"] = merged
        new["start"], new["end"] = merged[0]["start"], merged[-1]["end"]
        out_segments.append(new)
        before = s1 - s0
        after = sum(p["end"] - p["start"] for p in merged)
        report.append((si, seg.get("role", ""), before, after, len(merged),
                       [words[i]["word"] for i in removed]))
    return out_segments, report


_AIDX = {}


def _amap(src):
    """-map da faixa de áudio legível (iPhone grava também APAC, que o ffmpeg não decodifica)."""
    if src not in _AIDX:
        from common import probe
        _AIDX[src] = (probe(src).get("audio") or {}).get("index", 0)
    return ["-map", f"0:a:{_AIDX[src]}"]


def snap_to_breath(src, t, back=0.45, fwd=0.05):
    """Ajusta um ponto de corte para o instante de menor energia (respiro) logo antes de t.
    Os tempos por palavra da transcrição são estimados; sem isso a 1ª sílaba pode ser cortada."""
    import numpy as np
    a = max(0.0, t - back)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{back + fwd:.3f}", "-i", src, *_amap(src),
                          "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], stdout=subprocess.PIPE).stdout
    x = np.frombuffer(raw, np.float32)
    hop = 160
    n = len(x) // hop
    if n < 5:
        return t
    r = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    r = np.convolve(r, np.ones(3) / 3, mode="same")
    return round(a + int(np.argmin(r)) * hop / 16000, 3)


def snap_end(src, t, hi, fwd=0.5):
    """Estende o fim do trecho até a voz realmente acabar (cauda da última sílaba), sem passar de hi."""
    import numpy as np
    b = min(t + fwd, hi - 0.03)
    a = t - 0.05
    if b - a < 0.08:
        return t
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src, *_amap(src),
                          "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], stdout=subprocess.PIPE).stdout
    x = np.frombuffer(raw, np.float32)
    hop = 160
    n = len(x) // hop
    if n < 5:
        return t
    r = np.convolve(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12), np.ones(3) / 3, mode="same")
    thr = r.min() + 0.12 * (r.max() - r.min())
    k0 = int(np.argmax(r[:max(1, n // 2)]))
    after = np.flatnonzero(r[k0:] < thr)
    k = k0 + (int(after[0]) if len(after) else n - 1 - k0)
    return round(min(a + k * hop / 16000 + 0.06, hi - 0.02), 3)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edl")
    ap.add_argument("transcript")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--max-pause", type=float)
    ap.add_argument("--pad", type=float)
    ap.add_argument("--no-fillers", action="store_true")
    a = ap.parse_args()

    edl = load_json(a.edl)
    tr = load_json(a.transcript)
    words = tr["words"]
    for i, w in enumerate(words):
        w["i"] = i
    cfg = edl.get("tighten", {})
    max_pause = a.max_pause if a.max_pause is not None else cfg.get("max_pause", 0.45)
    pad = a.pad if a.pad is not None else cfg.get("pad", 0.12)
    fillers = False if a.no_fillers else cfg.get("remove_fillers", True)

    segs, report = tighten(edl, words, max_pause, pad, fillers)
    # início de cada trecho no respiro real do áudio (evita cortar a 1ª sílaba)
    try:
        from common import resolve_source
        src = resolve_source(edl, a.edl)
        for sg in segs:
            for p in sg["parts"]:
                if p["words"]:
                    i0 = p["words"][0]
                    w0 = words[i0]
                    # procura o respiro só entre a palavra anterior e a primeira palavra do trecho
                    gap = w0["start"] - words[i0 - 1]["end"] if i0 > 0 else 0.45
                    back = min(0.45, max(0.10, gap + 0.06))
                    p["start"] = min(p["start"], snap_to_breath(src, w0["start"], back=back))
                    # fim: espera a última palavra terminar de verdade (não corta o final da fala)
                    il = p["words"][-1]
                    hi = words[il + 1]["start"] if il + 1 < len(words) else words[il]["end"] + 0.6
                    p["end"] = max(p["end"], snap_end(src, words[il]["end"], hi))
            for a_, b_ in zip(sg["parts"], sg["parts"][1:]):  # trechos vizinhos não se sobrepõem
                if b_["start"] < a_["end"]:
                    a_["end"] = b_["start"]
            sg["start"], sg["end"] = sg["parts"][0]["start"], sg["parts"][-1]["end"]
    except SystemExit:
        print("AVISO: fonte não encontrada — inícios não ajustados ao áudio.")
    out = dict(edl)
    out["segments"] = segs
    out["tightened"] = {"max_pause": max_pause, "pad": pad, "remove_fillers": fillers}
    save_json(out, a.out)

    tb = ta = 0
    print(f"{'seg':>3} {'papel':<6} {'antes':>7} {'depois':>7} {'trechos':>7}  removido")
    for si, role, b, af, n, rem in report:
        tb += b
        ta += af
        print(f"{si:>3} {role:<6} {b:7.2f} {af:7.2f} {n:7d}  {' '.join(rem) if rem else '-'}")
    print(f"Total: {tb:.2f}s → {ta:.2f}s  (−{tb - ta:.2f}s, {100 * (tb - ta) / tb if tb else 0:.0f}%)")
    if ta > 90:
        print("ALERTA: corte acima de 90 s — considere enxugar ou dividir.")
    elif ta < 15:
        print("ALERTA: corte abaixo de 15 s.")
    print(f"EDL final: {a.out}")
    for s in segs:
        if s.get("role") == "hook":
            print(f"Hook começa em {tc(s['start'])} (fonte).")
            break


if __name__ == "__main__":
    main()
