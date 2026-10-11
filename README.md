# 2DCam Studio 3.5

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
- **Avatar:** voz, câmera e expressões. Microfone, câmera e pausa também ficam no topo, acessíveis em todas as abas.
- **Biblioteca:** miniaturas, favoritos, nomes editáveis e filtros por 2D/3D. Clique no item para usar o avatar; poses, pacotes e perfis ficam em grupos recolhidos.
- **Câmera:** dispositivo, calibração e resposta dos movimentos. A prévia só ocupa memória enquanto visível.
- **Configurações:** desempenho e saída visíveis; áudio, imagem e atalhos em grupos recolhidos. Clique no título para abrir o grupo.
- **Pausar:** desliga câmera e microfone e congela a animação. Retomar reativa os dispositivos que estavam ligados.

Para começar: importe o personagem, ative o microfone ou **Ligar rastreamento**, olhe para a câmera e **Calibrar posição neutra**. Ajuste o enquadramento com o mouse. Use a roda para aproximar; no 3D, o botão direito move a câmera. Salve a posição antes de abrir a saída.

## Preparar e editar personagens

Após importar PNG/GIF ou VRM/GLB, o guia mostra os recursos encontrados, ajuda a calibrar as entradas e salva os ajustes para o personagem. **Avatar → Preparar personagem** abre o guia novamente. A câmera e o microfone só ligam quando você clica; calibrar rosto salva a posição neutra na biblioteca.

**Biblioteca → Poses e expressões 2D → Montar personagem visualmente:** arraste PNG/GIF para Parado, Falando, Piscando e emoções. Os botões de teste mostram cada pose, incluindo GIF animado. Parado é obrigatório; salvar copia os recursos e só substitui o personagem após validar a operação inteira. Imagens de uma sequência podem ser selecionadas juntas; a prévia do editor mostra o primeiro arquivo dessa sequência.

**Avatar → Editar expressões do modelo:** escolha um recurso existente para cada emoção, boca ou piscar, teste a intensidade e salve. Recursos de VRM e formas de GLB aparecem conforme o modelo. A configuração vale para aquele personagem e pode ser guardada em perfil. O editor não cria formas faciais ausentes nem modifica o arquivo original. Os pacotes 3D ainda não levam esses novos vínculos personalizados; para preservá-los neste computador, use a biblioteca ou um perfil.

**Avatar → Ações do personagem:** acenar, concordar, negar e comemorar. VRM usa os ossos disponíveis; GLB admite movimentos do objeto; PNG/GIF usa movimento da imagem. Ações incompatíveis ficam desativadas. Os gestos se misturam ao rastreamento e terminam após 2,5 segundos. Atalhos padrão: Ctrl+Alt+7/8/9/0; podem ser personalizados.

**Editar → Desfazer/Refazer**, Ctrl+Z e Ctrl+Shift+Z restauram até 20 alterações de poses, vínculos, enquadramento e ajustes. O histórico guarda apenas configurações, sem duplicar modelos ou imagens. Restaurar ajustes do avatar também pode ser desfeito. O histórico é da sessão atual.

Se o app fechar inesperadamente, a próxima abertura oferece recuperar personagem e configurações do último salvamento. Câmera, microfone, saída transparente e janela OBS permanecem desligados. Arquivos ausentes impedem a recuperação sem substituir o personagem atual.

**Configurações → Verificar funcionamento** mostra problemas nas funções em uso com um botão para ajustar. Entradas desligadas não geram alertas. Entrada de áudio baixa é um aviso condicional: se você estiver falando, confira seleção/sensibilidade; silêncio normal também pode produzi-lo.

## Dispositivos e reconexão

A seleção mostra nomes de microfones e câmeras disponíveis. Use **Câmera → Atualizar dispositivos** após conectar um USB. Câmeras são enumeradas pelo mesmo backend da captura; se o nome não puder ser lido, permanece a seleção por número. A enumeração não inicia a captura.

O app tenta recuperar somente câmera/microfone que você tenha ligado. A espera entre falhas cresce de 2 até 30 segundos. **Desligar** ou **Pausar** cancela as tentativas; retomar recupera as entradas que estavam solicitadas, mesmo se desconectadas. Entradas começam desligadas a cada abertura. O dispositivo identificado é procurado novamente após mudança de índice; se não for encontrado, o app espera em vez de ativar outro dispositivo. Mudança de nome ou porta USB pode exigir selecionar o dispositivo novamente. Câmera em uso por outro programa, permissões e drivers podem impedir a conexão.

## Desempenho

