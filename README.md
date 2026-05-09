# AvatarCam 2D Desktop

Aplicacao desktop em Python onde sua camera e substituida por um avatar 2D animado. O app captura o microfone, detecta fala por volume em tempo real e alterna automaticamente entre animacao idle e animacao falando.

## O Que Vem Pronto

- Janela desktop nativa, sem navegador e sem servidor web.
- Avatar 2D carregado a partir de imagens escolhidas pelo usuario.
- Captura de microfone com `sounddevice`.
- Deteccao de fala por volume RMS com baixa latencia.
- Troca automatica entre idle e fala.
- Botao para ativar/desativar microfone.
- Botoes para escolher imagens idle e imagens falando.
- Barra de volume em tempo real.
- Sensibilidade e suavizacao ajustaveis.
- FPS da animacao ajustavel.
- Perfis de avatar para lives diferentes.
- Importacao automatica por pasta.
- Importacao copia os assets para a biblioteca local do app.
- Exportar/importar `.avatarpack`.
- Sistema de expressoes com atalhos `Ctrl+1` ate `Ctrl+4`.
- Estados de fala baixa, media e alta por volume.
- Calibracao automatica do ruido ambiente.
- Hotkeys: `F8`, `F9`, `F10`, `F11`, `F12`.
- Icone de bandeja do Windows com menu rapido.
- Editor de escala e posicao do avatar.
- Modo performance para pausar o preview do painel.
- Presets de performance: quality, balanced, performance e ultra.
- Seletor de dispositivo de microfone.
- Cache de imagens otimizadas ao importar avatar.
- Movimento vertical automatico liga/desliga.
- Sombra simples do avatar liga/desliga.
- Pet customizado por GIF, PNG unico ou sequencia de imagens.
- Pet com estados separados para idle, falando e volume alto.
- Pet com camada frente/atras, opacidade e espelhamento.
- Reacoes configuraveis do pet por volume de voz: pulo, tremida, flutuacao e velocidade.
- Piscar automatico opcional do avatar por imagens dedicadas.
- Controle para segurar a boca aberta por mais tempo apos a fala.
- Modo live dedicado com preset ultra, OBS atras e controles ocultos.
- Opcao de iniciar minimizado na bandeja.
- Integracao com Twitch Chat publico sem login.
- Comandos de chat com cooldown para pet, modo live, teste e expressoes.
- Logs locais rotativos para diagnostico.
- Botao para apagar configuracoes, perfis, caminhos de imagens e logs.
- Modo escuro/claro.
- Fundo personalizavel.
- Botao de teste de fala.
- Janela limpa para OBS em 1280x720.
- Fundo chroma key para remover no OBS.
- Opcao para manter a janela OBS sempre no topo.
- Janela OBS com resolucoes 16:9 e vertical.
- Opcao de janela OBS sem borda.
- Modo live para esconder controles e deixar so a janela de captura.
- Botao para enviar a janela OBS para tras das outras janelas.
- Processamento local: sem upload de audio, imagem ou configuracao.
- Estrutura separada por modulos.
- Script para gerar `.exe` no Windows.

## Estrutura

```text
.
|-- app.py
|-- requirements.txt
|-- README.md
|-- avatarcam
|   |-- main.py
|   |-- audio
|   |   |-- microphone.py
|   |-- core
|   |   |-- app_log.py
|   |   |-- avatar_pack.py
|   |   |-- hotkeys.py
|   |   |-- settings.py
|   |   |-- speech_detector.py
|   |-- chat
|   |   |-- twitch.py
|   |-- ui
|       |-- app_window.py
|       |-- avatar_canvas.py
|       |-- obs_window.py
|       |-- tray.py
|       |-- theme.py
|-- scripts
    |-- run.bat
    |-- build_exe.bat
```

## Rodar No VS Code

Instale Python 3.11 ou superior. Depois, no terminal dentro desta pasta:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Ou use:

```bash
scripts\run.bat
```

## Gerar Executavel `.exe`

Com o ambiente configurado, rode:

```bash
scripts\build_exe.bat
```

O executavel sera gerado em:

```text
dist\AvatarCam2D.exe
```

## Como Usar

1. Abra o app.
2. Clique em **Ativar microfone**.
3. Fale no microfone.
4. O app alterna para as imagens de fala enquanto sua voz e detectada.
5. Ao parar de falar, ele volta para idle.
6. Ajuste **Sensibilidade** se ele falar sozinho ou demorar para reagir.
7. Use **Teste de fala** para testar a animacao sem microfone.

## Pasta De Avatar Recomendada

Voce pode importar uma pasta inteira com este formato:

```text
meu-avatar/
|-- idle/
|   |-- 001.png
|   |-- 002.png
|-- talk/
|   |-- 001.png
|-- talk_low/
|   |-- 001.png
|-- talk_mid/
|   |-- 001.png
|-- talk_high/
|   |-- 001.png
|-- blink/
|   |-- 001.png
|-- pet/
|   |-- pet.gif
|-- pet_talk/
|   |-- pet-talk.gif
|-- pet_loud/
    |-- pet-loud.gif
```

Pastas em portugues tambem funcionam para fala:

```text
fala/
fala_baixa/
fala_media/
fala_alta/
```

Ao importar uma pasta, o app copia as imagens para:

```text
%USERPROFILE%\.avatarcam_2d\avatars
```

Assim o avatar continua funcionando mesmo se voce mover ou apagar a pasta original.

Durante a importacao, imagens PNG grandes sao otimizadas para reduzir custo de renderizacao. O arquivo original do usuario nao e alterado.

## Usar Suas Proprias Artes

