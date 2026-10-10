"""Enumera o mesmo backend DirectShow usado pelo OpenCV, sem abrir a câmera."""
import os


def camera_devices():
    if os.name != 'nt':
        return []
    import ctypes as ct
    import uuid
    class GUID(ct.Structure):
        _fields_ = [('bytes', ct.c_ubyte * 16)]
    def guid(value):
        return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)
    def method(pointer, index, result, *arguments):
        table = ct.cast(pointer, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
        return ct.WINFUNCTYPE(result, ct.c_void_p, *arguments)(table[index])
    def release(pointer):
        if pointer: method(pointer, 2, ct.c_ulong)(pointer)
    ole = ct.OleDLL('ole32'); auto = ct.OleDLL('oleaut32')
    ole.CoInitializeEx.argtypes = [ct.c_void_p, ct.c_ulong]
    ole.CoCreateInstance.argtypes = [ct.POINTER(GUID), ct.c_void_p, ct.c_ulong, ct.POINTER(GUID), ct.POINTER(ct.c_void_p)]
    auto.VariantClear.argtypes = [ct.c_void_p]
    initialized = False; enumerator = ct.c_void_p(); devices = ct.c_void_p()
    result = []
    try:
        ole.CoInitializeEx(None, 2); initialized = True
        ole.CoCreateInstance(ct.byref(guid('62be5d10-60eb-11d0-bd3b-00a0c911ce86')), None, 1,
                             ct.byref(guid('29840822-5b84-11d0-bd3b-00a0c911ce86')), ct.byref(enumerator))
        status = method(enumerator, 3, ct.c_long, ct.POINTER(GUID), ct.POINTER(ct.c_void_p), ct.c_ulong)(
            enumerator, ct.byref(guid('860bb310-5d01-11d0-bd3b-00a0c911ce86')), ct.byref(devices), 0)
        if status != 0: return []
        index = 0
        while index < 32:
            moniker = ct.c_void_p(); fetched = ct.c_ulong(); bag = ct.c_void_p()
            status = method(devices, 3, ct.c_long, ct.c_ulong, ct.POINTER(ct.c_void_p), ct.POINTER(ct.c_ulong))(
                devices, 1, ct.byref(moniker), ct.byref(fetched))
            if status != 0: break
            try:
                status = method(moniker, 9, ct.c_long, ct.c_void_p, ct.c_void_p, ct.POINTER(GUID), ct.POINTER(ct.c_void_p))(
                    moniker, None, None, ct.byref(guid('55272a00-42cb-11ce-8135-00aa004bb851')), ct.byref(bag))
                if status < 0: raise OSError('Falha ao ler o dispositivo de câmera.')
                values = {}
                for key in ('FriendlyName', 'DevicePath'):
                    variant = ct.create_string_buffer(24)
                    try:
                        status = method(bag, 3, ct.c_long, ct.c_wchar_p, ct.c_void_p, ct.c_void_p)(bag, key, variant, None)
                        if status == 0 and ct.c_ushort.from_buffer(variant).value == 8:
                            address = ct.c_void_p.from_buffer(variant, 8).value
                            if address: values[key] = ct.wstring_at(address)
                    finally: auto.VariantClear(variant)
                result.append({'index': index, 'name': values.get('FriendlyName', f'Câmera {index+1}'),
                               'id': values.get('DevicePath', '')})
            finally:
                release(bag); release(moniker)
            index += 1
        return result
    except OSError:
        return []
    finally:
        release(devices); release(enumerator)
        if initialized: ole.CoUninitialize()


def resolve_camera(devices, identity='', index=0):
    if identity:
        match = next((item for item in devices if item['id'] == identity), None)
        if not match: raise RuntimeError('Aguardando a câmera selecionada ser reconectada.')
        return match['index']
    if devices and not any(item['index'] == index for item in devices):
        raise RuntimeError('Câmera selecionada não encontrada.')
    return index
