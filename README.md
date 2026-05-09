# AvatarCam 2D Desktop

Aplicacao desktop em Python onde sua camera e substituida por um avatar 2D animado. O app captura o microfone, detecta fala por volume em tempo real e alterna automaticamente entre animacao idle e animacao falando.

## O Que Vem Pronto

- Janela desktop nativa, sem navegador e sem servidor web.
- Avatar 2D desenhado em Canvas.
- Captura de microfone com `sounddevice`.
- Deteccao de fala por volume RMS.
- Troca automatica entre idle e fala.
- Botao para ativar/desativar microfone.
- Botao para trocar avatar.
- Barra de volume em tempo real.
- Sensibilidade e suavizacao ajustaveis.
- Modo escuro/claro.
- Fundo personalizavel.
- Botao de teste de fala.
- Janela limpa para OBS em 1280x720.
- Fundo chroma key para remover no OBS.
- Opcao para manter a janela OBS sempre no topo.
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
|   |-- assets
|   |   |-- avatars.py
|   |-- audio
|   |   |-- microphone.py
|   |-- core
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
4. O avatar abre a boca e anima enquanto sua voz e detectada.
5. Ao parar de falar, ele volta para idle.
6. Ajuste **Sensibilidade** se ele falar sozinho ou demorar para reagir.
7. Use **Teste de fala** para testar a animacao sem microfone.

## Trocar Por Suas Proprias Artes

Hoje o avatar e desenhado em `avatarcam/ui/avatar_canvas.py`. Para usar artes 2D proprias no futuro, existem dois caminhos:

- Substituir o desenho do Canvas por imagens PNG usando `PhotoImage`.
- Criar sprites separados para idle/fala e trocar os frames dentro de `AvatarCanvas.update_state`.

A logica de audio e fala ja esta separada, entao voce nao precisa mexer em `avatarcam/audio` nem em `avatarcam/core`.

## Usar Com OBS

1. Abra o `AvatarCam2D.exe`.
2. Clique em **Abrir janela OBS**.
3. No OBS, adicione uma fonte **Window Capture**.
4. Escolha a janela chamada **OBS Avatar Output**.
5. Selecione o metodo de captura que funcionar melhor no seu Windows, geralmente **Windows 10 (1903 and up)**.
6. Para remover o fundo, adicione o filtro **Chroma Key** na fonte.
7. Use a cor do fundo selecionado no app, por exemplo `chroma_green`.

O app principal fica para controles e configuracoes. A janela **OBS Avatar Output** fica limpa, sem botoes, em formato 16:9, pronta para transmissao.

Para uma camera virtual real, ative a **OBS Virtual Camera** depois de compor a cena no OBS. Assim Discord, Zoom e outros apps podem receber a cena como camera.