O app nao depende mais de avatar pronto. Voce escolhe arquivos locais para cada estado:

- **Idle:** imagem parada ou sequencia de frames quando voce nao esta falando.
- **Falando:** imagem de boca aberta ou sequencia de frames quando sua voz e detectada.
- **Fala baixa/media/alta:** imagens opcionais para variar a boca conforme o volume.
- **Piscar:** imagens opcionais usadas automaticamente em pequenos intervalos quando o avatar esta idle.
- **Pet:** arte idle do pet.
- **Pet fala/alto:** artes opcionais para o pet reagir a fala e volume alto.

Formatos recomendados:

- PNG com transparencia para melhor resultado no OBS.
- GIF ou varios PNGs para animacao simples.
- Imagens na mesma proporcao para evitar pulos visuais.

Tudo fica local no seu PC. O app nao envia audio nem imagens para internet.

## Atalhos

- `F8`: ativar/desativar microfone.
- `F9`: teste de fala.
- `F10`: mostrar controles.
- `F11`: abrir/ocultar janela OBS.
- `F12`: mostrar/ocultar pet.

Quando possivel no Windows, o app registra esses atalhos como globais. Se o Windows bloquear, eles continuam funcionando quando a janela do app estiver focada.

Expressoes:

- `Ctrl+1` ate `Ctrl+4`: carrega as primeiras expressoes salvas.

## Avatarpack

Use **Exportar** para gerar um arquivo `.avatarpack` com imagens e configuracoes principais. Use **Importar .avatarpack** para restaurar em outro PC ou compartilhar seu avatar.

## Twitch Chat

Na area **Chat da live**:

1. Digite o nome do canal da Twitch, sem `#`.
2. Clique em **Conectar Twitch**.
3. As mensagens recentes aparecem no painel.
4. Ative ou desative **Comandos do chat**.
5. Ajuste o cooldown para evitar spam.

Comandos iniciais:

- `!pet`: mostrar/ocultar pet.
- `!pular` ou `!jump`: forcar reacao do pet.
- `!teste`: acionar teste de fala.
- `!live`: ativar modo live.
- `!avatar nome`: carregar uma expressao salva com esse nome.

A conexao e feita direto com o chat publico da Twitch. Nao precisa login e nao ha envio de audio, imagem ou configuracao para terceiros.

## Calibracao

Use **Calibrar ruido ambiente** antes da live. Fique em silencio por 3 segundos. O app mede o ruido do seu quarto, teclado e ventoinhas, depois ajusta a sensibilidade automaticamente.

## Ajuste Visual

Use os controles:

- **Escala avatar** para aumentar ou diminuir a arte.
- **Posicao X** para mover para esquerda/direita.
- **Posicao Y** para mover para cima/baixo.
- **Modo performance** para pausar o preview no painel principal e renderizar apenas a janela OBS.
- **Preset performance** para escolher entre qualidade e baixo uso de CPU.
- **Movimento vertical automatico** para ligar/desligar o sobe e desce do avatar.
- **Sombra do avatar** para dar leitura melhor no OBS.
- **Mostrar pet** para ligar/desligar o pet customizado.
- **Tamanho do pet** para ajustar o espaco dele na cena.
- **Pet posicao X/Y** para posicionar o pet na cena.
- **Camada do pet** para colocar na frente ou atras do avatar.
- **Opacidade pet** e **Espelhar pet** para ajustar composicao.
- **Forca reacao pet** e **Reacao do pet** para controlar como o GIF/PNG responde quando voce fala.
- **Escolher GIF/PNG do pet** para usar sua propria arte.
- **Segurar boca** para reduzir cortes secos quando voce para de falar.

Esses ajustes tambem sao aplicados na janela **OBS Avatar Output**.

## Usar Com OBS

1. Abra o `AvatarCam2D.exe`.
2. Escolha as imagens idle e falando.
3. Clique em **Abrir janela OBS**.
3. No OBS, adicione uma fonte **Window Capture**.
4. Escolha a janela chamada **OBS Avatar Output**.
5. Selecione o metodo de captura que funcionar melhor no seu Windows, geralmente **Windows 10 (1903 and up)**.
6. Para remover o fundo, adicione o filtro **Chroma Key** na fonte.
7. Use a cor do fundo selecionado no app, por exemplo `chroma_green`.

O app principal fica para controles e configuracoes. A janela **OBS Avatar Output** fica limpa, sem botoes, pronta para transmissao.

Para jogar sem atrapalhar:

1. Abra a janela OBS.
2. Desmarque **Manter janela OBS no topo**.
3. Clique em **Ativar modo live** ou **Enviar OBS para tras**.
4. Abra o jogo normalmente.

O app continua rodando e o OBS continua capturando a janela. Para restaurar os controles, foque a janela **OBS Avatar Output** e aperte `F10`, ou use o menu da bandeja do Windows.

Para uma camera virtual real, ative a **OBS Virtual Camera** depois de compor a cena no OBS. Assim Discord, Zoom e outros apps podem receber a cena como camera.

## Bandeja Do Windows

Ao fechar a janela principal, o app tenta ficar na bandeja do Windows. Pelo menu da bandeja voce pode:

- abrir controles;
- mostrar/ocultar OBS;
- ligar/desligar microfone;
- ativar modo live;
- mostrar/ocultar pet;
- sair do app.

Se o Windows bloquear o tray, o app continua funcionando normalmente.

## Privacidade E Logs

O app processa audio e imagens localmente. Nada e enviado para internet.

Os logs ficam em:

```text
%USERPROFILE%\.avatarcam_2d\logs
```

Use **Apagar configuracoes locais** para remover configuracoes, perfis, caminhos de imagens e logs.
