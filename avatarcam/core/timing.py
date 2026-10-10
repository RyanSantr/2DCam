import time


class Deadline:
    def __init__(self, seconds: float, clock=time.monotonic):
        self.clock = clock
        self.end = clock() + seconds

    @property
    def remaining(self) -> float:
        return max(0.0, self.end - self.clock())

    @property
    def active(self) -> bool:
        return self.remaining > 0


def calibrate_noise(samples: list[float]) -> tuple[float, float]:
    values = sorted(samples or [.01])
    # Percentil 85: um clique isolado nao determina toda a sensibilidade.
    floor = values[min(len(values) - 1, int((len(values) - 1) * .85))]
    return floor, max(.04, min(.7, floor * 2.7 + .035))
