"""Beat and drop detection from bass energy history."""

import time
from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class BeatEvent:
    """Describes a detected beat or drop."""

    is_beat: bool
    is_drop: bool
    intensity: float  # how far above the threshold (in units of std)
    bpm: float


class BeatDetector:
    """Detects beats and drops from a stream of bass energy values.

    Maintains a rolling history (~0.35 s at 60 fps = 21 frames) and fires
    beat / drop events when the current energy exceeds statistical thresholds.

    Latency notes:
    - Shorter history (21 frames vs 43) means the detector adapts faster to
      changes in loudness and catches beats sooner.
    - Lower MIN_BEAT_INTERVAL (120ms vs 200ms) allows detection of fast beats
      up to ~180 BPM eighth-notes without double-triggering.
    - Slightly lower thresholds compensate for the smaller sample window
      having higher variance.
    """

    HISTORY_LENGTH = 21  # ~0.35 s at 60 fps — fast adaptation
    BEAT_THRESHOLD_STDS = 1.3
    DROP_THRESHOLD_STDS = 2.2
    MIN_BEAT_INTERVAL = 0.120  # seconds — allows fast beats (~180 BPM 8th notes)
    MAX_BEAT_TIMESTAMPS = 16  # for BPM computation
    BPM_MIN = 60.0
    BPM_MAX = 200.0

    def __init__(self) -> None:
        self._history: deque[float] = deque(maxlen=self.HISTORY_LENGTH)
        self._beat_timestamps: deque[float] = deque(maxlen=self.MAX_BEAT_TIMESTAMPS)
        self._last_beat_time: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, bass_energy: float) -> BeatEvent | None:
        """Process one frame of bass energy. Returns a ``BeatEvent`` on a beat, else ``None``."""
        self._history.append(bass_energy)

        # Need at least a few frames to compute meaningful statistics
        if len(self._history) < 4:
            return None

        history_arr = np.array(self._history, dtype=np.float64)
        mean = float(np.mean(history_arr))
        std = float(np.std(history_arr))

        # Avoid triggering on silence
        if std < 1e-10:
            return None

        deviation = (bass_energy - mean) / std  # z-score

        is_beat = deviation >= self.BEAT_THRESHOLD_STDS
        is_drop = deviation >= self.DROP_THRESHOLD_STDS

        if not is_beat:
            return None

        # Enforce minimum interval
        now = time.monotonic()
        if now - self._last_beat_time < self.MIN_BEAT_INTERVAL:
            return None

        self._last_beat_time = now
        self._beat_timestamps.append(now)

        bpm = self._compute_bpm()

        return BeatEvent(
            is_beat=True,
            is_drop=is_drop,
            intensity=float(deviation),
            bpm=bpm,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _compute_bpm(self) -> float:
        """Estimate BPM from the median inter-beat interval of recent beats."""
        if len(self._beat_timestamps) < 2:
            return 0.0

        timestamps = list(self._beat_timestamps)
        intervals = [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]
        median_interval = float(np.median(intervals))

        if median_interval <= 0:
            return 0.0

        bpm = 60.0 / median_interval

        # Clamp to musically reasonable range
        bpm = max(self.BPM_MIN, min(self.BPM_MAX, bpm))
        return round(bpm, 1)
