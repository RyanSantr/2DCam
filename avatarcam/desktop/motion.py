"""Movimento leve e prévia de rosto; não abre câmera nem carrega detector."""
import math

FIELDS = ('yaw', 'pitch', 'roll', 'jaw', 'blinkLeft', 'blinkRight',
          'smile', 'frown', 'surprise', 'gazeX', 'gazeY')


def pose(values=None):
    values = values if isinstance(values, dict) else {}
    result = {'detected': True}
    for key in FIELDS:
        number = values.get(key, 0.)
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number): number = 0.
        signed = key in ('yaw', 'pitch', 'roll', 'gazeX', 'gazeY')
        limit = .8 if key in ('yaw', 'pitch', 'roll') else 1.
        result[key] = max(-limit if signed else 0., min(limit, number))
    return result


class IdleMotion:
    def __init__(self): self.elapsed = 0.

    def advance(self, dt, strength, level=0., speaking=False):
        self.elapsed += max(0., min(.2, dt))
        t = self.elapsed
        voice = min(1., max(0., level)) if speaking else 0.
        # Ondas lentas e pequenas; o áudio acrescenta um aceno discreto.
        blink_phase = t % 4.7
        blink = math.sin(blink_phase / .18 * math.pi) if blink_phase < .18 and t > .2 else 0.
        return pose(dict(yaw=math.sin(t * .51) * .045 * strength,
                         pitch=(math.sin(t * .79) * .027 + math.sin(t * 4.1) * voice * .045) * strength,
                         roll=math.sin(t * .37) * .022 * strength,
                         gazeX=math.sin(t * .31) * .10 * strength,
                         gazeY=math.sin(t * .43) * .06 * strength,
                         blinkLeft=blink, blinkRight=blink))


class MotionPreview:
    def __init__(self): self.stop()

    def stop(self): self.active = False; self.sequence = False; self.values = pose(); self.started = 0.

    def start(self, values, now, sequence=False):
        self.active = True; self.sequence = bool(sequence); self.started = now; self.values = pose(values)

    def sample(self, now):
        if not self.active: return None
        if not self.sequence: return dict(self.values)
        t = max(0., now - self.started)
        if t >= 12:
            self.stop(); return None
        phase = t % 3 / 3
        wave = math.sin(phase * math.pi * 2)
        if t < 3: return pose(dict(yaw=wave * .4, pitch=wave * .16, roll=wave * .12))
        if t < 6: return pose(dict(gazeX=wave * .6, gazeY=wave * .4))
        if t < 9: return pose(dict(jaw=abs(wave) * .8))
        blink = math.sin(phase / .15 * math.pi) if phase < .15 else 0.
        return pose(dict(blinkLeft=blink, blinkRight=blink, smile=abs(wave) * .7))
