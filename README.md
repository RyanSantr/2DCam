# 2DCam Studio

Aplicativo para Windows com avatares 2D e 3D, resposta à voz e rastreamento facial na própria janela.

## Baixar e abrir

**[Baixar 2DCam Studio 3.12 para Windows](https://github.com/RyanSantr/2DCam/releases/download/v3.12.0/2DCam-Studio-3.12.exe)**

Abra o EXE. Não precisa instalar Python nem abrir um navegador. Na primeira abertura, aguarde a preparação dos componentes; as próximas usam a cópia já preparada. Requer Windows 10/11 de 64 bits e os componentes .NET Framework do Windows.

A personagem 3D de exemplo acompanha o app. Câmera e microfone começam desligados. Para atualizar, feche a versão anterior e abra o novo EXE.

## Usar

1. Clique em **Importar avatar** ou arraste PNG, GIF, WebP, VRM, GLB ou `.avatarpack`. Para uma sequência 2D, selecione vários arquivos ou arraste uma pasta.
2. Ative o microfone para responder à voz ou **Ligar câmera** para acompanhar seu rosto. Use **Calibrar posição neutra** olhando para a câmera.
3. Ajuste o enquadramento com o mouse e a roda. Salve a posição e abra **Janela do avatar**.

Na Biblioteca, busque avatares pelo nome e filtre por favoritos ou tipo. Selecione um avatar e clique em **Usar avatar selecionado**, pressione Enter ou dê um duplo clique. Selecionar para renomear ou favoritar mantém o personagem em uso. Você também pode montar poses 2D e salvar cenas. Em Avatar, pode preparar o personagem, editar expressões disponíveis e usar gestos. **Ctrl+Z** desfaz alterações; **F8** mostra os controles e **F9** pausa.

**Cenas e personagens:** prepare o personagem e clique em **Salvar cena**. Dê um nome como “Personagem 1 — Conversa”, depois prepare outro e salve “Personagem 2 — Jogo”. Cada cena guarda avatar 2D/3D, poses, velocidade da animação, enquadramento, movimentos e ajustes da saída. As nove primeiras combinações livres usam **Ctrl+Shift+1…9**. Você pode trocar ou desativar as teclas em **Ajustes → Atalhos → Personalizar atalhos**. Os perfis de versões anteriores aparecem como cenas.

A troca mantém a mesma janela **2DCam - Avatar** aberta para o OBS e carrega somente o personagem em uso. Com a sincronização desligada, ative **Usar também fora do app** para usar as teclas com um jogo em primeiro plano. Para acompanhar os atalhos e as cenas do OBS, configure a sincronização abaixo.

**Animações 2D:** use **Biblioteca → Poses e expressões 2D → Montar personagem visualmente**. Cada pose (parado, falando, piscando e emoções) aceita um ou vários GIFs, PNGs e WebPs. Sequências seguem a ordem numérica dos nomes: `1`, `2`, `10`. A prévia permite pausar, reiniciar e ajustar imagens fixas de 1 a 30 quadros/s. GIF, WebP e PNG animados mantêm seus tempos originais, inclusive misturados com imagens fixas. A velocidade escolhida acompanha o personagem e seu pacote.

Uma pasta pode conter os quadros diretamente ou usar subpastas `idle`, `talk` e `blink`. Até 256 quadros por pose, dentro do limite de memória do modo de desempenho. Se a animação ultrapassar esse limite, reduza dimensões ou quadros antes de importar.

**Sem webcam:** ative o microfone e use **Avatar → Usar sem webcam** para ajustar os movimentos suaves. **Testar movimentos sem câmera** permite conferir cabeça, olhar, boca e piscar; o teste automático dura 12 segundos e encerra sozinho. Ele não liga dispositivos. Fechar a prévia devolve o personagem ao funcionamento normal.

Os pacotes `.avatarpack` também preservam vínculos personalizados de expressões 3D e ajustes de movimento. Pacotes antigos continuam aceitos; use a versão 3.7 ou posterior para recuperar esses novos ajustes.

**Interface:** a aba **Saída** reúne a captura e os vínculos do OBS; **Ajustes** reúne desempenho, imagem, áudio e atalhos. Arraste o separador entre a prévia e o painel para ajustar o espaço. **Ctrl+F** abre a busca na Biblioteca; **Alt+1…5** percorre as abas. Sliders mostram o valor em porcentagem, aceitam teclado e permitem Desfazer. A roda ajusta um controle somente quando ele está em foco, evitando mudanças ao rolar o painel.

Para consumir menos recursos durante a transmissão, selecione **Econômico**, oculte a prévia da câmera e use uma saída de 640 × 360 ou 960 × 540. O consumo depende do modelo e do computador.

### OBS

Adicione uma fonte **Captura de janela**, selecione **2DCam - Avatar** e aplique **Chroma Key** para remover o fundo verde ou azul. Abra **Janela do avatar** e minimize normalmente a janela de controles: o avatar continua aberto e animado em sua janela independente. Na aba Saída, há também **Minimizar só os controles**. Mantenha a janela do avatar aberta, sem minimizar. **F8** ou o menu do botão direito na saída trazem os controles de volta.

**Sincronizar cenas e personagens automaticamente:**

1. Salve seus personagens em **Salvar cena**, no 2DCam.
2. No OBS 28 ou posterior, abra **Ferramentas → Configurações do servidor WebSocket** e habilite o servidor. Ele já acompanha o OBS; consulte o [guia oficial](https://obsproject.com/kb/remote-control-guide).
3. No 2DCam, clique em **Vincular OBS**, informe a porta (normalmente `4455`) e a senha mostradas pelo OBS e clique em **Conectar**.
4. Para cada cena do OBS, escolha o personagem/cena do 2DCam na tabela. Os vínculos são salvos automaticamente. Se os nomes forem iguais, o vínculo funciona automaticamente; escolha **Manter personagem atual** para desativá-lo naquela cena.

Agora, trocar de cena no OBS por atalho, mouse ou outro controle carrega o personagem correspondente. No **Modo Estúdio**, a troca acompanha a cena em programa, após a transição. Cenas sem vínculo mantêm o personagem atual. Com o OBS conectado, os atalhos de troca de cena próprios do 2DCam ficam suspensos para evitar conflitos; os controles e expressões continuam disponíveis. O 2DCam acompanha o OBS; escolher uma cena manualmente no 2DCam não altera o OBS.

A conexão usa somente este computador. Se o OBS fechar, o app mantém o personagem e tenta reconectar. Para reconectar sozinho após reabrir o 2DCam, marque **Lembrar senha neste usuário do Windows** ao conectar. A senha salva é protegida pelo Windows e só pode ser recuperada pelo mesmo usuário. Sem essa opção, informe-a novamente ao abrir o app.

Para transparência, o app também oferece saída Spout2; o OBS precisa do [complemento Spout2](https://github.com/Off-World-Live/obs-spout2-plugin/releases).

### Formatos e dados

PNG/GIF/WebP usam poses e movimento da imagem. VRM e GLB usam os recursos presentes no modelo; boca, olhos e expressões dependem dele. VRM/GLB precisam de recursos incorporados, até 128 MiB, sem Draco, Meshopt ou KTX2. **Live2D ainda não está disponível nesta versão.**

Personagens e configurações ficam em `%USERPROFILE%\.avatarcam_2d`. Os componentes preparados ficam em `%LOCALAPPDATA%\2DCam\runtime`. O rastreamento é processado localmente, sem enviar ou gravar imagens da câmera. Instruções e créditos também estão em **Ajuda → Sobre, ajuda e créditos**.

## Código-fonte

- `avatarcam/`: aplicativo, rastreamento e recursos.
- `scripts/`: iniciar e construir o executável.
- `web3d-build/`: construção do renderizador incorporado.
- `third-party-licenses/`: licenças dos componentes e modelos incluídos.

No Windows, com **Python 3.12 x64**, execute `scripts/run.bat`. Para gerar `dist/2DCam-Studio-3.12.exe`, execute `scripts/build_exe.bat`.

Para alterar o renderizador, use Node 22 e execute `npm ci --ignore-scripts` e `npm run build` dentro de `web3d-build`. O renderizador pronto já acompanha o código. A rotina de build no GitHub constrói o renderizador e o executável Windows.

## Créditos

Projeto de RyanSantr, sob [licença MIT](LICENSE). O avatar de exemplo é de pixiv Inc. Os avisos e condições dos componentes estão em [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) e `third-party-licenses/`.
