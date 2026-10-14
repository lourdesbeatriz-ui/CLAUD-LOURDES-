"""Funções compartilhadas pelos scripts da skill editor-cortes-aula."""
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from fractions import Fraction


def die(msg):
    print(f"ERRO: {msg}", file=sys.stderr)
    sys.exit(1)


def require(*tools):
    for t in tools:
        if shutil.which(t) is None:
            die(f"'{t}' não encontrado no PATH. Instale-o (ex.: apt-get install ffmpeg).")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def resolve_source(edl, edl_path):
    src = edl.get("source")
    if not src:
        die("EDL sem campo 'source'.")
    if not os.path.isabs(src):
        src = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(edl_path)), src))
    if not os.path.exists(src):
        die(f"Vídeo de origem não encontrado: {src}")
    return src


def run(cmd, capture=False, check=True):
    res = subprocess.run(cmd, stdout=subprocess.PIPE if capture else None,
                         stderr=subprocess.PIPE if capture else None, text=True)
    if check and res.returncode != 0:
        tail = (res.stderr or "")[-3000:] if capture else ""
        die(f"comando falhou ({res.returncode}): {' '.join(cmd[:6])} ...\n{tail}")
    return res


def probe(path):
    """Retorna informações essenciais do arquivo (dimensões já corrigidas pela rotação)."""
    require("ffprobe")
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
               "-show_streams", path], capture=True).stdout
    data = json.loads(out)
    v = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    a = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    info = {"path": path, "duration": float(data["format"].get("duration", 0) or 0),
            "size_bytes": int(data["format"].get("size", 0) or 0), "video": None, "audio": None}
    if v:
        w, h = int(v["width"]), int(v["height"])
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(float(sd["rotation"]))
        if not rot and "rotate" in (v.get("tags") or {}):
            rot = int(v["tags"]["rotate"])
        if abs(rot) % 180 == 90:
            w, h = h, w
        fr = v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1"
        try:
            fps = Fraction(fr) if Fraction(fr) > 0 else Fraction(v.get("r_frame_rate", "30/1"))
        except (ZeroDivisionError, ValueError):
            fps = Fraction(30, 1)
        info["video"] = {"width": w, "height": h, "rotation": rot, "codec": v.get("codec_name"),
                         "pix_fmt": v.get("pix_fmt"), "fps": float(fps), "fps_str": fr,
                         "r_frame_rate": v.get("r_frame_rate"), "profile": v.get("profile"),
                         "bit_rate": int(v.get("bit_rate", 0) or 0)}
    if a:
        info["audio"] = {"codec": a.get("codec_name"), "sample_rate": int(a.get("sample_rate", 0) or 0),
                         "channels": a.get("channels"), "bit_rate": int(a.get("bit_rate", 0) or 0)}
    return info


def output_fps(info, forced=None):
    """FPS de saída: o da fonte, limitado a 60, como fração string para o ffmpeg."""
    if forced:
        return str(forced)
    v = info["video"]
    candidates = [v.get("r_frame_rate"), v.get("fps_str")]
    for c in candidates:
        try:
            f = Fraction(c)
            if 10 <= f <= 61:
                return f"{f.numerator}/{f.denominator}"
        except (TypeError, ValueError, ZeroDivisionError):
            continue
    return "60/1" if v["fps"] > 60 else f"{Fraction(v['fps']).limit_denominator(1001)}"


def tc(t):
    """Segundos -> hh:mm:ss.mmm"""
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def norm_word(w):
    """minúsculas, sem acento e sem pontuação — para comparações."""
    w = unicodedata.normalize("NFKD", w.lower())
    w = "".join(c for c in w if not unicodedata.combining(c))
    return re.sub(r"[^\w%$]", "", w)


def find_font_file(name="Inter", weight="Bold"):
    if shutil.which("fc-match") is None:
        return None
    r = subprocess.run(["fc-match", "-f", "%{file}", f"{name}:style={weight}"],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    return r.stdout.strip() or None
