"""Orchestrates the full per-frame render pipeline.

Draws every visual element into the scene FBO, applies bloom post-processing,
composites scene + bloom + motion-blur feedback + flash onto the default
framebuffer, and finally overlays the HUD.
"""

from __future__ import annotations

import math
import logging
from typing import TYPE_CHECKING

import moderngl

from renderer.context import RenderContext
from renderer.bloom import BloomProcessor

if TYPE_CHECKING:
    from utils.math_utils import SmoothedAudioState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional visual-element renderers.  Each import is wrapped so that the
# pipeline keeps working even when some modules have not been written yet.
# ---------------------------------------------------------------------------

def _try_import(module_path: str, class_name: str):
    """Attempt to import *class_name* from *module_path*.

    Returns the class on success, or ``None`` if the module is not yet
    available.
    """
    try:
        mod = __import__(module_path, fromlist=[class_name])
        return getattr(mod, class_name)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Optional renderer %s.%s not available: %s", module_path, class_name, exc)
        return None


BackgroundRenderer   = _try_import("renderer.background",      "BackgroundRenderer")
OrbRenderer          = _try_import("renderer.orb",              "OrbRenderer")
FrequencyBarsRenderer = _try_import("renderer.frequency_bars",  "FrequencyBarsRenderer")
ParticleRenderer     = _try_import("renderer.particles",        "ParticleRenderer")
DNAHelixRenderer     = _try_import("renderer.dna_helix",        "DNAHelixRenderer")
ShockwaveRenderer    = _try_import("renderer.shockwave",        "ShockwaveRenderer")
WarpTunnelRenderer   = _try_import("renderer.warp_tunnel",      "WarpTunnelRenderer")
LissajousRenderer    = _try_import("renderer.lissajous",        "LissajousRenderer")
HUDRenderer          = _try_import("renderer.hud",              "HUDRenderer")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class RenderPipeline:
    """Full per-frame render pipeline for the music visualizer.

    Order of operations
    -------------------
    1. Draw all visual elements into ``fbo_scene``.
    2. Run bloom post-processing (extract + 2-pass blur).
    3. Composite scene + bloom + previous-frame feedback + flash to screen.
    4. Copy the composited frame into ``fbo_previous`` for next-frame feedback.
    5. Overlay the HUD (Lissajous scope, BPM readout, etc.).
    """

    def __init__(self, ctx: RenderContext) -> None:
        self.ctx = ctx

        # -- Instantiate visual-element renderers (None if not yet written) --
        self.background   = BackgroundRenderer(ctx)   if BackgroundRenderer   else None
        self.orb           = OrbRenderer(ctx)          if OrbRenderer          else None
        self.freq_bars     = FrequencyBarsRenderer(ctx) if FrequencyBarsRenderer else None
        self.particles     = ParticleRenderer(ctx)     if ParticleRenderer     else None
        self.dna_helix     = DNAHelixRenderer(ctx)     if DNAHelixRenderer     else None
        self.shockwave_renderer = ShockwaveRenderer(ctx) if ShockwaveRenderer else None
        self.warp_tunnel   = WarpTunnelRenderer(ctx)   if WarpTunnelRenderer   else None
        self.lissajous     = LissajousRenderer(ctx)    if LissajousRenderer    else None
        self.hud           = HUDRenderer(ctx)          if HUDRenderer          else None

        # -- Post-processing ------------------------------------------------
        self.bloom = BloomProcessor(ctx)

        # -- Composite shader (scene + bloom + feedback + flash) ------------
        self.composite_program = ctx.create_program(
            "fullscreen_quad.vert", "composite.frag"
        )

        # -- Frame state ----------------------------------------------------
        self.time: float = 0.0
        self.flash_intensity: float = 0.0

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def render(self, audio_state: SmoothedAudioState, dt: float) -> None:
        """Execute the full render pipeline for one frame.

        Parameters
        ----------
        audio_state : SmoothedAudioState
            Smoothed audio analysis data for this frame.
        dt : float
            Delta time in seconds since the previous frame.
        """
        # 1. Advance time counter
        self.time += dt

        # 2. React to beats and drops
        self._handle_beat_reactions(audio_state, dt)

        # 3. Render scene elements into fbo_scene
        self._render_scene(audio_state, dt)

        # 4. Bloom post-processing
        bloom_texture = self.bloom.process(self.ctx.tex_scene)

        # 5. Composite to default framebuffer (screen)
        self._composite(bloom_texture, audio_state)

        # 6. Copy result into fbo_previous for next-frame motion-blur
        self._copy_to_previous()

        # 7. HUD overlay (drawn directly onto the default framebuffer)
        self._render_hud(audio_state, dt)

    # ------------------------------------------------------------------
    # Beat / drop reactions
    # ------------------------------------------------------------------

    def _handle_beat_reactions(
        self, audio_state: SmoothedAudioState, dt: float
    ) -> None:
        """Update flash and shockwave state based on beat/drop events."""
        reaction_scale = getattr(audio_state, "reaction_scale", 1.0)

        # No white flash — beats expressed through movement only

        # Drop: trigger shockwave (no flash)
        if audio_state.drop_intensity > 0.5:
            if self.shockwave_renderer is not None and not self.shockwave_renderer.active:
                self.shockwave_renderer.trigger()

        self.flash_intensity = 0.0

        # Advance shockwave animation
        if self.shockwave_renderer is not None:
            self.shockwave_renderer.update(dt)

    # ------------------------------------------------------------------
    # Scene rendering (into fbo_scene)
    # ------------------------------------------------------------------

    def _render_scene(self, audio_state: SmoothedAudioState, dt: float) -> None:
        """Draw all visual elements into ``fbo_scene``."""
        self.ctx.fbo_scene.use()
        self.ctx.ctx.viewport = (0, 0, self.ctx.width, self.ctx.height)
        self.ctx.fbo_scene.clear(0.0, 0.0, 0.0, 1.0)

        # a) Background (no blending -- fully opaque base layer)
        self.ctx.set_no_blending()
        if self.background is not None:
            self.background.render(audio_state, self.time)

        # b) Switch to additive blending for luminous elements
        self.ctx.set_additive_blending()

        # c) Frequency bars
        if self.freq_bars is not None:
            self.freq_bars.render(audio_state, self.time)

        # d) Central orb
        if self.orb is not None:
            self.orb.render(audio_state, self.time)

        # e) DNA helix
        if self.dna_helix is not None:
            self.dna_helix.render(audio_state, self.time)

        # f) Particles (physics update + draw)
        if self.particles is not None:
            self.particles.update(audio_state, dt)
            self.particles.render(audio_state, self.time)

        # g) Shockwave (uses its own internal state via trigger/update)
        if self.shockwave_renderer is not None and self.shockwave_renderer.active:
            self.shockwave_renderer.render(audio_state, self.time)

        # h) Warp tunnel
        if self.warp_tunnel is not None:
            self.warp_tunnel.render(audio_state, self.time)

    # ------------------------------------------------------------------
    # Composite pass
    # ------------------------------------------------------------------

    def _composite(self, bloom_texture: moderngl.Texture,
                   audio_state: "SmoothedAudioState | None" = None) -> None:
        """Combine scene, bloom, previous-frame feedback, and flash."""
        self.ctx.ctx.screen.use()
        self.ctx.ctx.viewport = (0, 0, self.ctx.width, self.ctx.height)
        self.ctx.ctx.screen.clear(0.0, 0.0, 0.0, 1.0)
        self.ctx.set_no_blending()

        # Bind textures to consecutive texture units.
        self.ctx.tex_scene.use(location=0)
        bloom_texture.use(location=1)
        self.ctx.tex_previous.use(location=2)

        prog = self.composite_program
        self._try_set(prog, "u_scene", 0)
        self._try_set(prog, "u_bloom", 1)
        self._try_set(prog, "u_previous_frame", 2)
        self._try_set(prog, "u_flash_intensity", self.flash_intensity)
        self._try_set(prog, "u_motion_blur_strength", 0.85)
        self._try_set(prog, "u_time", self.time)

        # Audio-reactive uniforms for chromatic aberration, vignette, grain
        if audio_state is not None:
            self._try_set(prog, "u_beat_intensity",
                          getattr(audio_state, "beat_intensity", 0.0))
            self._try_set(prog, "u_bass_energy",
                          getattr(audio_state, "bass_energy", 0.0))
        self._try_set(prog, "u_resolution",
                      (float(self.ctx.width), float(self.ctx.height)))

        self.ctx.render_fullscreen_quad(prog)

    # ------------------------------------------------------------------
    # Motion-blur feedback copy
    # ------------------------------------------------------------------

    def _copy_to_previous(self) -> None:
        """Blit the current default framebuffer into ``fbo_previous``."""
        self.ctx.ctx.copy_framebuffer(
            dst=self.ctx.fbo_previous,
            src=self.ctx.ctx.screen,
        )

    # ------------------------------------------------------------------
    # HUD overlay
    # ------------------------------------------------------------------

    def _render_hud(self, audio_state: SmoothedAudioState, dt: float) -> None:
        """Draw HUD elements on top of the composited image."""
        # Ensure we are drawing onto the default framebuffer.
        self.ctx.ctx.screen.use()
        self.ctx.set_alpha_blending()

        # Lissajous scope (small viewport in a corner)
        if self.lissajous is not None:
            scope_size = min(self.ctx.width, self.ctx.height) // 5
            margin = 20
            self.ctx.ctx.viewport = (
                margin,
                margin,
                scope_size,
                scope_size,
            )
            self.lissajous.render(audio_state, self.time)

        # HUD text / overlays (full viewport)
        if self.hud is not None:
            self.ctx.ctx.viewport = (0, 0, self.ctx.width, self.ctx.height)
            self.hud.render(audio_state, self.time)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _try_set(program: moderngl.Program, name: str, value) -> None:
        """Set a uniform on *program* if it exists, otherwise silently skip."""
        if name in program:
            program[name].value = value
