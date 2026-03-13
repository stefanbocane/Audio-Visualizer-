"""
Math utilities for audio smoothing, easing, and real-time signal processing.
"""

import math
import numpy as np


# ---------------------------------------------------------------------------
# Exponential smoothing
# ---------------------------------------------------------------------------

def exp_smooth(current, target, speed, dt):
    """Framerate-independent exponential smoothing.

    Parameters
    ----------
    current : float or np.ndarray
        Current (smoothed) value.
    target : float or np.ndarray
        Raw target value to approach.
    speed : float
        Convergence speed (higher = faster). Typical range 4-50.
    dt : float
        Delta time in seconds since last update.

    Returns
    -------
    float or np.ndarray
        Updated smoothed value.
    """
    factor = 1.0 - math.exp(-speed * dt)
    return current + (target - current) * factor


# ---------------------------------------------------------------------------
# Easing functions
# ---------------------------------------------------------------------------

def ease_out_cubic(t):
    """Cubic ease-out: decelerating to zero velocity.

    Parameters
    ----------
    t : float
        Progress in [0, 1].

    Returns
    -------
    float
    """
    t = max(0.0, min(1.0, t))
    t -= 1.0
    return t * t * t + 1.0


def ease_in_out_quad(t):
    """Quadratic ease in-out: acceleration then deceleration.

    Parameters
    ----------
    t : float
        Progress in [0, 1].

    Returns
    -------
    float
    """
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 2.0 * t * t
    return -1.0 + (4.0 - 2.0 * t) * t


# ---------------------------------------------------------------------------
# Smoothed audio state
# ---------------------------------------------------------------------------

_NUM_BANDS = 6
_NUM_BINS = 128
_WAVEFORM_LEN = 512

# Smoothing speeds (higher = more responsive, lower = smoother).
# Tuned for fluid motion that still feels tight to the music.
# At 60 fps (dt ~0.0167s), speed 18 gives factor ~0.26 (smooth glide).
_BAND_SPEED = 18.0     # fluid band transitions
_BIN_SPEED = 20.0      # spectrum bars glide smoothly
_ENERGY_SPEED = 14.0   # overall energy moves gradually
_BASS_SPEED = 20.0     # bass responsive but not jarring
_BPM_SPEED = 3.0       # BPM drifts slowly
_WAVEFORM_SPEED = 28.0 # waveforms track well but stay smooth
_STEREO_SPEED = 12.0   # stereo width eases in/out

# Decay rates for transient intensities
_BEAT_DECAY = 6.0    # beats linger a bit for fluid falloff
_DROP_DECAY = 2.5    # drops sustain longer for dramatic effect

# Rolling average window (EMA time constant in seconds)
# Shorter window means reaction_scale adapts faster to volume changes
_ROLLING_AVG_TAU = 0.8  # was 2.0


