# Template — Plano de Edição (quando não for possível exportar o vídeo)

> Deixe claro no topo: **"Este é um plano de edição. O vídeo ainda não foi editado."**

---

## Corte 01 — <título interno>

**Objetivo:** <ideia central em 1 frase>
**Plataforma:** Reels / TikTok / Shorts · **Formato:** 1080×1920, 9:16
**Duração estimada:** <ex.: 42 s> · **Potencial de retenção:** <nota 1–10 e por quê>

### 1. Hook (0:00–0:03)
- **Fala de abertura (literal):** "<frase exata>" — fonte `00:30:34.200 → 00:30:39.850`
- **Texto na tela (opcional):** "<até 8 palavras, fiel ao conteúdo>" — topo, 0–3 s
- **Por que funciona:** <quebra de crença / pergunta / dado / dor>

### 2. Tabela de cortes (ordem final)
| # | IN (fonte) | OUT (fonte) | Conteúdo | Ação | Observação |
|---|---|---|---|---|---|
| 1 | 00:30:34.200 | 00:30:39.850 | "…" | Hook | Começar sem respiração |
| 2 | 00:30:01.100 | 00:30:33.900 | "…" | Manter | Remover pausas > 0,45 s |
| 3 | 00:30:40.000 | 00:31:01.400 | "…" | Manter | Punch-in 108% para disfarçar jump cut |

### 3. Remoções dentro dos trechos
| Timecode (fonte) | O que sai | Motivo |
|---|---|---|
| 00:30:12.310–00:30:12.620 | "é…" | Hesitação |
| 00:30:20.050–00:30:20.900 | "o contrato, o contrato" → manter só 1 | Repetição |

**Pausas estratégicas a manter:** 00:30:39.850–00:30:40.600 (antes da conclusão).

### 4. Legendas (SRT revisado — tempos do vídeo final)
```
1
00:00:00,000 --> 00:00:01,400
O banco não pode

2
00:00:01,400 --> 00:00:02,600
cobrar isso de você.
```
**Palavras-chave em destaque:** <lista>
**Estilo:** Inter/Montserrat Bold ~70 px, branco, contorno 5 px, destaque `#FFC94A`, base da legenda em y≈1330.

### 5. Imagem
- Recorte 9:16 centrado no rosto (≈<x>% da largura); <ou fundo desfocado se houver slide>.
- Contraste +6%, saturação +7%, brilho +0,01; temperatura <±>; denoise leve; nitidez sutil.

### 6. Áudio
- Passa-alta 80 Hz · redução de ruído moderada · EQ -2,5 dB @250 Hz, +2,5 dB @3 kHz · de-esser · compressão 3:1 · normalizar -14 LUFS / TP -1,5 dBTP.
- Música: <nenhuma | trilha X a -24 dB com ducking>.

### 7. Exportação
MP4 · H.264 High · 1080×1920 · <fps da fonte> · CRF 17 / ~12–20 Mbps · AAC 320 kbps 48 kHz.

### 8. Instruções por editor (se o usuário indicar)
- **CapCut:** <passos: Dividir nos timecodes, Excluir, Legendas automáticas → revisar texto, Estilo, Ajustar → Redução de ruído, Exportar 1080p/fps da fonte>
- **Premiere / DaVinci:** <sequência 1080×1920, Essential Sound "Diálogo", Lumetri leve, exportar H.264 alta taxa>

### 9. Pontos de atenção
- <grafias a confirmar, trechos com áudio ruim, dependência de slide etc.>
