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
- Estados de fala baixa, media e alta por volume.
- Calibracao automatica do ruido ambiente.
- Hotkeys: `F8`, `F9`, `F10`, `F11`.
- Modo escuro/claro.
- Fundo personalizavel.
- Botao de teste de fala.
- Janela limpa para OBS em 1280x720.
- Fundo chroma key para remover no OBS.
- Opcao para manter a janela OBS sempre no topo.
- Janela OBS com resolucoes 16:9 e vertical.
- Opcao de janela OBS sem borda.
- Modo live para esconder controles e deixar so a janela de captura.
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
|   |   |-- hotkeys.py
|   |   |-- settings.py
|   |   |-- speech_detector.py
|   |-- ui
|       |-- app_window.py
|       |-- avatar_canvas.py
|       |-- obs_window.py
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
    |-- 001.png
```

Pastas em portugues tambem funcionam para fala:

```text
fala/
fala_baixa/
fala_media/
fala_alta/
```

## Usar Suas Proprias Artes

O app nao depende mais de avatar pronto. Voce escolhe arquivos locais para cada estado:

- **Idle:** imagem parada ou sequencia de frames quando voce nao esta falando.
- **Falando:** imagem de boca aberta ou sequencia de frames quando sua voz e detectada.
- **Fala baixa/media/alta:** imagens opcionais para variar a boca conforme o volume.

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

Quando possivel no Windows, o app registra esses atalhos como globais. Se o Windows bloquear, eles continuam funcionando quando a janela do app estiver focada.

## Calibracao

Use **Calibrar ruido ambiente** antes da live. Fique em silencio por 3 segundos. O app mede o ruido do seu quarto, teclado e ventoinhas, depois ajusta a sensibilidade automaticamente.

## Usar Com OBS

1. Abra o `AvatarCam2D.exe`.
2. Escolha as imagens idle e falando.
3. Clique em **Abrir janela OBS**.
3. No OBS, adicione uma fonte **Window Capture**.
4. Escolha a janela chamada **OBS Avatar Output**.
5. Selecione o metodo de captura que funcionar melhor no seu Windows, geralmente **Windows 10 (1903 and up)**.
6. Para remover o fundo, adicione o filtro **Chroma Key** na fonte.
7. Use a cor do fundo selecionado no app, por exemplo `chroma_green`.

O app principal fica para controles e configuracoes. A janela **OBS Avatar Output** fica limpa, sem botoes, pronta para transmissao. Use **Modo live: ocultar controles** para esconder o painel durante jogos. Para restaurar os controles, foque a janela **OBS Avatar Output** e aperte `F10`.

Para uma camera virtual real, ative a **OBS Virtual Camera** depois de compor a cena no OBS. Assim Discord, Zoom e outros apps podem receber a cena como camera.
