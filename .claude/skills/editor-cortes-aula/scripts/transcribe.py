#!/usr/bin/env python3
"""Transcreve a gravação com timestamps por palavra (faster-whisper ou openai-whisper).

Uso:
  python3 transcribe.py aula.mp4 -o proj/transcricao.json [--model large-v3] [--lang pt]
  python3 transcribe.py proj/transcricao.json --print [--words]   # leitura com timecodes
  python3 transcribe.py legenda.srt -o proj/transcricao.json      # importa SRT (tempo por palavra estimado)

Formato de saída:
  {"language": "pt", "source": "...", "words": [{"i": 0, "word": "Olá,", "start": 1.20, "end": 1.48, "prob": 0.98}, ...],
   "segments": [{"start": ..., "end": ..., "text": "...", "w0": 0, "w1": 12}]}

Para corrigir grafia, edite apenas o campo "word". Nunca altere start/end.
"""
import argparse
import os
import re
import sys

from common import die, load_json, save_json, tc


def transcribe_media(path, model_name, lang, device, initial_prompt):
    words, segs = [], []
    try:
        from faster_whisper import WhisperModel
        compute = "float16" if device == "cuda" else "int8"
        model = WhisperModel(model_name, device=device, compute_type=compute)
        it, _ = model.transcribe(path, language=lang, word_timestamps=True, beam_size=5,
                                 vad_filter=True, vad_parameters={"min_silence_duration_ms": 300},
                                 initial_prompt=initial_prompt, condition_on_previous_text=False)
        for s in it:
            w0 = len(words)
            for w in s.words or []:
                words.append({"word": w.word.strip(), "start": round(w.start, 3),
                              "end": round(w.end, 3), "prob": round(w.probability, 3)})
            segs.append({"start": round(s.start, 3), "end": round(s.end, 3),
                         "text": s.text.strip(), "w0": w0, "w1": len(words) - 1})
            print(f"[{tc(s.start)}] {s.text.strip()}", file=sys.stderr)
        return words, segs, "faster-whisper"
    except ImportError:
        pass
    try:
        import whisper
    except ImportError:
        die("Nenhum motor de transcrição instalado. Rode: pip install faster-whisper "
            "(ou envie uma transcrição/SRT com timestamps).")
    model = whisper.load_model(model_name)
    r = model.transcribe(path, language=lang, word_timestamps=True, initial_prompt=initial_prompt,
                         condition_on_previous_text=False, verbose=False)
    for s in r["segments"]:
        w0 = len(words)
        for w in s.get("words", []):
            words.append({"word": w["word"].strip(), "start": round(w["start"], 3),
                          "end": round(w["end"], 3), "prob": round(w.get("probability", 1.0), 3)})
        segs.append({"start": round(s["start"], 3), "end": round(s["end"], 3),
                     "text": s["text"].strip(), "w0": w0, "w1": len(words) - 1})
    return words, segs, "openai-whisper"


