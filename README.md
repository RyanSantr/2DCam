# 2DCam Studio 3.2

[![Testes Windows](https://github.com/RyanSantr/2DCam/actions/workflows/tests.yml/badge.svg)](https://github.com/RyanSantr/2DCam/actions/workflows/tests.yml)

Aplicativo Windows para usar avatares 2D e 3D na própria janela, com voz e rastreamento facial local.

## Abrir

Baixe o ZIP Windows em [Releases](https://github.com/RyanSantr/2DCam/releases/latest). O botão **Code → Download ZIP** contém o código-fonte; o aplicativo pronto está em Releases.

1. Extraia **todo o ZIP**.
2. Abra **2DCamStudio.exe**.
3. Mantenha **_internal** ao lado do executável.

Não precisa instalar Python nem abrir navegador. Câmera e microfone começam desligados.

Abrir novamente traz os controles da instância existente para a frente. Cada biblioteca de configurações usa uma única instância, evitando carregar o avatar duas vezes.

## Controles

- **Importar avatar:** PNG/GIF, VRM/GLB ou .avatarpack. Também aceita arrastar um arquivo.
- **Avatar:** voz, câmera e expressões.
- **Biblioteca:** avatares recentes, poses 2D, pacotes e perfis.
- **Câmera:** dispositivo, calibração e resposta dos movimentos. A prévia só ocupa memória enquanto visível.
- **Configurações:** desempenho, tamanho/fundo da saída e diagnóstico.
- **Pausar:** desliga câmera e microfone e congela a animação. Retomar reativa os dispositivos que estavam ligados.

Para começar: importe o personagem, ative o microfone ou **Ligar rastreamento**, olhe para a câmera e **Calibrar posição neutra**. Ajuste o enquadramento com o mouse. Use a roda para aproximar; no 3D, o botão direito move a câmera. Salve a posição antes de abrir a saída.

## Desempenho

| Modo | Limite de renderização | Rastreamento | Resolução solicitada à câmera | Imagens 2D + pixmaps |
|---|---:|---:|---|---|
| Econômico | 24 FPS | 12 leituras/s | 320 × 240 | 32 + 16 MiB |
| Equilibrado | 30 FPS | 20 leituras/s | 480 × 360 | 64 + 24 MiB |
| Qualidade | 60 FPS | 30 leituras/s | 640 × 480 | 96 + 32 MiB |

São limites e metas, não uma promessa de FPS. GPU, iluminação, câmera e complexidade do modelo afetam o resultado. O orçamento das imagens não limita toda a memória do aplicativo; modelos 3D, detector facial e componentes nativos usam memória adicional.

Com o OBS, comece por **Econômico**, saída **960 × 540** ou **640 × 360**, câmera oculta e **Ocultar controles ao abrir saída**. A memória privada residente dos processos aparece no rodapé; não inclui memória compartilhada nem VRAM.

O app carrega apenas um avatar 3D. A saída reutiliza a mesma superfície do editor; por isso a prévia do editor fica substituída por uma mensagem durante a captura. Voltar ao editor devolve o mesmo renderizador. Trocar para 2D destrói a página 3D e libera seu conteúdo. Modelos pesados devem ser reduzidos pelo criador; o app não consegue garantir um teto de RAM para todo VRM/GLB.

## Saída para OBS

1. Clique **Abrir saída para OBS**.
2. No OBS, crie **Captura de janela** e selecione **2DCam - Avatar**.
3. Use **Automático**; se a captura falhar, escolha **Windows 10 (1903 ou superior)**.
4. Desative **Capturar cursor** e ative **Área do cliente**.
5. Use o filtro **Chroma Key** para remover o fundo verde ou azul.

Mantenha a saída aberta e sem minimizar. Os controles do editor podem ficar ocultos. Clique com o botão direito na área vazia da saída para mostrar os controles, pausar ou fechar. Fechar a saída devolve o avatar ao editor. Não é necessário criar uma Fonte de navegador.

Tamanhos: 640 × 360, 960 × 540, 1280 × 720 e 1920 × 1080. Fundos: verde, azul ou cinza. **Recarregar prévia 3D** recupera uma renderização interrompida. O app não instala driver de câmera virtual nem oferece alpha transparente diretamente ao OBS.

A captura foi exercitada no OBS 32.2.2 / Windows 11 com Windows Graphics Capture. Outras versões e dispositivos exigem verificação. Em computadores com duas GPUs, o OBS e o app podem exigir ajustes nas preferências gráficas do Windows.

Referências oficiais: [Captura de janela](https://obsproject.com/kb/window-capture-sources) e [Seleção de GPU](https://obsproject.com/kb/gpu-selection-guide).

## Formatos

- **PNG/GIF:** movimento da imagem e troca de poses de fala, piscar e expressões. Uma imagem plana não ganha uma malha facial articulada. Adicione as poses na Biblioteca.
- **VRM:** cabeça, olhos, boca e expressões conforme os recursos presentes no modelo; física do cabelo quando disponível.
- **GLB:** visualização e animação incorporada. Boca e olhos dependem dos morphs; orientação parcial do objeto acompanha a cabeça.

VRM/GLB devem ser autocontidos, com recursos incorporados, sem Draco/Meshopt/KTX2. Limite do arquivo: 128 MiB. Imagens são redimensionadas no cache conforme o modo; animações aceitam até 256 frames e devem caber no orçamento de imagens. Não importa Live2D Cubism, FBX ou OBJ.

## Biblioteca e privacidade

Arquivos importados são copiados para a biblioteca local. Recentes guardam até 12 avatares. Perfis guardam poses, expressões 2D, pet, modelo, enquadramento, ajustes de voz/movimento, desempenho e saída. Carregar um perfil substitui as poses vazias corretamente; um arquivo obrigatório ausente mantém o avatar atual. É possível excluir um perfil sem apagar as imagens. Perfis antigos continuam disponíveis.

Pacotes .avatarpack permitem transportar o personagem; vínculos personalizados de expressão permanecem nas configurações locais. Perfis guardam caminhos locais e não são pacotes portáteis. Dados locais ficam em `%USERPROFILE%\.avatarcam_2d`.

Pastas 2D aceitam idle, talk/fala, blink/piscar e pet. A câmera é processada em memória; o app não envia nem grava seus frames. O diagnóstico não inclui imagens da câmera. Configurações da versão anterior são preservadas.

## Atalhos

| Atalho | Ação |
|---|---|
| Ctrl+O | Importar |
| Ctrl+M | Microfone |
| Ctrl+T | Câmera |
| Ctrl+P | Pausar / retomar |
| Ctrl+Shift+O | Saída |
| Espaço | Testar fala |

## Código e créditos

Código principal em avatarcam/desktop e avatarcam/tracking. Com Python 3.12 de 64 bits, execute `scripts/run.bat` para iniciar pelo código ou `scripts/build_exe.bat` para gerar o aplicativo. O resultado é dist/2DCamStudio/; distribua a pasta inteira. O renderizador compilado e os modelos já estão no repositório; Node só é necessário ao alterar o JavaScript. Módulos antigos são mantidos somente para regressão; o executável usa a interface nativa.

Projeto original de RyanSantr; MIT preservada. Modelo de exemplo VRM1_Constraint_Twist_Sample, © 2022 pixiv Inc., arquivo preservado sem alterações. Detector MediaPipe incluído. Fontes, condições e licenças em THIRD_PARTY_NOTICES.txt e third-party-licenses/.
