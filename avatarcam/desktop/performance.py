"""Orcamentos de trabalho e medicao local, sem amostragem bloqueante."""
import os
import time

PRESETS = {
    'economy': dict(name='Econômico', fps=24, tracking_fps=12, camera_width=320, camera_height=240, pixel_ratio=.75, cache_mb=32, pixmap_mb=16, image_side=960),
    'balanced': dict(name='Equilibrado', fps=30, tracking_fps=20, camera_width=480, camera_height=360, pixel_ratio=1., cache_mb=64, pixmap_mb=24, image_side=1280),
    'quality': dict(name='Qualidade', fps=60, tracking_fps=30, camera_width=640, camera_height=480, pixel_ratio=1.5, cache_mb=96, pixmap_mb=32, image_side=1600),
}

def preset(key):
    return dict(PRESETS.get(key,PRESETS['balanced']))

class ProcessUsage:
    def __init__(self):
        self.previous={}; self.at=time.monotonic()
    def sample(self):
        try:
            import psutil
            process=psutil.Process(os.getpid())
            processes=[process]+process.children(recursive=True)
            current={}; rss=private=cpu=0; now=time.monotonic()
            for item in processes:
                try:
                    memory=item.memory_info(); rss+=memory.rss
                    # private nao conta novamente paginas compartilhadas entre processos.
                    private+=getattr(item.memory_full_info(),'uss',memory.rss)
                    times=item.cpu_times(); total=times.user+times.system; current[item.pid]=total
                    if item.pid in self.previous: cpu+=max(0,total-self.previous[item.pid])
                except psutil.Error: pass
            interval=max(.001,now-self.at); self.previous=current; self.at=now
            return dict(rss_mb=round(rss/1048576,1),private_mb=round(private/1048576,1),
                        cpu_one_core_percent=round(cpu/interval*100,1),processes=len(current))
        except (ImportError,OSError):
            return {}
