"""Tamanhos compartilhados pelo editor, perfis e janela de captura."""
OUTPUT_SIZES = {
    '540p': (960, 540),
    '360p': (640, 360),
    '720p': (1280, 720),
    '1080p': (1920, 1080),
    'portrait720': (720, 1280),
    'portrait1080': (1080, 1920),
}


def output_size(key):
    return OUTPUT_SIZES.get(key, OUTPUT_SIZES['540p'])
