# Instruções para o Claude: projeto AgriPrecisa

Complemento do QGIS com ferramentas de agricultura de precisão, de Gustavo Di Chiacchio Faulin (Fatec Pompeia "Shunji Nishimura"). Repositório: https://github.com/gdfaulin/AgriPrecisa

## Sobre o autor e como se comunicar

- Responder sempre em português do Brasil, em linguagem clara, sem travessões.
- O autor não é programador. **O Claude cuida de todo o git e do GitHub**; não pedir que ele rode comandos. Quando algo exigir ação dele (por exemplo, enviar o ZIP ao plugins.qgis.org), explicar passo a passo, pelo navegador.
- **Sempre fazer perguntas antes de implementar**, em formato de opções clicáveis, para entender as expectativas do autor e para sugerir melhorias. Mesmo quando o pedido parecer claro, perguntar sobre alternativas, detalhes de comportamento e melhorias possíveis antes de alterar o código.
- Regra permanente: **todo bug corrigido ganha um teste de regressão** (em `tests/` ou em `tests/integration/run_qgis_integration.py`).

## Propósito didático (vale para todos os complementos do autor)

Os complementos são usados em aula (por exemplo, Laboratório de Agricultura de Precisão) e devem **facilitar operações complexas que o autor ensina em sala**, para que os alunos assimilem os conceitos enquanto usam a ferramenta. Por isso:

- Interfaces visuais e autoexplicativas: controles como barras deslizantes, gráficos e prévias ajudam mais que campos numéricos soltos.
- Cada parâmetro técnico vem acompanhado de uma explicação curta, em linguagem simples, do que ele faz e de quando usar cada valor (por exemplo, potência do IDW, raio de busca, tamanho do pixel).
- Mostrar números que ajudam a interpretar o resultado (área, densidade amostral, quantidade de amostras usadas) e avisos claros quando algo está errado (SRC fora de metros).
- Botão de Ajuda em toda janela, explicando o conceito por trás da etapa, não só os campos.
- Seguir o layout e o padrão das ferramentas nativas do QGIS, para o aluno reconhecer a interface.
- Ao propor uma mudança, avaliar e comentar como ela ajuda (ou atrapalha) o entendimento dos alunos.

## Estrutura

```
agriprecisa/                pasta do complemento (é o que vai no ZIP)
  metadata.txt              versão, changelog, metadados do repositório do QGIS
  core/idw_math.py          matemática pura, sem QGIS (IDW, cobertura, validação cruzada; testada com pytest)
  core/pipeline.py          fluxo IDW > grade > estatística zonal (assistente e Processing)
  core/compat.py            constantes compatíveis com QGIS 3.x e 4.x
  gui/idw_wizard.py         assistente em 4 etapas
  gui/params_page.py        Etapa 3: parâmetros por atributo, modo aluno/avançado, validação
  gui/widgets.py            curva peso x distância e prévia do mapa
  gui/cv_dialog.py          tabela de erro da validação cruzada
  processing_provider/      provedor e algoritmo da Caixa de Ferramentas
  i18n.py                   textos em pt, en e es (toda chave nos três idiomas)
tests/                      testes pytest (sem QGIS)
tests/integration/          teste de ponta a ponta com QGIS real
scripts/build_zip.py        gera dist/agriprecisa-<versão>.zip
docs/GUIA_PUBLICACAO.md     guia para o autor
```

## Fluxo para cada nova versão (automação do git)

### 1. Preparar o repositório
- Anexar com permissão de envio: `add_repo` com owner `gdfaulin`, repo `AgriPrecisa`, access `push`.
- Clonar uma única vez: `git clone --depth 1 https://github.com/gdfaulin/agriprecisa /home/claude/agriprecisa`.
- Antes de criar o ramo: `git fetch origin main` e partir de `origin/main`.

### 2. Implementar
- Textos novos sempre via `tr("chave")` com a chave nos três idiomas em `i18n.py`.
- Números exibidos ao usuário com `fmt()` (separadores conforme o idioma).
- Constantes do QGIS que mudaram entre 3.x e 4.x vão em `core/compat.py`.

### 3. Versão
- Aumentar `version=` em `agriprecisa/metadata.txt` (maior.menor.correção). O plugins.qgis.org recusa versão repetida.
- Acrescentar linha no topo de `changelog=` (metadata.txt, em inglês) e em `CHANGELOG.md`.

### 4. Testar (obrigatório antes de publicar)
- `python3 -m pytest -q tests`
- Teste com QGIS real. Se o QGIS não estiver instalado na sessão:
  `DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3-qgis qgis-providers python3-gdal`
  O QGIS do Ubuntu usa o `python3.12`, não o `python3` padrão.
- `QT_QPA_PLATFORM=offscreen python3.12 -W ignore tests/integration/run_qgis_integration.py` deve terminar com `ALL INTEGRATION CHECKS PASSED`.
- Gerar o ZIP com `python3 scripts/build_zip.py`, extrair em pasta limpa e rodar o teste de integração contra o ZIP extraído.
- Para mostrar telas ao autor: `AGRIPRECISA_SHOT=/caminho/tela.png` no teste de integração salva uma captura do assistente.

### 5. Publicar no GitHub
- Ramo: `versao-X.Y.Z`. Commit em português, terminando com as linhas de atribuição da sessão.
- Não versionar `dist/`, `__pycache__/` nem `.pytest_cache/` (estão no `.gitignore`).
- `git push -u origin versao-X.Y.Z`
- **O GraphQL do GitHub não funciona nesta sessão** (`gh pr create` falha). Usar a API REST:
  - abrir PR: `gh api repos/gdfaulin/agriprecisa/pulls -f base=main -f head=versao-X.Y.Z -f title="Versão X.Y.Z: ..." -F body=@corpo.md`
  - mesclar: `gh api -X PUT repos/gdfaulin/agriprecisa/pulls/<n>/merge -f merge_method=merge -f commit_title="Versão X.Y.Z (#<n>)"`
- O autor pediu publicação automática: abrir e mesclar o PR sem esperar aprovação, depois dos testes passarem.
- **Releases do GitHub não são permitidas nesta sessão** (HTTP 403). Não tentar; entregar o ZIP ao autor pelo chat.

### 6. Entregar ao autor
- Enviar `agriprecisa-X.Y.Z.zip` pelo chat e dizer em uma linha o que mudou.
- Lembrar que o envio ao plugins.qgis.org é feito por ele: página do AgriPrecisa > **Add version** > escolher o ZIP (Etapa 4 e 5 do guia).
- Atualizar `docs/GUIA_PUBLICACAO.md` se o processo mudar.
