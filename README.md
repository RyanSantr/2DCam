# 2DCam Studio

Aplicativo para Windows com avatares 2D e 3D, resposta à voz e rastreamento facial na própria janela.

## Baixar e abrir

**[Baixar 2DCam Studio 3.6 para Windows](https://github.com/RyanSantr/2DCam/releases/download/v3.6.0/2DCam-Studio-3.6.exe)**

Abra o EXE. Não precisa instalar Python nem abrir um navegador. Na primeira abertura, aguarde a preparação dos componentes; as próximas usam a cópia já preparada. Requer Windows 10/11 de 64 bits e os componentes .NET Framework do Windows.

A personagem 3D de exemplo acompanha o app. Câmera e microfone começam desligados. Para atualizar, feche a versão anterior e abra o novo EXE.

## Usar

1. Clique em **Importar avatar** ou arraste um PNG, GIF, VRM, GLB ou `.avatarpack`.
2. Ative o microfone para responder à voz ou **Ligar rastreamento** para acompanhar seu rosto. Use **Calibrar posição neutra** olhando para a câmera.
3. Ajuste o enquadramento com o mouse e a roda. Salve a posição e abra **Saída OBS**.

Na Biblioteca, você pode montar poses 2D, organizar favoritos e salvar perfis. Em Avatar, pode preparar o personagem, editar expressões disponíveis e usar gestos. **Ctrl+Z** desfaz alterações; **F8** mostra os controles e **F9** pausa.

Para consumir menos recursos durante a transmissão, selecione **Econômico**, oculte a prévia da câmera e use uma saída de 640 × 360 ou 960 × 540. O consumo depende do modelo e do computador.

### OBS

Adicione uma fonte **Captura de janela**, selecione **2DCam - Avatar** e aplique **Chroma Key** para remover o fundo verde ou azul. Mantenha a saída aberta, sem minimizar.

Para transparência, o app também oferece saída Spout2; o OBS precisa do [complemento Spout2](https://github.com/Off-World-Live/obs-spout2-plugin/releases).

### Formatos e dados

PNG/GIF usam poses e movimento da imagem. VRM e GLB usam os recursos presentes no modelo; boca, olhos e expressões dependem dele. VRM/GLB precisam de recursos incorporados, até 128 MiB, sem Draco, Meshopt ou KTX2. **Live2D ainda não está disponível nesta versão.**

Personagens e configurações ficam em `%USERPROFILE%\.avatarcam_2d`. Os componentes preparados ficam em `%LOCALAPPDATA%\2DCam\runtime`. O rastreamento é processado localmente, sem enviar ou gravar imagens da câmera. Instruções e créditos também estão em **Ajuda → Sobre, ajuda e créditos**.

## Código-fonte

- `avatarcam/`: aplicativo, rastreamento e recursos.
- `scripts/`: iniciar e construir o executável.
- `web3d-build/`: construção do renderizador incorporado.
- `third-party-licenses/`: licenças dos componentes e modelos incluídos.

No Windows, com **Python 3.12 x64**, execute `scripts/run.bat`. Para gerar `dist/2DCam-Studio-3.6.exe`, execute `scripts/build_exe.bat`.

Testes: `.venv\Scripts\python -m unittest discover -s tests -v`. Para alterar o renderizador, use Node 22 e execute `npm ci --ignore-scripts` e `npm run build` dentro de `web3d-build`. O renderizador pronto já acompanha o código.

## Créditos

Projeto de RyanSantr, sob [licença MIT](LICENSE). O avatar de exemplo é de pixiv Inc. Os avisos e condições dos componentes estão em [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) e `third-party-licenses/`.
