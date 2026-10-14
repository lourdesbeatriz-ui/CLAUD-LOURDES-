# Skills — Lourdes

## Editor Profissional de Cortes de Aula — Alta Retenção

Skill em [`.claude/skills/editor-cortes-aula/`](.claude/skills/editor-cortes-aula/SKILL.md) que transforma gravações de aulas, mentorias e palestras em cortes verticais (Reels, TikTok, Shorts) com hook forte, limpeza de silêncios e vícios de linguagem, legendas dinâmicas revisadas, tratamento de imagem e áudio e exportação 1080×1920 H.264.

- **Claude Code:** a skill é carregada automaticamente neste repositório. Basta enviar o vídeo e pedir "faça um corte desta aula".
- **claude.ai (app/web):** envie o arquivo `dist/editor-cortes-aula.zip` em *Configurações → Capacidades → Skills → Enviar skill*.

Estrutura:

| Arquivo | Função |
|---|---|
| `SKILL.md` | Instruções permanentes, regras invioláveis e fluxo de trabalho |
| `references/edl-formato.md` | Formato da lista de cortes (EDL) |
| `references/legendas.md` | Padrão de legendas, revisão e área segura |
| `references/imagem-audio-exportacao.md` | Valores de imagem, áudio e exportação |
| `references/checklist-qa.md` | Revisão obrigatória antes da entrega |
| `references/plano-de-edicao-template.md` | Plano detalhado quando não for possível exportar |
| `scripts/analyze.py` | Metadados, loudness, silêncios, frames para enquadramento |
| `scripts/transcribe.py` | Transcrição com tempo por palavra (faster-whisper) |
| `scripts/tighten.py` | Remove pausas, hesitações e palavras marcadas |
| `scripts/captions.py` | Legendas `.ass` dinâmicas + `.srt` |
| `scripts/render.py` | Cortes, 9:16, cor, áudio (−14 LUFS), legendas, MP4 |
| `scripts/qa.py` | Revisão técnica + frames de controle com área segura |

Requisitos: `ffmpeg` com libass, Python 3 e `pip install faster-whisper` para transcrever.
