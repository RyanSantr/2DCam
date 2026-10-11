"""Estado pequeno para expressões, gestos, histórico e qualidade adaptativa."""
from copy import deepcopy
import math

GESTURES = {'wave': 'Acenar', 'yes': 'Concordar', 'no': 'Negar', 'celebrate': 'Comemorar'}
EXPRESSION_ACTIONS = ('neutral', 'happy', 'angry', 'sad', 'relaxed', 'surprised', 'mouth', 'blink')


def neutral_pose(value):
    value = value if isinstance(value, dict) else {}
    return {key: max(-.8,min(.8,number)) if isinstance(number,(int,float)) and not isinstance(number,bool) and math.isfinite(number) else 0.
            for key in ('yaw','pitch','roll') for number in [value.get(key,0.)]}


def expression_config(value):
    result = {}
    if not isinstance(value, dict): return result
    for action, entry in value.items():
        if action not in EXPRESSION_ACTIONS or not isinstance(entry, dict): continue
        target = entry.get('target', action)
        intensity = entry.get('intensity', 1.)
        if not isinstance(target, str) or len(target) > 100: continue
        if isinstance(intensity, bool) or not isinstance(intensity, (int, float)) or not math.isfinite(intensity): intensity = 1.
        result[action] = dict(target=target, intensity=max(0., min(1., intensity)))
    return result


class History:
    """Guarda configurações; nunca imagens, modelos ou frames de câmera."""
    def __init__(self, limit=20):
        self.undo = []; self.redo = []; self.limit = limit

    def push(self, state):
        if not self.undo or self.undo[-1] != state:
            self.undo.append(deepcopy(state)); self.undo = self.undo[-self.limit:]
        self.redo.clear()

    def back(self, current):
        if not self.undo: return None
        self.redo.append(deepcopy(current)); return self.undo.pop()

    def forward(self, current):
        if not self.redo: return None
        self.undo.append(deepcopy(current)); return self.redo.pop()


class AdaptiveQuality:
    """Reduz por carga sustentada; sobe somente após 30 segundos estáveis."""
    order = ('economy', 'balanced', 'quality')

    def __init__(self): self.reset()
    def reset(self):
        self.key = 'balanced'; self.slow = self.good = 0; self.changed_at = -100.

    def sample(self, now, fps, target, lag, active=True):
        if not active:
            self.slow = self.good = 0; return None
        slow = lag > .12 or (fps is not None and fps < target * .72)
        self.slow = self.slow + 1 if slow else 0
        self.good = self.good + 1 if not slow and lag < .07 and (fps is None or fps >= target * .9) else 0
        index = self.order.index(self.key)
        if self.slow >= 3 and index > 0 and now - self.changed_at >= 8:
            index -= 1
        elif self.good >= 15 and index < 2 and now - self.changed_at >= 30:
            index += 1
        else: return None
        self.key = self.order[index]; self.changed_at = now; self.slow = self.good = 0
        return self.key


def helpful_issues(controller):
    issues = []
    if controller.paused: return [('Pausado', 'Retome para animar o personagem.', 'resume')]
    if controller.inputs.wanted['camera']:
        if not controller.tracker.running:
            issues.append(('Câmera desconectada', controller.inputs.status['camera'] or 'Confira a conexão e as permissões da câmera.', 'devices'))
        elif not controller.face['detected']:
            issues.append(('Rosto não encontrado', 'Olhe para a câmera e ilumine o rosto. Abra a prévia para conferir.', 'camera'))
    if controller.inputs.wanted['audio']:
        if not controller.microphone.is_running:
            issues.append(('Microfone desconectado', controller.inputs.status['audio'] or 'Confira o microfone selecionado.', 'devices'))
        elif getattr(controller, 'quiet_since', None) is not None and controller.last_tick - controller.quiet_since > 12:
            issues.append(('Entrada de áudio baixa', 'Se estiver falando, confira o microfone e calibre a sensibilidade.', 'audio'))
    report = controller.renderer_report
    if report.get('error'): issues.append(('Avatar não abriu', str(report['error'])[:220], 'reload'))
    if controller.mode != '2D' and report.get('loaded'):
        if not report.get('hasMouth', True): issues.append(('Modelo sem boca configurada', 'Abra o editor de expressões e escolha a expressão de boca, se o modelo tiver uma.', 'expressions'))
        if report.get('triangles', 0) > 150000 or report.get('textures', 0) > 40:
            issues.append(('Modelo pesado', 'Experimente o desempenho automático ou Econômico.', 'performance'))
    if getattr(controller, 'spout_error', ''): issues.append(('Saída transparente indisponível', controller.spout_error, 'output'))
    return issues
