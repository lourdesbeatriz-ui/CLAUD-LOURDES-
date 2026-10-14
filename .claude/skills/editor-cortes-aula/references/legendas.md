# Legendas profissionais — padrão da skill

## 1. Revisão do texto (obrigatória, antes de gerar o .ass)

Edite o campo `"word"` das palavras em `transcricao.json` (ou rode `captions.py --fix "errado=>certo"` repetidas vezes). Não altere `start`/`end`.

Checklist de revisão:
- **Pontuação e acentuação** completas (vírgulas de vocativo, ponto de interrogação em perguntas, crase).
- **Maiúsculas**: início de frase, nomes próprios, instituições (Banco Central, Supremo Tribunal Federal).
- **Siglas**: STJ, STF, CDC, CPC, CLT, CTN, BACEN, CMN, CNJ, OAB, CNPJ, CPF, LGPD, PIX, CET, IOF, TR, IPCA, Selic, CDI.
- **Números**: "art. 54", "§ 2º", "inciso III", "Lei 14.181/2021", "Súmula 382", "R$ 10 mil", "5% ao mês", "30 dias". Prefira algarismos para dados, valores e prazos.
- **Termos jurídicos/técnicos**: anatocismo, capitalização, revisional, tutela de urgência, superendividamento, recuperação judicial, busca e apreensão, alienação fiduciária etc.
- **Nomes do professor, escritório e marcas** — confirme com o usuário se houver dúvida.
- Hesitações e palavras removidas pelo `tighten.py` não aparecem nas legendas (o script já filtra).
- Nunca "corrigir" o conteúdo do que o professor disse — apenas a grafia.

Se não tiver certeza de uma grafia, liste-a em "Pontos de atenção" na entrega.

## 2. Diagramação

- Fonte: **Inter Bold/ExtraBold** (instalada) ou Montserrat Bold/ExtraBold se disponível; corpo ~66–76 px (padrão 70) em 1080×1920.
- 1 linha preferencial, no máximo 2; até ~22 caracteres por linha (`max_chars`).
- Bloco de 0,8 a 2,5 s; quebra em pontuação ou pausa > 0,25 s.
- Não terminar linha com artigo, preposição ou conjunção solta ("de", "o", "que", "e").
- Contorno escuro 4–5 px + sombra suave (legível sobre qualquer fundo, sem caixa pesada).
- Caixa alta opcional apenas no `hook_text`; legendas em caixa normal (mais legíveis e sóbrias).

## 3. Destaque estratégico

- `mode: "ativo"`: a palavra sendo falada fica na cor de destaque — estilo dinâmico moderno.
- `mode: "estatico"`: somente as palavras de `highlight` ficam coloridas — mais sóbrio (bom para conteúdo jurídico formal).
- Palavras-chave (`highlight`) ficam na cor de destaque em ambos os modos. Use 1–2 por bloco: termos centrais, números, consequências ("nulo", "ilegal", "5 anos").
- Cor padrão de destaque: dourado `#FFC94A`. Substitua pela cor da marca do usuário e mantenha em toda a série.

## 4. Área segura (1080×1920, Reels/TikTok/Shorts)

```
y=0     ┌──────────────────────┐
        │  topo: evitar texto  │  0–220 px (status bar / nome do perfil)
y=220   │  hook_text aqui      │  220–520 px
        │                      │
        │   ROSTO (≈300–1000)  │
        │                      │
y=1150  │  legendas aqui       │  1150–1450 px (caption_y padrão 1330 = base do bloco)
y=1450  │                      │
        │ legenda do post/UI   │  1500–1920 px: evitar (descrição, botões, áudio)
y=1920  └──────────────────────┘
        margens laterais: 90 px esq., 140 px dir. (ícones de curtir/comentar)
```

- Se o rosto estiver baixo no quadro (ex.: professor sentado), suba o recorte com `crop_y` ou desça a legenda até no máximo `caption_y: 1450`.
- Nunca cobrir a boca. Confira nos frames de QA.

## 5. Sincronia

- Cada palavra entra no seu `start` (do Whisper com word timestamps); tolerância ≤ 100 ms.
- Blocos não se sobrepõem; o próximo começa quando o anterior termina.
- Após cortes, o `captions.py` remapeia tempos da fonte para o tempo do vídeo final — nunca escreva timecodes de legenda à mão quando os scripts estiverem disponíveis.
