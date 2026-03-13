"""
Aurora Borealis color palette and interpolation utilities.

All colors are RGB tuples normalized to 0.0-1.0 for OpenGL compatibility.
"""

import math


# ---------------------------------------------------------------------------
# Named palette colours (RGB, each channel 0-1)
# ---------------------------------------------------------------------------

AURORA_PALETTE = {
    "deep_space":   (0.02, 0.05, 0.08),
    "teal":         (0.0,  0.6,  0.6),
    "emerald":      (0.0,  0.8,  0.4),
    "green":        (0.2,  1.0,  0.3),
    "violet":       (0.6,  0.2,  0.9),
    "ice_blue":     (0.5,  0.9,  1.0),
    "white_flash":  (1.0,  1.0,  1.0),
}

# Ordered sequence used by palette_gradient
_GRADIENT_ORDER = [
    AURORA_PALETTE["deep_space"],
    AURORA_PALETTE["teal"],
    AURORA_PALETTE["emerald"],
    AURORA_PALETTE["green"],
    AURORA_PALETTE["violet"],
    AURORA_PALETTE["ice_blue"],
    AURORA_PALETTE["white_flash"],
]


# ---------------------------------------------------------------------------
# Interpolation helpers
# ---------------------------------------------------------------------------

def lerp_color(a, b, t):
    """Linearly interpolate between two RGB tuples *a* and *b*.

    Parameters
    ----------
    a, b : tuple[float, float, float]
        Source and destination colours (each channel 0-1).
    t : float
        Blend factor clamped to [0, 1].

    Returns
    -------
    tuple[float, float, float]
    """
    t = max(0.0, min(1.0, t))
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def aurora_color(energy, beat_intensity):
    """Map an energy level and beat intensity to an Aurora Borealis colour.

    Parameters
    ----------
    energy : float
        Overall energy in roughly [0, 1] (can exceed 1 for peaks).
    beat_intensity : float
        Instantaneous beat strength in [0, 1].

    Returns
    -------
    tuple[float, float, float]
        RGB colour (each channel 0-1).
    """
    deep_space = AURORA_PALETTE["deep_space"]
    teal       = AURORA_PALETTE["teal"]
    emerald    = AURORA_PALETTE["emerald"]
    green      = AURORA_PALETTE["green"]
    violet     = AURORA_PALETTE["violet"]
    ice_blue   = AURORA_PALETTE["ice_blue"]
    white      = AURORA_PALETTE["white_flash"]

    # Flash on extreme beats
    if beat_intensity > 0.95:
        return lerp_color(ice_blue, white, (beat_intensity - 0.95) / 0.05)

    # Energy-based base colour
    if energy < 0.25:
        # Low energy: deep teal region
        t = energy / 0.25
        base = lerp_color(deep_space, teal, t)
    elif energy < 0.5:
        # Medium-low: teal -> emerald
        t = (energy - 0.25) / 0.25
        base = lerp_color(teal, emerald, t)
    elif energy < 0.7:
        # Medium-high: emerald -> green
        t = (energy - 0.5) / 0.2
        base = lerp_color(emerald, green, t)
    elif energy < 0.9:
        # High: green -> violet
        t = (energy - 0.7) / 0.2
        base = lerp_color(green, violet, t)
    else:
        # Peak: violet -> ice blue
        t = (energy - 0.9) / 0.1
        base = lerp_color(violet, ice_blue, t)

    # Blend toward violet/ice on strong beats
    if beat_intensity > 0.5:
        beat_t = (beat_intensity - 0.5) / 0.5
        base = lerp_color(base, violet, beat_t * 0.6)

    return base


def palette_gradient(t):
    """Smoothly interpolate across the full Aurora palette.

    Parameters
    ----------
    t : float
        Position along the gradient, clamped to [0, 1].
        0 = deep_space, 1 = white_flash.

    Returns
    -------
    tuple[float, float, float]
    """
    t = max(0.0, min(1.0, t))
    n = len(_GRADIENT_ORDER) - 1  # number of segments
    scaled = t * n
    idx = int(scaled)
    if idx >= n:
        return _GRADIENT_ORDER[-1]
    frac = scaled - idx
    return lerp_color(_GRADIENT_ORDER[idx], _GRADIENT_ORDER[idx + 1], frac)