class SmoothedAudioState:
    """Holds smoothed, frame-ready versions of all audio analysis fields.

    Call :meth:`update` once per frame with raw analysis data and the frame
    delta-time. All public attributes are safe to read from the render loop.
    """

    def __init__(self):
        # Frequency data
        self.bands = np.zeros(_NUM_BANDS, dtype=np.float32)
        self.bins = np.zeros(_NUM_BINS, dtype=np.float32)

        # Transient intensities (decay over time)
        self.beat_intensity = 0.0
        self.drop_intensity = 0.0

        # Scalar energy metrics
        self.overall_energy = 0.0
        self.bass_energy = 0.0
        self.bpm = 0.0

        # Waveform buffers (per channel)
        self.left_waveform = np.zeros(_WAVEFORM_LEN, dtype=np.float32)
        self.right_waveform = np.zeros(_WAVEFORM_LEN, dtype=np.float32)

        # Stereo analysis
        self.stereo_width = 0.0

        # Adaptive intensity scaling
        self.reaction_scale = 1.0

        # Internal: rolling average energy for reaction_scale
        self._rolling_energy = 0.0
        self._rolling_initialized = False

    # ------------------------------------------------------------------
    def update(self, raw_data, dt):
        """Ingest a new frame of raw audio analysis and smooth all fields.

        Parameters
        ----------
        raw_data : dict
            Keys should include any subset of:
            ``bands``, ``bins``, ``beat_intensity``, ``drop_intensity``,
            ``overall_energy``, ``bass_energy``, ``bpm``,
            ``left_waveform``, ``right_waveform``, ``stereo_width``.
            Missing keys are silently ignored (values keep decaying /
            holding).
        dt : float
            Time in seconds since the previous call.
        """
        if dt <= 0.0:
            return

        # --- Frequency bands / bins ---
        if "bands" in raw_data:
            target = np.asarray(raw_data["bands"], dtype=np.float32)
            target = _ensure_length(target, _NUM_BANDS)
            self.bands = exp_smooth(self.bands, target, _BAND_SPEED, dt)

        if "bins" in raw_data:
            target = np.asarray(raw_data["bins"], dtype=np.float32)
            target = _ensure_length(target, _NUM_BINS)
            self.bins = exp_smooth(self.bins, target, _BIN_SPEED, dt)

        # --- Beat / drop (set on hit, then decay) ---
        if "beat_intensity" in raw_data:
            incoming = float(raw_data["beat_intensity"])
            # Accept the new value only if it exceeds the current decayed one
            self.beat_intensity = max(self.beat_intensity, incoming)

        if "drop_intensity" in raw_data:
            incoming = float(raw_data["drop_intensity"])
            self.drop_intensity = max(self.drop_intensity, incoming)

        # Apply exponential decay
        self.beat_intensity *= math.exp(-_BEAT_DECAY * dt)
        self.drop_intensity *= math.exp(-_DROP_DECAY * dt)

        # Clamp near-zero to zero to avoid denormals
        if self.beat_intensity < 1e-4:
            self.beat_intensity = 0.0
        if self.drop_intensity < 1e-4:
            self.drop_intensity = 0.0

        # --- Scalar energies ---
        if "overall_energy" in raw_data:
            target = float(raw_data["overall_energy"])
            self.overall_energy = exp_smooth(
                self.overall_energy, target, _ENERGY_SPEED, dt
            )

        if "bass_energy" in raw_data:
            target = float(raw_data["bass_energy"])
            self.bass_energy = exp_smooth(
                self.bass_energy, target, _BASS_SPEED, dt
            )

        if "bpm" in raw_data:
            target = float(raw_data["bpm"])
            self.bpm = exp_smooth(self.bpm, target, _BPM_SPEED, dt)

        # --- Waveforms ---
        if "left_waveform" in raw_data:
            target = np.asarray(raw_data["left_waveform"], dtype=np.float32)
            target = _ensure_length(target, _WAVEFORM_LEN)
            self.left_waveform = exp_smooth(
                self.left_waveform, target, _WAVEFORM_SPEED, dt
            )

        if "right_waveform" in raw_data:
            target = np.asarray(raw_data["right_waveform"], dtype=np.float32)
            target = _ensure_length(target, _WAVEFORM_LEN)
            self.right_waveform = exp_smooth(
                self.right_waveform, target, _WAVEFORM_SPEED, dt
            )

        # --- Stereo width ---
        if "stereo_width" in raw_data:
            target = float(raw_data["stereo_width"])
            self.stereo_width = exp_smooth(
                self.stereo_width, target, _STEREO_SPEED, dt
            )

        # --- Reaction scale (adaptive intensity) ---
        self._update_reaction_scale(dt)

    # ------------------------------------------------------------------
    def _update_reaction_scale(self, dt):
        """Compute reaction_scale = current_energy / rolling_avg_energy."""
        energy = self.overall_energy

        # Bootstrap the rolling average on the first valid frame
        if not self._rolling_initialized:
            if energy > 0.0:
                self._rolling_energy = energy
                self._rolling_initialized = True
            self.reaction_scale = 1.0
            return

        # EMA update: alpha derived from _ROLLING_AVG_TAU time constant
        alpha = 1.0 - math.exp(-dt / _ROLLING_AVG_TAU)
        self._rolling_energy += (energy - self._rolling_energy) * alpha

        # Avoid division by zero
        if self._rolling_energy > 1e-6:
            raw_scale = energy / self._rolling_energy
        else:
            raw_scale = 1.0

        # Clamp to sane range
        self.reaction_scale = max(0.3, min(3.0, raw_scale))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_length(arr, length):
    """Pad or truncate a 1-D numpy array to *length*."""
    if len(arr) >= length:
        return arr[:length]
    padded = np.zeros(length, dtype=arr.dtype)
    padded[: len(arr)] = arr
    return padded