def transcribe_sherpa(path, model_dir, vad_path, lang, threads=4):
    """Alternativa sem Hugging Face: Whisper (ONNX, sherpa-onnx) + VAD Silero, ambos baixáveis do GitHub
    (github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models). O Whisper ONNX não dá tempo por palavra,
    então cada trecho de fala detectado pelo VAD (curto, ~1–6 s) tem suas palavras distribuídas
    proporcionalmente ao tamanho, apenas sobre os quadros com voz (energia) — erro típico < 150 ms."""
    import glob
    import subprocess
    import numpy as np
    import sherpa_onnx

    sr = 16000
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr),
                          "-f", "f32le", "-"], stdout=subprocess.PIPE, check=True).stdout
    audio = np.frombuffer(raw, dtype=np.float32).copy()
    enc = glob.glob(os.path.join(model_dir, "*encoder*.onnx"))[0]
    dec = glob.glob(os.path.join(model_dir, "*decoder*.onnx"))[0]
    tok = glob.glob(os.path.join(model_dir, "*tokens.txt"))[0]
    rec = sherpa_onnx.OfflineRecognizer.from_whisper(encoder=enc, decoder=dec, tokens=tok, language=lang,
                                                     num_threads=threads, tail_paddings=800)
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = vad_path
    cfg.silero_vad.threshold = 0.45
    cfg.silero_vad.min_silence_duration = 0.22
    cfg.silero_vad.min_speech_duration = 0.2
    cfg.silero_vad.max_speech_duration = 12
    cfg.sample_rate = sr
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=60)
    win = cfg.silero_vad.window_size
    chunks = []
    for i in range(0, len(audio), win):
        vad.accept_waveform(audio[i:i + win])
        while not vad.empty():
            chunks.append((vad.front.start, np.array(vad.front.samples, dtype=np.float32)))
            vad.pop()
    vad.flush()
    while not vad.empty():
        chunks.append((vad.front.start, np.array(vad.front.samples, dtype=np.float32)))
        vad.pop()

    hop = 160  # 10 ms
    words, segs = [], []
    for start, samples in chunks:
        st = rec.create_stream()
        st.accept_waveform(sr, samples)
        rec.decode_stream(st)
        text = st.result.text.strip()
        toks = text.split()
        if not toks:
            continue
        t0 = start / sr
        n = len(samples) // hop
        rms = np.sqrt(np.mean(samples[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12) if n else np.array([1.0])
        thr = max(np.percentile(rms, 30) * 1.2, 1e-4)
        voiced = (rms > thr).astype(float)
        if voiced.sum() < 3:
            voiced[:] = 1
        cum = np.concatenate([[0], np.cumsum(voiced)]) / voiced.sum()
        weights = np.array([len(x) + 1 for x in toks], dtype=float)
        fr = np.concatenate([[0], np.cumsum(weights)]) / weights.sum()
        def at(f):  # fração de "fala" -> tempo
            k = int(np.searchsorted(cum, f, side="left"))
            return t0 + min(k, n) * hop / sr
        w0 = len(words)
        for j, x in enumerate(toks):
            s, e = at(fr[j] + 1e-6), at(fr[j + 1])
            words.append({"word": x, "start": round(s, 3), "end": round(max(e, s + 0.08), 3), "prob": 0.8})
        segs.append({"start": round(t0, 3), "end": round(t0 + len(samples) / sr, 3), "text": text,
                     "w0": w0, "w1": len(words) - 1})
        print(f"[{tc(t0)}] {text}", file=sys.stderr)
    return words, segs, "sherpa-onnx-whisper"


def parse_srt(path):
    """Importa SRT; distribui o tempo de cada bloco entre as palavras proporcionalmente ao tamanho."""
    txt = open(path, encoding="utf-8-sig").read()
    blocks = re.split(r"\n\s*\n", txt.strip())
    words, segs = [], []
    t = lambda s: sum(float(x) * m for x, m in zip(s.replace(",", ".").split(":"), (3600, 60, 1)))
    for b in blocks:
        lines = b.strip().splitlines()
        m = next((re.match(r"(\S+)\s*-->\s*(\S+)", l) for l in lines if "-->" in l), None)
        if not m:
            continue
        s, e = t(m.group(1)), t(m.group(2))
        text = " ".join(l for l in lines[lines.index(m.string) + 1:]).strip()
        toks = text.split()
        if not toks:
            continue
        total = sum(len(x) + 1 for x in toks)
        cur, w0 = s, len(words)
        for x in toks:
            d = (e - s) * (len(x) + 1) / total
            words.append({"word": x, "start": round(cur, 3), "end": round(cur + d, 3), "prob": 0.5})
            cur += d
        segs.append({"start": s, "end": e, "text": text, "w0": w0, "w1": len(words) - 1})
    return words, segs


def print_transcript(data, show_words):
    W = data["words"]
    for s in data["segments"]:
        print(f"[{tc(s['start'])} → {tc(s['end'])}] {s['text']}")
        if show_words:
            print("   " + "  ".join(f"{W[i]['i']}:{W[i]['word']}@{W[i]['start']:.2f}"
                                    for i in range(s["w0"], s["w1"] + 1)))
    low = [w for w in W if w.get("prob", 1) < 0.5]
    if low:
        print(f"\n# {len(low)} palavras com baixa confiança (revise nas legendas):")
        print("  " + ", ".join(f"{w['word']}@{tc(w['start'])}" for w in low[:80]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="vídeo/áudio, transcricao.json ou .srt")
    ap.add_argument("-o", "--out")
    ap.add_argument("--model", default="large-v3", help="tiny|base|small|medium|large-v3 (padrão large-v3)")
    ap.add_argument("--lang", default="pt")
    ap.add_argument("--device", default="auto", help="cpu|cuda|auto")
    ap.add_argument("--prompt", default="Aula em português do Brasil. Termos: STJ, STF, CDC, CPC, BACEN, Selic, CDI.",
                    help="contexto/vocabulário para melhorar nomes e termos técnicos")
    ap.add_argument("--sherpa-dir", help="pasta do modelo Whisper ONNX (sherpa-onnx) — usa este motor")
    ap.add_argument("--vad", help="silero_vad.onnx (obrigatório com --sherpa-dir)")
    ap.add_argument("--print", action="store_true", help="imprime a transcrição com timecodes")
    ap.add_argument("--words", action="store_true", help="com --print, lista índice:palavra@tempo")
    a = ap.parse_args()

    if a.input.endswith(".json"):
        data = load_json(a.input)
    elif a.input.lower().endswith(".srt"):
        words, segs = parse_srt(a.input)
        data = {"language": a.lang, "source": a.input, "engine": "srt-import", "words": words, "segments": segs}
    else:
        if not os.path.exists(a.input):
            die(f"arquivo não encontrado: {a.input}")
        device = a.device
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        if a.sherpa_dir:
            if not a.vad:
                die("--vad é obrigatório com --sherpa-dir")
            words, segs, engine = transcribe_sherpa(a.input, a.sherpa_dir, a.vad, a.lang)
        else:
            words, segs, engine = transcribe_media(a.input, a.model, a.lang, device, a.prompt)
        data = {"language": a.lang, "source": os.path.abspath(a.input), "engine": engine,
                "model": a.model, "words": words, "segments": segs}
    for i, w in enumerate(data["words"]):
        w["i"] = i
    if a.out:
        save_json(data, a.out)
        print(f"Transcrição salva: {a.out}  ({len(data['words'])} palavras)", file=sys.stderr)
    if a.print or not a.out:
        print_transcript(data, a.words)


if __name__ == "__main__":
    main()
