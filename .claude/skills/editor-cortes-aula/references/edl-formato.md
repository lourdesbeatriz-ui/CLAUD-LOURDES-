# Formato do EDL (lista de decisões de edição)

O EDL é um JSON que descreve **um corte**. Você o escreve depois de ler a transcrição; os scripts `tighten.py`, `captions.py` e `render.py` o consomem. Todos os tempos são em **segundos da gravação original** (fonte), exceto quando indicado.

```json
{
  "source": "../aula.mp4",
  "title": "Juros abusivos: o erro que todo empresário comete",

  "segments": [
    {"start": 1834.20, "end": 1839.85, "role": "hook"},
    {"start": 1801.10, "end": 1833.90},
    {"start": 1840.00, "end": 1861.40, "zoom": 1.08}
  ],

  "drop_words": [[1812.31, 1812.62], [1820.05, 1820.90]],
  "keep_pauses": [[1839.85, 1840.60]],

  "layout": "crop",
  "crop_x": 0.47,
  "crop_y": 0.5,

  "hook_text": "O banco não pode cobrar isso de você",
  "highlight": ["juros", "abusivos", "STJ", "contrato"],
  "overlays": [
    {"text": "Súmula 382 do STJ", "start": 12.4, "end": 15.0}
  ],

  "style": {
    "font": "Inter",
    "font_size": 70,
    "accent": "#FFC94A",
    "text_color": "#FFFFFF",
    "caption_y": 1330,
    "max_chars": 22,
    "mode": "ativo"
  },

  "audio_preset": "padrao",
  "video_preset": "padrao",
  "music": null,

  "tighten": {"max_pause": 0.45, "pad": 0.12, "remove_fillers": true}
}
```

## Campos

| Campo | Obrigatório | Descrição |
|---|---|---|
| `source` | sim | Caminho do vídeo original (relativo ao arquivo EDL ou absoluto). |
| `segments` | sim | Trechos **na ordem em que aparecem no corte final**. `start`/`end` na fonte. `role: "hook"` marca a abertura. `zoom` (1.0–1.15) aplica punch-in sutil no segmento. |
| `drop_words` | não | Intervalos `[ini, fim]` (fonte) a remover dentro dos segmentos — repetições, falsos começos, vícios que você decidiu tirar. Use os tempos exatos das palavras da transcrição. |
| `keep_pauses` | não | Intervalos de pausa estratégica que o `tighten.py` **não** deve encurtar. |
| `layout` | não | `crop` (padrão; recorte 9:16 no rosto) ou `blur` (quadro inteiro centralizado sobre fundo desfocado — para slides/lousa). Fonte já vertical: só escala. |
| `crop_x`, `crop_y` | não | Centro do recorte (0–1) na fonte. `crop_x` = posição horizontal do rosto. Use os frames de `analyze.py` para estimar. |
| `hook_text` | não | Texto de abertura (0–3 s) no topo da área segura. Fiel ao conteúdo. |
| `hook_duration` | não | Duração do `hook_text` em s (padrão 3.0). |
| `highlight` | não | Palavras-chave (sem acento/maiúsculas importam pouco: a comparação é normalizada) destacadas na cor `accent`. |
| `overlays` | não | Textos de apoio; `start`/`end` em **segundos do vídeo final**. |
| `style` | não | Identidade visual. Reutilize o mesmo bloco em todos os cortes da série. `mode`: `ativo` (palavra falada destacada) ou `estatico` (só palavras-chave). |
| `audio_preset` | não | `leve`, `padrao`, `forte` (intensidade de denoise/EQ/compressão). |
| `video_preset` | não | `nenhum`, `leve`, `padrao` (correção de cor/denoise/nitidez). Ajustes finos: `video_adjust: {"brightness":0.02,"contrast":1.05,"saturation":1.06,"gamma":1.0,"temperature":0}` (`temperature` em -1…1: negativo esfria, positivo aquece). |
| `music` | não | `{"path": "trilha.mp3", "db": -24}` — só com trilha licenciada. Ducking automático. |
| `tighten` | não | Parâmetros do `tighten.py`. |
| `fps` | não | Força fps de saída; padrão = fps da fonte (máx. 60). |

## O que o `tighten.py` faz

1. Encaixa `start`/`end` de cada segmento nas fronteiras de palavra (com `pad`), para não truncar sílabas.
2. Remove `drop_words` e, se `remove_fillers`, hesitações puras ("ahn", "hã", "éé", "hum", "hmm", "uh", "eh") isoladas.
3. Encurta pausas internas maiores que `max_pause` (mantendo `pad` de respiro de cada lado), exceto as de `keep_pauses`.
4. Descarta sub-trechos menores que 0,30 s (funde com o vizinho quando possível).
5. Grava `segments` finais (com `parts`) e um relatório de tempo economizado.

O EDL final (`*.final.edl.json`) é o que vai para `captions.py` e `render.py`.

## Layout "split" (duas telas) — padrão da série

```json
{
  "layout": "split",
  "split": {"top_h": 1020, "handle": "@perfil"},
  "crop_x": 0.5, "crop_y": 0.42,
  "panel": [
    {"start": 0, "end": 5.5, "type": "texto", "kicker": "Insight 01",
     "title": "Juros sobre juros", "subtitle": "têm limite legal",
     "body": "O que o contrato diz nem sempre é o que a lei permite."},
    {"start": 5.5, "end": 11, "type": "video", "path": "broll/assinatura.mp4", "source_start": 2.0,
     "label": "Contrato de empréstimo"},
    {"start": 11, "end": 16, "type": "imagem", "path": "broll/tribunal.jpg",
     "kicker": "Jurisprudência", "label": "Súmula 539 do STJ"}
  ]
}
```

- `panel[].start/end`: segundos **do vídeo final**. Tipos: `texto` (cartão), `imagem` (Ken Burns lento; `zoom` 1.05–1.15), `video` (take sem áudio; `source_start` = ponto inicial do take; `saturation`).
- Entre elementos, aparece o fundo creme com ornamento e `handle`.
- Legendas: o `captions.py` aplica automaticamente o estilo limpo do split (Jost Medium 54, branco, sombra suave, sem destaque) e posiciona a base em `top_h - 60`.
- `hook_text` é ignorado no split — use o primeiro cartão do painel como hook visual.
- Tema: `"theme": {"bordo": "#6B1E2E", ...}` sobrescreve cores (ver `scripts/panel.py`).
