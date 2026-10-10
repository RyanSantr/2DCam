from PyInstaller.utils.hooks import copy_metadata

# O pacote com wheels usa este nome de distribuicao, mantendo import webrtcvad.
datas = copy_metadata('webrtcvad-wheels')
hiddenimports = ['_webrtcvad']
