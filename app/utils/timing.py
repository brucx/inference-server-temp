import time

import structlog

logger = structlog.get_logger()


class Timer:
    def __init__(self):
        self.timings: dict[str, float] = {}
        self.start_times: dict[str, float] = {}

    def start(self, name: str) -> None:
        self.start_times[name] = time.time() * 1000
        logger.debug(f"Timer started: {name}")

    def stop(self, name: str) -> float:
        if name not in self.start_times:
            logger.warning(f"Timer {name} was not started")
            return 0.0

        elapsed_ms = (time.time() * 1000) - self.start_times[name]
        self.timings[name] = elapsed_ms
        del self.start_times[name]

        logger.debug(f"Timer stopped: {name}, elapsed: {elapsed_ms:.2f}ms")
        return elapsed_ms

    def get(self, name: str) -> float | None:
        return self.timings.get(name)

    def get_all_timings(self) -> dict[str, float]:
        return {name: round(time_ms, 2) for name, time_ms in self.timings.items()}

    def reset(self) -> None:
        self.timings.clear()
        self.start_times.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for name in list(self.start_times.keys()):
            self.stop(name)
