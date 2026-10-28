# Identidade visual padrão da série (preferências da usuária)

## Regras aprendidas com o feedback (OBRIGATÓRIAS)
1. **Na parte de baixo NUNCA use a professora** — nada de recortes do corpo, mãos, roupa ou rosto dela.
   O painel tem só cartões de texto centralizados e takes de objetos/ambiente centralizados
   (ex.: o troféu de xadrez da estante), ou imagens de banco quando disponíveis.
2. **Ela sempre centralizada na tela de cima**: rode `scripts/facecenter.py` no EDL final e use
   `base_zoom` ≈ 1.15–1.2 (fonte 4K permite sem perder nitidez).
3. **Frases fortes, não frases à toa**: escolha trechos com afirmações de impacto (quebra de crença,
   frase de efeito, conclusão), não frases de transição ou exemplos soltos.
4. **Pouco picote**: prefira blocos contínuos de fala (1–3 segmentos longos), removendo só pausas
   longas (`max_pause` ≈ 0.65, `pad` 0.15). Nada de montar frase com pedacinhos.
5. Cada elemento do painel deve estar **centralizado** (texto e objeto no centro do quadro).

Aplique este padrão a TODOS os cortes, salvo pedido diferente. Ele foi aprovado pela usuária.

## Formato "tela única" (quando a usuária pedir sem duas telas)
- `layout: "crop"`, `base_zoom` ≈ 1.22 + `facecenter.py --face-y 0.36` (rosto no terço superior, acompanhado).
- Iluminação: gravações do iPhone saem com altas luzes estouradas → `video_adjust`:
  `{"contrast":1.0,"saturation":1.03,"gamma":0.97,"curves":"0/0 0.25/0.24 0.5/0.47 0.75/0.69 0.9/0.81 1/0.9"}`.
- Legenda: Jost Medium 62, branca, centralizada (base y≈1420), sombra suave, sem destaque.
- Gancho: `hook_text` + `hook_kicker` com `style.hook_style: "elegante"` (Cormorant branca sendo escrita, 0–3 s).
  O título do gancho NÃO repete a fala — ele cria tensão/curiosidade complementar e fiel.
- Transição: punch-in sutil alternando `zoom` 1.0/1.07 entre blocos + whoosh discreto em cada corte
  (`sfx_auto`), soft hit na abertura.
- Áudio: `audio_preset: "limpo"`, `rnn_mix: 0.8`.

## Ganchos fortes (critério)
Comece pela frase mais contundente do trecho (ex.: "Você está rasgando dinheiro.", "Quanto você cobra
por R$ 1 milhão de dívida?"). Pode repetir a frase no fim como fechamento quando ela aparece de novo
naturalmente na fala. Evite começar por contexto ou transição.

## Formato: duas telas (`"layout": "split"`)

```
┌──────────────────────────┐ y=0
│                          │
│   PROFESSORA (vídeo)     │  tela de cima: 1080×1020, rosto centralizado
│                          │
│   legenda centralizada   │  base em y≈960, Jost Medium 54 px, branca
├──────────────────────────┤ y=1020
│  painel inferior creme   │  1080×900: alterna cartões de texto,
│  cartões · imagens ·     │  imagens (Ken Burns lento) e takes de vídeo
│  takes de vídeo          │  relacionados ao que ela está falando
└──────────────────────────┘ y=1920
```

- A professora fica **sempre em cima e só em cima**. O painel de baixo mescla cartões de insight com **imagens e takes de objetos/ambiente** que ilustrem o que ela diz (ex.: troféu de xadrez, contrato, fachada de banco/tribunal, calculadora, gráfico de juros) — **nunca ela**.
- Ritmo do painel: troque de elemento a cada ~4–7 s; comece com o cartão do insight (funciona como hook visual); alterne texto → take → imagem; volte a um cartão na conclusão.
- Rótulo discreto opcional sobre imagens/takes (`label`, `kicker`) — faixa creme translúcida, texto bordô.

## Legendas das falas
- **Sem marca-texto, sem caixa e sem palavra colorida** nas legendas da fala. Branco, Jost Medium, centralizado, com sombra suave (contorno translúcido desfocado), nada de contorno forte.
- Os destaques visuais ficam no painel (títulos), não na legenda.

## Paleta
| Nome | Hex | Uso |
|---|---|---|
| Bordô | `#6B1E2E` | títulos, rótulos |
| Marrom | `#5C4030` | subtítulo itálico, corpo |
| Caramelo | `#967058` | kicker, ornamentos, @perfil |
| Areia | `#E8DDD2` | apoios |
| Creme | `#F5EFE9` | fundo do painel |

## Tipografia (em `assets/fonts`, licença OFL — livre para uso comercial)
- Títulos: **Cormorant Garamond Medium** + **Medium Italic** no subtítulo.
- Legendas e textos: **Jost** (Medium nas legendas; Regular/Light nos textos).
- Nunca usar fontes "marcadas"/chamativas, nem contornos grossos, emojis ou efeitos.

## Cartão de insight (`panel` → `type: "texto"`)
Ornamento fino caramelo → `kicker` espaçado (ex.: "INSIGHT 01") → título serifado bordô → subtítulo itálico marrom → corpo leve (1–2 linhas). Texto sempre fiel ao que a professora disse.

## Imagens e takes (B-roll)
- Fontes permitidas: material da própria usuária, bancos com licença livre para uso comercial (Pexels, Pixabay, Unsplash, Mixkit, Coverr) ou domínio público (Wikimedia Commons, com crédito quando exigido). Registre a origem de cada arquivo em `broll/CREDITOS.txt`.
- Proibido: logos/marcas de bancos ou pessoas reais em contexto que sugira acusação; imagens com marca d'água; imagens que contradigam a fala; "ilustrar" fatos que ela não disse.
- Prefira takes sóbrios e com cor quente/neutra (combina com a paleta); saturação levemente reduzida (`saturation: 0.92`, padrão).
- Se não houver acesso a bancos de imagem, use somente cartões de texto e avise a usuária — não invente imagens.
