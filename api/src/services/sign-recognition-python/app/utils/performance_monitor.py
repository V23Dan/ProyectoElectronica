# app/utils/performance_monitor.py
import time
import logging
from collections import deque
from typing import Dict, Optional

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    def __init__(self, window_size: int = 60):
        self.window_size = window_size
        self.frame_times = deque(maxlen=window_size)
        self.start_time = None
        self.last_metrics_time = 0.0
        self.metrics_interval = 5.0  # seg
        self.last_metrics = {}

    def start_frame(self):
        """Marca inicio de procesamiento de frame."""
        self.start_time = time.perf_counter()

    def end_frame(self):
        """Marca fin de frame y registra duración."""
        if self.start_time is None:
            return
        duration = time.perf_counter() - self.start_time
        self.frame_times.append(duration)
        self.start_time = None

    def get_fps(self) -> float:
        """Calcula FPS promedio."""
        if not self.frame_times:
            return 0.0
        avg_time = sum(self.frame_times) / len(self.frame_times)
        return 1.0 / avg_time if avg_time > 0 else 0.0

    def get_system_usage(self) -> Optional[Dict[str, float]]:
        """Devuelve uso actual de CPU y RAM (si psutil disponible)."""
        if psutil is None:
            return None
        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_percent": psutil.virtual_memory().percent
        }

    def maybe_log_metrics(self):
        """Imprime métricas cada cierto tiempo."""
        now = time.time()
        if now - self.last_metrics_time >= self.metrics_interval:
            fps = self.get_fps()
            sys_usage = self.get_system_usage()
            msg = f"FPS: {fps:.1f}"
            if sys_usage:
                msg += f" | CPU: {sys_usage['cpu_percent']:.0f}% | RAM: {sys_usage['ram_percent']:.0f}%"
            logger.info(msg)
            self.last_metrics_time = now
            self.last_metrics = {"fps": fps, **(sys_usage or {})}
