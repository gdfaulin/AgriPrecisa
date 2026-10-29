# Guia de publicação do AgriPrecisa no repositório oficial do QGIS

Este guia leva o AgriPrecisa do seu computador até o repositório oficial (plugins.qgis.org), de onde qualquer pessoa poderá instalá-lo pelo próprio QGIS. O caminho principal não usa terminal, tudo é feito pelo navegador e pelo QGIS.

> **Atualizações no GitHub são automáticas.** O repositório github.com/gdfaulin/AgriPrecisa já existe, e, a partir da versão 1.0.2, o Claude publica cada nova versão diretamente nele (ramo, testes, pull request e mesclagem). As instruções dessa automação estão no arquivo `CLAUDE.md` do repositório. A Etapa 2 abaixo fica só como registro de como o repositório foi criado. O que continua com você é enviar o ZIP ao plugins.qgis.org (Etapas 3 a 5).

O arquivo que você vai usar é o **agriprecisa-X.Y.Z.zip**, entregue pelo Claude no chat a cada versão. É o complemento que vai para o repositório do QGIS.

---

## Etapa 1. Testar no seu QGIS

1. Abra *Complementos > Gerenciar e instalar complementos*.
2. Se o antigo **IDW em grade vetorial** estiver instalado, desinstale-o na aba *Instalados*, para não ficarem dois botões iguais.
3. Na aba **Instalar a partir do ZIP**, escolha o ZIP da versão mais recente (por exemplo, `agriprecisa-1.0.2.zip`) e clique em **Instalar complemento**.
4. Confira:
   - o menu *Vetor > AgriPrecisa* com os itens **IDW em grade vetorial...** e **Documentação do AgriPrecisa**;
   - a barra de ferramentas **AgriPrecisa** com o ícone da grade com pontos;
   - na *Caixa de Ferramentas de Processamento* (Ctrl+Alt+T), o grupo **AgriPrecisa > Interpolação > IDW em grade vetorial**.
5. Rode o assistente com um talhão real e compare com os resultados do script antigo.
6. Para ver os outros idiomas: *Configurações > Opções > Geral*, marque **Substituir a localidade do sistema**, escolha *English* ou *Español* e reinicie o QGIS.

> Se algo der errado, a mensagem de erro aparece em *Exibir > Painéis > Registro de mensagens*, na aba *Python*. Copie o texto e me envie.

---

## Etapa 2. Criar o repositório no GitHub (já feito)

O repositório do QGIS exige um endereço público com o código (`repository`) e um local para receber relatos de problemas (`tracker`). Os metadados já apontam para **github.com/gdfaulin/AgriPrecisa**.

1. Entre em https://github.com com a conta **gdfaulin**.
2. Clique no **+** (canto superior direito) e em **New repository**.
3. Preencha:
   - *Repository name*: `AgriPrecisa` (exatamente assim, com A e P maiúsculos);
   - *Description*: `Precision agriculture tools for QGIS`;
   - marque **Public**;
   - **não** marque *Add a README*, *.gitignore* nem *license*, porque esses arquivos já estão no pacote.
4. Clique em **Create repository**.
5. Descompacte `AgriPrecisa-repositorio.zip` no seu computador. Vai aparecer uma pasta `AgriPrecisa` com `agriprecisa`, `docs`, `scripts`, `tests`, `README.md`, `LICENSE` e outros.
6. Na página do repositório recém-criado, clique no link **uploading an existing file**.
7. Abra a pasta descompactada, selecione **todo o conteúdo dela** (não a pasta em si) e arraste para a área de upload do navegador. O GitHub mantém as subpastas.
8. Em *Commit changes*, escreva `Versão 1.0.0` e clique em **Commit changes**.
9. Confira que *Issues* está ativo: aba **Settings > General > Features > Issues**.

> O arquivo `.gitignore` começa com ponto e fica oculto no Windows e no macOS. Se ele não subir, não tem problema, ele só evita que arquivos temporários entrem no repositório.

---

## Etapa 3. Criar a conta OSGeo

O repositório do QGIS usa a identidade da OSGeo (Open Source Geospatial Foundation).

