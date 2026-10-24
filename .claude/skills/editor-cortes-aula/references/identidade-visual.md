# Identidade visual padrão da série (preferências da usuária)

Aplique este padrão a TODOS os cortes, salvo pedido diferente. Ele foi aprovado pela usuária.

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

- A professora fica **sempre em cima**. O painel de baixo **não é só texto**: mescle cartões de insight com **imagens e takes de vídeo** que ilustrem o que ela diz (ex.: contrato sendo assinado, fachada de banco/tribunal, calculadora, documentos, gráfico de juros).
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