| Modo | Limite de renderização | Rastreamento | Resolução solicitada à câmera | Imagens 2D + pixmaps |
|---|---:|---:|---|---|
| Econômico | 24 FPS | 12 leituras/s | 320 × 240 | 32 + 16 MiB |
| Equilibrado | 30 FPS | 20 leituras/s | 480 × 360 | 64 + 24 MiB |
| Qualidade | 60 FPS | 30 leituras/s | 640 × 480 | 96 + 32 MiB |

O modo **Automático** começa em Equilibrado, reduz qualidade após três amostras de lentidão e pode subir após 30 segundos de estabilidade. Considera a taxa do renderizador e atrasos da interface; não tenta medir a carga de outros apps nem garante uma taxa de FPS. Pausar/ocultar interrompe a decisão. Para manter a qualidade fixa, escolha um dos três modos da tabela.

São limites e metas, não uma promessa de FPS. GPU, iluminação, câmera e complexidade do modelo afetam o resultado. O orçamento das imagens não limita toda a memória do aplicativo; modelos 3D, detector facial e componentes nativos usam memória adicional.

Os controles recebem atualizações agrupadas em até 10 vezes por segundo; o avatar mantém sua própria taxa. A miniatura da câmera só é refeita quando chega um frame novo e é liberada ao ocultar ou minimizar os controles.

Com o OBS, comece por **Econômico**, saída **960 × 540** ou **640 × 360**, câmera oculta e **Ocultar controles ao abrir saída**. A memória privada residente dos processos aparece no rodapé; não inclui memória compartilhada nem VRAM.

O app carrega apenas um avatar 3D. A saída reutiliza a mesma superfície do editor; por isso a prévia do editor fica substituída por uma mensagem durante a captura. Voltar ao editor devolve o mesmo renderizador. Trocar para 2D destrói a página 3D e libera seu conteúdo. Modelos pesados devem ser reduzidos pelo criador; o app não consegue garantir um teto de RAM para todo VRM/GLB.

## Saída para OBS

1. Clique **Saída OBS**.
2. No OBS, crie **Captura de janela** e selecione **2DCam - Avatar**.
3. Use **Automático**; se a captura falhar, escolha **Windows 10 (1903 ou superior)**.
4. Desative **Capturar cursor** e ative **Área do cliente**.
5. Use o filtro **Chroma Key** para remover o fundo verde ou azul.

Mantenha a saída aberta e sem minimizar. Os controles do editor podem ficar ocultos. Clique com o botão direito na área vazia da saída para mostrar os controles, pausar ou fechar. Fechar a saída devolve o avatar ao editor. Não é necessário criar uma Fonte de navegador.

Tamanhos horizontais: 640 × 360, 960 × 540, 1280 × 720 e 1920 × 1080. Verticais: 720 × 1280 e 1080 × 1920. A opção **Saída sempre no topo** mantém o avatar à vista. Fundos: verde, azul ou cinza. **Recarregar prévia 3D** recupera uma renderização interrompida. O app não instala driver de câmera virtual. A opção Spout2 abaixo oferece alpha; Captura de janela continua usando Chroma Key.

A captura foi exercitada no OBS 32.2.2 / Windows 11 com Windows Graphics Capture. Outras versões e dispositivos exigem verificação. Em computadores com duas GPUs, o OBS e o app podem exigir ajustes nas preferências gráficas do Windows.

