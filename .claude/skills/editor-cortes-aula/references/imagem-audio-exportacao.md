# Imagem, áudio e exportação — valores de referência

Os valores abaixo são os usados por `scripts/render.py`. Ajuste via EDL quando o material pedir.

## Imagem

### Reenquadramento 9:16
- Fonte horizontal (16:9): recorte de largura `ih*9/16` centrado em `crop_x` (posição do rosto), escala para 1080×1920 com `lanczos`.
- Fonte com resolução baixa (altura < 1080): o recorte será ampliado; mantenha `video_preset: "leve"` e avise o usuário sobre o limite de nitidez.
- `layout: "blur"`: quadro inteiro escalado para 1080 de largura, centralizado, sobre cópia ampliada e desfocada (`gblur sigma≈40`, brilho -0,08). Use quando slide/lousa for essencial.
- Punch-in (`zoom` 1.05–1.12 por segmento) para disfarçar jump cuts e dar ritmo. Nunca acima de 1.15.

### Correção (presets)
| preset | eq (contraste / saturação / brilho) | denoise `hqdn3d` | nitidez `unsharp` |
|---|---|---|---|
| nenhum | — | — | — |
| leve | 1.03 / 1.04 / 0.00 | 1:1:4:4 | 5:5:0.3 |
| padrao | 1.06 / 1.07 / 0.01 | 1.5:1.5:6:6 | 5:5:0.45 |

- Balanço de branco: `video_adjust.temperature` (-1…1) aplica `colortemperature` relativo a 6500 K (±1500 K). Pele deve parecer natural — nem laranja, nem azulada.
- Exposição: `brightness` -0.05…+0.06; `gamma` 0.9–1.15 para recuperar sombras sem estourar.
- Proibido: filtros estilizados, LUTs fortes, suavização de pele, nitidez com halo.

## Áudio

Cadeia (`audio_preset`):

| etapa | leve | padrao | forte |
|---|---|---|---|
| highpass | 70 Hz | 80 Hz | 90 Hz |
| afftdn (nr / nf) | 8 / -30 | 12 / -28 | 18 / -25 |
| EQ 250 Hz | -1.5 dB | -2.5 dB | -3 dB |
| EQ 3 kHz (presença) | +1.5 dB | +2.5 dB | +3 dB |
| EQ 10 kHz (ar) | +0.5 dB | +1 dB | +1 dB |
| deesser | sim | sim | sim |
| acompressor | 2:1, thr -20 dB | 3:1, thr -22 dB | 4:1, thr -24 dB |

Depois: `loudnorm` em **duas passagens** → I = -14 LUFS, TP = -1.5 dBTP, LRA = 9; e `alimiter` de segurança em -1.0 dBFS.

- Junções: micro-fade de 10 ms em cada segmento (sem estalos).
- Se a voz soar "metálica"/"aquática", reduzir para `leve`. Se o ruído for muito forte, `forte` + aviso ao usuário.
- Música (`music`): volume padrão -24 dB, `sidechaincompress` (threshold 0.03, ratio 8, attack 20 ms, release 400 ms) com a voz como sidechain; fade-out de 1,5 s no fim.

## Exportação (padrão)

| parâmetro | valor |
|---|---|
| Resolução | 1080×1920 (9:16) |
| Container | MP4, `+faststart` |
| Vídeo | H.264 High, `yuv420p`, CRF 17, preset `slow`, `maxrate 20M` / `bufsize 40M`, GOP = 2 s |
| FPS | igual à fonte (23.976/25/29.97/30/50/60); acima de 60 → 60 |
| Áudio | AAC-LC 320 kbps, 48 kHz, estéreo |
| Cor | BT.709, faixa limitada (tv) |

YouTube Shorts aceita o mesmo arquivo. Para formatos 1:1 ou 4:5 (feed), ajustar `--size 1080x1080` ou `1080x1350` no `render.py` e a posição das legendas.
