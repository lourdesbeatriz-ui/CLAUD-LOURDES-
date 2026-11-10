"""Alinhamento de palavras por sílaba (sem modelo de alinhamento).

O Whisper ONNX devolve só o texto de cada trecho de fala. Para a legenda acompanhar a voz, cada
palavra é ancorada nos núcleos silábicos reais do áudio (picos de energia na faixa da voz):
conta-se as sílabas de cada palavra (grupos de vogais) e distribui-se as sílabas, em ordem,
pelos picos detectados no trecho. Sem picos suficientes, cai no rateio por energia.

Uso direto (refaz os tempos de uma transcrição existente, mantendo o texto corrigido):
  python3 align.py transcricao.json video.MOV -o transcricao_alinhada.json
"""
import argparse
import re
import subprocess

import numpy as np

SR, HOP, WIN = 16000, 160, 400  # 10 ms / 25 ms
VOWELS = "aeiouáéíóúâêôãõàüy"


def syllables(word):
    w = word.lower()
    digits = re.sub(r"\D", "", w)
    letters = re.sub(r"[^a-záéíóúâêôãõàüç]", "", w)
    n = len(re.findall(f"[{VOWELS}]+", letters))
    if digits:
        n += max(1, int(round(1.5 * len(digits))))
    return max(1, n)


def _band_energy_db(x):
    n = max(0, (len(x) - WIN) // HOP + 1)
    if n < 3:
        return np.zeros(0)
    idx = np.arange(WIN)[None, :] + HOP * np.arange(n)[:, None]
    fr = x[idx] * np.hanning(WIN)[None, :]
    spec = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    f = np.fft.rfftfreq(WIN, 1 / SR)
    band = spec[:, (f >= 300) & (f <= 2500)].sum(1)
    db = 10 * np.log10(band + 1e-10)
    return np.convolve(db, np.ones(3) / 3, mode="same")


def nuclei(x):
    """Tempos (s, relativos ao trecho) dos núcleos silábicos e a curva de energia."""
    e = _band_energy_db(x)
    if len(e) < 5:
        return [], e
    floor = np.percentile(e, 20)
    top = np.percentile(e, 97)
    thr = floor + 0.35 * (top - floor)
    cand = [i for i in range(len(e)) if e[i] >= thr and e[i] == e[max(0, i - 5):i + 6].max()]
    peaks = []
    for i in cand:  # funde picos sem vale de ao menos 2 dB entre eles
        if peaks and e[peaks[-1]:i + 1].min() > min(e[peaks[-1]], e[i]) - 2.0:
            if e[i] > e[peaks[-1]]:
                peaks[-1] = i
            continue
        peaks.append(i)
    return [(p * HOP + WIN / 2) / SR for p in peaks], e


def voiced_bounds(e):
    if not len(e):
        return 0.0, 0.0
    floor = np.percentile(e, 20)
    v = np.flatnonzero(e > floor + 6)
    if not len(v):
        return 0.0, len(e) * HOP / SR
    return v[0] * HOP / SR, (v[-1] * HOP + WIN) / SR


def align_chunk(samples, t0, toks):
    """[(start, end)] absolutos para cada token do trecho que começa em t0."""
    dur = len(samples) / SR
    pk, e = nuclei(samples)
    vb0, vb1 = voiced_bounds(e)
    syl = [syllables(t) for t in toks]
    S = sum(syl)
    if len(pk) >= max(2, 0.45 * S):
        P = len(pk)
        pidx = lambda k: pk[int(round(k * (P - 1) / max(1, S - 1)))]
        out, k = [], 0
        for s in syl:
            out.append((pidx(k), pidx(k + s - 1)))
            k += s
        res = []
        for j, (a, b) in enumerate(out):
            prev_b = out[j - 1][1] if j else None
            next_a = out[j + 1][0] if j + 1 < len(out) else None
            st = a - (min(0.12, 0.5 * (a - prev_b)) if prev_b is not None else 0.14)
            en = b + (min(0.16, 0.5 * (next_a - b)) if next_a is not None else 0.2)
            res.append([max(st, vb0 - 0.03, 0.0), min(en, max(vb1 + 0.05, b + 0.08), dur)])
        for j in range(1, len(res)):  # sem sobreposição; respeita a ordem
            res[j][0] = max(res[j][0], res[j - 1][1] - 0.01)
            res[j][1] = max(res[j][1], res[j][0] + 0.08)
        return [(round(t0 + s, 3), round(t0 + en, 3)) for s, en in res]
    # poucos picos: rateio pela energia (comportamento antigo)
    n = len(samples) // HOP
    rms = np.sqrt(np.mean(samples[:n * HOP].reshape(n, HOP) ** 2, axis=1) + 1e-12) if n else np.array([1.0])
    voiced = (rms > max(np.percentile(rms, 30) * 1.2, 1e-4)).astype(float)
    if voiced.sum() < 3:
        voiced[:] = 1
    cum = np.concatenate([[0], np.cumsum(voiced)]) / voiced.sum()
    wts = np.array(syl, dtype=float)
    fr = np.concatenate([[0], np.cumsum(wts)]) / wts.sum()
    at = lambda f: t0 + min(int(np.searchsorted(cum, f, side="left")), n) * HOP / SR
    return [(round(at(fr[j] + 1e-6), 3), round(max(at(fr[j + 1]), at(fr[j] + 1e-6) + 0.08), 3))
            for j in range(len(toks))]


def load_audio(path, stream=None):
    m = ["-map", f"0:a:{stream}"] if stream is not None else []
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", path, *m, "-vn", "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], stdout=subprocess.PIPE, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def realign(data, media):
    from common import probe
    idx = (probe(media).get("audio") or {}).get("index")
    audio = load_audio(media, idx)
    W = data["words"]
    for s in data["segments"]:
        a, b = int(s["start"] * SR), int(s["end"] * SR)
        ids = list(range(s["w0"], s["w1"] + 1))
        toks = [W[i]["word"] or "x" for i in ids]
        for i, (st, en) in zip(ids, align_chunk(audio[a:b], s["start"], toks)):
            W[i]["start"], W[i]["end"] = st, en
    return data


def main():
    from common import load_json, save_json
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcript")
    ap.add_argument("media")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    data = realign(load_json(a.transcript), a.media)
    data["aligned"] = "syllable"
    save_json(data, a.out)
    print(f"Tempos realinhados por sílaba: {a.out}")


if __name__ == "__main__":
    main()
