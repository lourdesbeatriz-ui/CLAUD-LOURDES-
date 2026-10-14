# Checklist de revisão (QA) — obrigatório antes de entregar

Rode `scripts/qa.py` e depois confira manualmente (abra as imagens de `*_qa/`).

## Técnico (automático — `qa.py` aponta FALHA/ALERTA)
- [ ] 1080×1920, H.264 High, yuv420p, MP4 com faststart.
- [ ] FPS igual ao da fonte (ou 60 se a fonte for maior).
- [ ] Áudio AAC 48 kHz; loudness integrado entre -15 e -13 LUFS; true peak ≤ -1,0 dBTP; sem clipping.
- [ ] Duração dentro do alvo (15–90 s; ideal 30–60 s).
- [ ] Sem buraco de silêncio > 0,7 s no vídeo final (exceto pausas estratégicas marcadas).
- [ ] Legendas: nenhuma fora da área segura; nenhum bloco > 2 linhas; sem sobreposição.

## Conteúdo (você confere)
- [ ] O hook aparece com fala nos primeiros ~0,3 s e é forte sozinho.
- [ ] O corte tem começo, meio e fim; a ideia está completa e não depende de contexto ausente.
- [ ] Nenhuma junção altera o sentido; nada foi atribuído ao professor que ele não disse.
- [ ] `hook_text`/overlays fiéis ao conteúdo.
- [ ] Pausas estratégicas preservadas; nenhuma palavra truncada nas junções.

## Legendas (você confere lendo o .ass/.srt)
- [ ] Português impecável: acentos, crase, pontuação, maiúsculas.
- [ ] Nomes próprios, siglas, números, artigos de lei e termos técnicos corretos.
- [ ] Destaques com parcimônia e nas palavras certas.
- [ ] Sincronia conferida nos frames de controle (palavra ativa = palavra falada).

## Visual (frames de controle)
- [ ] Rosto bem enquadrado, olhos no terço superior, sem cortar queixo/topo da cabeça de forma estranha.
- [ ] Legenda não cobre boca nem elementos importantes; longe dos ícones do app.
- [ ] Cor natural da pele; sem estourar ou escurecer demais; sem ruído evidente.
- [ ] Identidade visual igual aos outros cortes da série.

Se qualquer item falhar: corrigir EDL/legenda/parâmetros → re-renderizar → rodar QA de novo. Só então entregar.
