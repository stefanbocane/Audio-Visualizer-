"""Audio capture module using sounddevice with low-latency ring buffers."""

import threading
from dataclasses import dataclass, field

import numpy as np
import sounddevice as sd


@dataclass
class AudioData:
    """Snapshot of captured audio data for renderer consumption."""

    left: np.ndarray = field(default_factory=lambda: np.zeros(1024, dtype=np.float32))
    right: np.ndarray = field(default_factory=lambda: np.zeros(1024, dtype=np.float32))
    mono: np.ndarray = field(default_factory=lambda: np.zeros(1024, dtype=np.float32))


class AudioCapture:
    """Captures audio from a system device (e.g. BlackHole) with low-latency buffering.

    The audio callback continuously fills a ring buffer per channel. On each
    callback invocation the latest SNAPSHOT_SIZE samples are copied into the
    *write* AudioData buffer, then the write and read references are atomically
    swapped so the renderer always gets a consistent snapshot.

    Latency-critical settings (at 44100 Hz):
    - block_size=256  -> 5.8 ms per callback invocation
    - SNAPSHOT_SIZE=1024 -> 23.2 ms of audio per analysis frame
    - RING_SIZE=2048 -> enough headroom for the ring buffer
    """

    RING_SIZE = 2048
    SNAPSHOT_SIZE = 1024

    def __init__(
        self,
        device_name: str = "BlackHole",
        sample_rate: int = 44100,
        block_size: int = 256,
        channels: int = 2,
    ) -> None:
        self.device_name = device_name
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.channels = channels

        # Ring buffers – one per channel
        self._ring_left = np.zeros(self.RING_SIZE, dtype=np.float32)
        self._ring_right = np.zeros(self.RING_SIZE, dtype=np.float32)
        self._write_pos = 0

        # Double buffers
        self._write_buffer = AudioData()
        self._read_buffer = AudioData()
        self._lock = threading.Lock()

        # Resolve the device index — try requested device, then fall back
        self._device_index, self.device_name = self._resolve_device_with_fallback(device_name)

        self._stream: sd.InputStream | None = None

    # ------------------------------------------------------------------
    # Device helpers
    # ------------------------------------------------------------------

    @staticmethod
    def list_devices() -> list[dict]:
        """Return the list of available audio devices as dicts."""
        devices = sd.query_devices()
        result = []
        for i, dev in enumerate(devices):
            result.append({"index": i, "name": dev["name"], "max_input_channels": dev["max_input_channels"]})
        return result

    @classmethod
    def _resolve_device_with_fallback(cls, device_name: str) -> tuple[int, str]:
        """Find the device index whose name contains *device_name*.

        Falls back to the default input device (microphone) if the requested
        device is not found.

        Returns (device_index, actual_device_name).
        """
        devices = sd.query_devices()

        # Try the requested device first
        for i, dev in enumerate(devices):
            if device_name.lower() in dev["name"].lower() and dev["max_input_channels"] > 0:
                return i, dev["name"]

        # Fallback: use the default input device (microphone)
        print(f"Audio device '{device_name}' not found — falling back to microphone.")
        print("For best results, install BlackHole: https://existential.audio/blackhole/")
        default_input = sd.default.device[0]
        if default_input is not None and default_input >= 0:
            dev = devices[default_input]
            if dev["max_input_channels"] > 0:
                print(f"Using: {dev['name']}")
                return int(default_input), dev["name"]

        # Last resort: find any input device
        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                print(f"Using: {dev['name']}")
                return i, dev["name"]

        available = "\n".join(
            f"  [{i}] {dev['name']}  (inputs: {dev['max_input_channels']})"
            for i, dev in enumerate(devices)
        )
        raise RuntimeError(
            f"No audio input devices found.\n"
            f"Available devices:\n{available}"
        )

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Open the input stream and begin capturing audio."""
        if self._stream is not None:
            return

        self._stream = sd.InputStream(
            device=self._device_index,
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            channels=self.channels,
            dtype="float32",
            latency="low",
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop and close the input stream."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    # ------------------------------------------------------------------
    # Callback & buffer management
    # ------------------------------------------------------------------

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time,  # noqa: A002 – sd callback signature
        status: sd.CallbackFlags,
    ) -> None:
        """Called by sounddevice on each audio block (runs in a C-level thread)."""
        if status:
            # Xruns or other warnings – silently continue
            pass

        # Write incoming samples into the ring buffers
        n = frames
        pos = self._write_pos % self.RING_SIZE

        if self.channels >= 2:
            left_chunk = indata[:, 0]
            right_chunk = indata[:, 1]
        else:
            left_chunk = indata[:, 0]
            right_chunk = left_chunk

        # Handle wrap-around
        if pos + n <= self.RING_SIZE:
            self._ring_left[pos : pos + n] = left_chunk
            self._ring_right[pos : pos + n] = right_chunk
        else:
            first = self.RING_SIZE - pos
            self._ring_left[pos:] = left_chunk[:first]
            self._ring_left[: n - first] = left_chunk[first:]
            self._ring_right[pos:] = right_chunk[:first]
            self._ring_right[: n - first] = right_chunk[first:]

        self._write_pos += n

        # Snapshot the latest SNAPSHOT_SIZE samples into the write buffer
        end = self._write_pos % self.RING_SIZE
        if self._write_pos >= self.SNAPSHOT_SIZE:
            left_snap = self._roll_snapshot(self._ring_left, end)
            right_snap = self._roll_snapshot(self._ring_right, end)
        else:
            left_snap = np.zeros(self.SNAPSHOT_SIZE, dtype=np.float32)
            right_snap = np.zeros(self.SNAPSHOT_SIZE, dtype=np.float32)

        mono_snap = (left_snap + right_snap) * 0.5

        self._write_buffer.left = left_snap
        self._write_buffer.right = right_snap
        self._write_buffer.mono = mono_snap

        # Swap double buffer
        self.swap_buffers()

    def _roll_snapshot(self, ring: np.ndarray, end: int) -> np.ndarray:
        """Extract the last SNAPSHOT_SIZE samples from a ring buffer ending at *end*."""
        start = end - self.SNAPSHOT_SIZE
        if start >= 0:
            return ring[start:end].copy()
        else:
            return np.concatenate((ring[start:], ring[:end])).copy()

    def swap_buffers(self) -> None:
        """Atomically swap the read and write buffer references."""
        with self._lock:
            self._read_buffer, self._write_buffer = self._write_buffer, self._read_buffer

    def get_audio_data(self) -> AudioData:
        """Return the current read buffer (safe to call from any thread)."""
        with self._lock:
            return self._read_buffer
