"""FFT-based audio analysis producing frequency bands, log-spaced bins, and waveforms.

Latency notes:
- FFT window is 1024 samples = 23.2 ms at 44100 Hz.
  This gives ~43 Hz frequency resolution, which is adequate for music
  visualization (sub-bass starts at 20 Hz, bass at 60 Hz).
- Previous 2048-sample window added 23 ms of unnecessary latency.
"""

from dataclasses import dataclass, field

import numpy as np

from audio.capture import AudioData

# Frequency ranges (Hz) for each named band.
BAND_RANGES: dict[str, tuple[float, float]] = {
    "sub_bass": (20.0, 60.0),
    "bass": (60.0, 250.0),
    "low_mid": (250.0, 500.0),
    "mid": (500.0, 2000.0),
    "high_mid": (2000.0, 4000.0),
    "treble": (4000.0, 16000.0),
}

NUM_BINS = 128
WAVEFORM_SIZE = 512

# FFT size — 1024 samples = 23.2 ms at 44100 Hz.
FFT_SIZE = 1024


@dataclass
class AnalysisResult:
    """Container for a single frame of spectral analysis."""

    bands: dict[str, float] = field(default_factory=dict)
    bins: np.ndarray = field(default_factory=lambda: np.zeros(NUM_BINS, dtype=np.float32))
    overall_energy: float = 0.0
    bass_energy: float = 0.0
    left_waveform: np.ndarray = field(default_factory=lambda: np.zeros(WAVEFORM_SIZE, dtype=np.float32))
    right_waveform: np.ndarray = field(default_factory=lambda: np.zeros(WAVEFORM_SIZE, dtype=np.float32))
    stereo_width: float = 0.0


class AudioAnalyzer:
    """Transforms raw ``AudioData`` into spectral and temporal features."""

    def __init__(self, sample_rate: int = 44100) -> None:
        self.sample_rate = sample_rate

        # Pre-compute the Hanning window (matches the 1024-sample mono signal)
        self._window = np.hanning(FFT_SIZE).astype(np.float32)

        # Pre-compute frequency axis for rfft of FFT_SIZE samples
        self._freqs = np.fft.rfftfreq(FFT_SIZE, d=1.0 / self.sample_rate)

        # Pre-compute band index slices
        self._band_slices: dict[str, np.ndarray] = {}
        for name, (lo, hi) in BAND_RANGES.items():
            mask = (self._freqs >= lo) & (self._freqs < hi)
            self._band_slices[name] = mask

        # Pre-compute 128 log-spaced bin edges (20 Hz -> 16 000 Hz)
        self._bin_edges = np.logspace(np.log10(20.0), np.log10(16000.0), NUM_BINS + 1)

        # Pre-compute bin index arrays for vectorized log-bin computation
        self._bin_masks = []
        for i in range(NUM_BINS):
            lo = self._bin_edges[i]
            hi = self._bin_edges[i + 1]
            mask = (self._freqs >= lo) & (self._freqs < hi)
            self._bin_masks.append(mask)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, audio_data: AudioData) -> AnalysisResult:
        """Run full analysis on one frame of audio data.

        Uses the most recent FFT_SIZE samples from the audio snapshot for
        minimal latency — we always analyze the freshest audio available.
        """
        mono = audio_data.mono
        left = audio_data.left
        right = audio_data.right

        # Use the most recent FFT_SIZE samples (the tail of the buffer)
        mono_segment = mono[-FFT_SIZE:]
        left_segment = left[-FFT_SIZE:]
        right_segment = right[-FFT_SIZE:]

        # --- FFT ----------------------------------------------------------
        windowed = mono_segment * self._window
        fft_result = np.fft.rfft(windowed)
        magnitudes = np.abs(fft_result) / FFT_SIZE

        # --- Frequency bands ----------------------------------------------
        bands: dict[str, float] = {}
        for name, mask in self._band_slices.items():
            band_mags = magnitudes[mask]
            bands[name] = float(np.mean(band_mags)) if len(band_mags) > 0 else 0.0

        # --- Log-spaced bins (vectorized) ---------------------------------
        bins = self._compute_log_bins(magnitudes)

        # --- Energies -----------------------------------------------------
        overall_energy = sum(bands.values())
        bass_energy = bands.get("sub_bass", 0.0) + bands.get("bass", 0.0)

        # --- Stereo width -------------------------------------------------
        stereo_width = self._compute_stereo_width(left_segment, right_segment)

        # --- Waveform snippets (last 512 samples) -------------------------
        left_waveform = left[-WAVEFORM_SIZE:].copy()
        right_waveform = right[-WAVEFORM_SIZE:].copy()

        return AnalysisResult(
            bands=bands,
            bins=bins,
            overall_energy=overall_energy,
            bass_energy=bass_energy,
            left_waveform=left_waveform,
            right_waveform=right_waveform,
            stereo_width=stereo_width,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_log_bins(self, magnitudes: np.ndarray) -> np.ndarray:
        """Sum FFT magnitudes into 128 logarithmically-spaced frequency bins.

        Uses pre-computed masks for O(N) vectorized computation instead of
        the previous O(N*BINS) loop that recomputed masks every call.
        """
        bins = np.zeros(NUM_BINS, dtype=np.float32)
        for i, mask in enumerate(self._bin_masks):
            selected = magnitudes[mask]
            if len(selected) > 0:
                bins[i] = float(np.sum(selected))
        return bins

    @staticmethod
    def _compute_stereo_width(left: np.ndarray, right: np.ndarray) -> float:
        """Compute stereo width as 1 - |correlation|.

        Returns 0.0 for perfectly correlated (mono) signals and approaches
        1.0 for fully decorrelated (wide stereo) signals.
        """
        # Guard against silent / constant channels
        if np.std(left) < 1e-10 or np.std(right) < 1e-10:
            return 0.0

        corr = np.corrcoef(left, right)[0, 1]
        return float(1.0 - abs(corr))