1. Acesse https://id.osgeo.org/ldap/create e preencha o cadastro. Use um nome de usuário simples, como `gdfaulin`.
2. Confirme o e-mail recebido.
3. Entre em https://plugins.qgis.org com esse usuário e senha (botão **Login**).

---

## Etapa 4. Enviar o complemento

1. Em https://plugins.qgis.org, já logado, clique em **Upload a plugin** (https://plugins.qgis.org/plugins/add/).
2. Escolha o ZIP da versão mais recente e envie.
3. O site valida o pacote automaticamente: nome da pasta, `metadata.txt`, campos obrigatórios, arquivo `LICENSE` e versão única. O pacote já foi conferido contra essas regras.
4. A primeira versão fica **aguardando aprovação** de um membro da equipe do QGIS. O prazo costuma ser de alguns dias. Você recebe um e-mail quando for aprovada.
5. Depois de aprovada, qualquer pessoa encontra o AgriPrecisa em *Complementos > Gerenciar e instalar complementos > Tudo*.

---

## Etapa 5. Publicar novas versões

Cada envio precisa de um número de versão **novo**, no formato `maior.menor.correção`:

- `1.0.3`: correção de erro ou ajuste pequeno;
- `1.1.0`: nova ferramenta ou nova opção;
- `2.0.0`: mudança grande, que altera o funcionamento.

**O que o Claude faz automaticamente** quando você pede uma alteração e diz para publicar:

1. aumenta a versão e registra a mudança no histórico (`metadata.txt` e `CHANGELOG.md`);
2. roda os testes automáticos e o teste completo dentro do QGIS;
3. gera o ZIP e testa o ZIP final;
4. publica no GitHub: cria um ramo, envia, abre um *pull request* (pedido de inclusão) e o mescla no ramo principal;
5. envia o ZIP para você no chat.

**O que você faz:**

1. Instala o ZIP no seu QGIS e confere (Etapa 1).
2. Entra em https://plugins.qgis.org, abre a página do AgriPrecisa e clica em **Add version**.
3. Escolhe o ZIP e envia.

Para pedir ao Claude, basta algo como: *"Publique a nova versão do AgriPrecisa no GitHub."*

> O GitHub não permite que o Claude crie a página de *release* (versão para download) nesta configuração. Isso não afeta a publicação: o código fica no GitHub e o ZIP vai para o plugins.qgis.org.

---

## Etapa 6 (opcional). Rodar os testes e gerar o ZIP pelo terminal

Esta etapa é para quando você quiser rodar os testes por conta própria. Até lá, posso fazer isso por você.

**Abrir o terminal**

- *Windows*: abra o menu Iniciar e procure **OSGeo4W Shell**. Ele vem com o QGIS e já tem o Python do QGIS configurado.
- *macOS*: abra o **Terminal** pelo Spotlight (Cmd+Espaço, digite "Terminal").

**Comandos, um de cada vez**

1. Entrar na pasta do projeto. O comando `cd` ("change directory") muda a pasta em que o terminal está trabalhando:

   ```
   cd caminho/para/AgriPrecisa
   ```

   Dica: digite `cd ` (com espaço) e arraste a pasta para a janela do terminal, o caminho é preenchido sozinho.

2. Instalar o pytest, a ferramenta que executa os testes automáticos. Só é preciso fazer isso uma vez:

   ```
   python -m pip install pytest
   ```

   `python -m pip` chama o instalador de pacotes do Python, e `install pytest` pede para instalar o pytest.

3. Rodar os testes:

   ```
   python -m pytest tests
   ```

   O pytest procura os arquivos `test_*.py` na pasta `tests` e executa cada verificação. No final aparece algo como `22 passed`. Se aparecer `failed`, copie a mensagem e me envie.

4. Gerar o ZIP:

   ```
   python scripts/build_zip.py
   ```

   O script lê a versão em `metadata.txt` e cria `dist/agriprecisa-<versão>.zip` só com a pasta do complemento, sem arquivos temporários.

---

## Conferência antes de enviar

- [ ] Testado no QGIS (Etapa 1)
- [ ] Repositório público no GitHub com Issues ativo
- [ ] Endereços em `homepage`, `repository` e `tracker` abrindo corretamente
- [ ] Versão nova em `metadata.txt`
- [ ] Testes passando