Referências oficiais: [Captura de janela](https://obsproject.com/kb/window-capture-sources) e [Seleção de GPU](https://obsproject.com/kb/gpu-selection-guide).

### Saída transparente com Spout2

1. Instale o [complemento oficial Spout2 para OBS](https://github.com/Off-World-Live/obs-spout2-plugin/releases) no seu OBS e reinicie-o.
2. No 2DCam, clique **Configurações → Ligar saída transparente**.
3. No OBS, adicione **Captura Spout2**, selecione **2DCam - Transparente** e escolha **Alpha** no modo de composição.
4. Não adicione Chroma Key a essa fonte. O fundo já contém transparência.

A transmissão é produzida pelo app; não é necessário outro app para controlar o personagem. O complemento pertence ao OBS e não é instalado silenciosamente pelo 2DCam. A saída trabalha em até 640 pixels no maior lado e 24 tentativas por segundo; a frequência real depende da GPU e do renderizador. Uma única imagem/captura fica pendente por vez. Ler/exportar pixels gera trabalho adicional; para o menor consumo, mantenha essa opção desligada e use Captura de janela. Outra janela cobrindo o app não interrompe a transmissão. Pausar/minimizar a janela que renderiza suspende novos envios. Desligar a saída libera o transmissor. GPUs/drivers e uso de GPUs diferentes podem impedir o compartilhamento.

Recepção alpha validada em 2D/3D com OBS 32.2.2 e Spout2 1.12.0. Não promete compatibilidade universal.

## Formatos

- **PNG/GIF:** movimento da imagem e troca de poses de fala, piscar e expressões. Uma imagem plana não ganha uma malha facial articulada. Adicione as poses na Biblioteca.
- **VRM:** cabeça, olhos, boca e expressões conforme os recursos presentes no modelo; física do cabelo quando disponível.
- **GLB:** visualização e animação incorporada. Boca e olhos dependem dos morphs; orientação parcial do objeto acompanha a cabeça.

VRM/GLB devem ser autocontidos, com recursos incorporados, sem Draco/Meshopt/KTX2. Limite do arquivo: 128 MiB. Imagens são redimensionadas no cache conforme o modo; animações aceitam até 256 frames e devem caber no orçamento de imagens. FBX e OBJ não são importados. O adaptador Live2D está preparado no código, mas esta distribuição não inclui o Cubism Core nem o renderizador Cubism compilado. A publicação de um app de rastreamento requer aprovação da Live2D.

## Biblioteca e privacidade

Arquivos importados são copiados para a biblioteca local. A biblioteca guarda até 48 avatares; favoritos têm prioridade ao atingir o limite. Recentes guardam até 12. Renomear altera apenas o nome exibido. Miniaturas 3D são geradas a partir da prévia do avatar, quando visível, em até 96 × 96; não capturam a imagem da câmera. Perfis guardam poses, expressões 2D, vínculos 3D, calibração neutra, pet, modelo, enquadramento, ajustes de voz/movimento, desempenho e saída. Carregar um perfil substitui as poses vazias corretamente; um arquivo obrigatório ausente mantém o avatar atual. É possível excluir um perfil sem apagar as imagens. Perfis antigos continuam disponíveis.

Pacotes .avatarpack levam imagens, poses, expressões 2D, modelo 3D e enquadramento. Os arquivos são extraídos em blocos pequenos para reduzir picos de memória. A importação mantém seus dispositivos e modo de desempenho. Pacotes antigos continuam aceitos; pacotes novos com expressões exigem a versão 3.3 ou posterior. Perfis guardam caminhos locais e não são pacotes portáteis. Dados locais ficam em `%USERPROFILE%\.avatarcam_2d`.

Pastas 2D aceitam idle, talk/fala, blink/piscar e pet. A câmera é processada em memória; o app não envia nem grava seus frames. O diagnóstico não inclui imagens da câmera. Configurações da versão anterior são preservadas.

## Atalhos

A tabela mostra os padrões. Em **Configurações → Atalhos de live → Personalizar atalhos**, pressione uma nova combinação ou limpe o campo para desativar a ação. Combinações repetidas e atalhos reservados são rejeitados. A edição suspende os atalhos do app para não disparar ações ao digitar. Restaurar padrões desfaz a personalização.

| Atalho | Ação |
|---|---|
| Ctrl+O | Importar |
| Ctrl+M | Microfone |
| Ctrl+T | Câmera |
| Ctrl+P | Pausar / retomar |
| Ctrl+Shift+O | Saída |
| Espaço | Testar fala |
| F8 | Mostrar / ocultar controles |
| F9 | Pausar / retomar |
| F10 | Microfone |
| Ctrl+Alt+1 | Expressão automática |
| Ctrl+Alt+2…6 | Neutro, feliz, bravo, triste, surpreso |

Os atalhos de live funcionam nos controles e na saída. Para usá-los enquanto outro programa está em foco, marque **Configurações → Atalhos de live → Usar também fora do app**. Essa opção começa desligada; desmarcar libera os atalhos registrados pelo 2DCam. Expressões indisponíveis no personagem são ignoradas.

## Código e créditos

Código principal em avatarcam/desktop e avatarcam/tracking. Com Python 3.12 de 64 bits, execute `scripts/run.bat` para iniciar pelo código ou `scripts/build_exe.bat` para gerar o aplicativo. O resultado é dist/2DCamStudio/; distribua a pasta inteira. O renderizador compilado e os modelos já estão no repositório; Node só é necessário ao alterar o JavaScript. Módulos antigos são mantidos somente para regressão; o executável usa a interface nativa.

Projeto original de RyanSantr; MIT preservada. Modelo de exemplo VRM1_Constraint_Twist_Sample, © 2022 pixiv Inc., arquivo preservado sem alterações. Detector MediaPipe incluído. Fontes, condições e licenças em THIRD_PARTY_NOTICES.txt e third-party-licenses/.
