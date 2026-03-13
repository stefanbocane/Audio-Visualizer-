"""Multi-pass bloom post-processing: extract, two-pass Gaussian blur x2.

The bloom is run at half resolution for performance.  Two iterations of the
horizontal+vertical blur produce a wider, dreamier glow that enhances the
aurora colour palette without washing the image toward white.
"""

import moderngl

from renderer.context import RenderContext


class BloomProcessor:
    """Applies a screen-space bloom effect via extract + iterated Gaussian blur.

    Workflow
    --------
    1. **Extract** -- pixels above a luminance threshold are written to
       ``fbo_bloom_extract`` (half resolution).  The threshold is set low
       (0.55) so that more of the colourful scene receives a subtle glow.
    2. **Blur iteration 1** -- horizontal blur into ``fbo_blur_a``, then
       vertical blur into ``fbo_blur_b``.
    3. **Blur iteration 2** -- repeat horizontal+vertical using the output
       of iteration 1 for an even softer spread.

    The final bloom texture (``tex_blur_b``) is returned for compositing.
    """

    # Extraction luminance threshold -- lower = more of the scene glows.
    THRESHOLD = 0.55

    # Number of horizontal+vertical blur iterations.
    BLUR_ITERATIONS = 2

    def __init__(self, ctx: RenderContext) -> None:
        self.ctx = ctx

        # Compile shader programs.
        self.extract_program = ctx.create_program(
            "fullscreen_quad.vert", "bloom_extract.frag"
        )
        self.blur_program = ctx.create_program(
            "fullscreen_quad.vert", "bloom_blur.frag"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, scene_texture: moderngl.Texture) -> moderngl.Texture:
        """Run the full bloom pipeline and return the blurred bloom texture.

        Parameters
        ----------
        scene_texture : moderngl.Texture
            The colour attachment of the main scene FBO (``tex_scene``).

        Returns
        -------
        moderngl.Texture
            The final bloom result (``tex_blur_b``), ready for additive
            compositing onto the final image.
        """
        half_w = max(self.ctx.width // 2, 1)
        half_h = max(self.ctx.height // 2, 1)

        # --- Pass 1: extract bright pixels --------------------------------
        self.ctx.fbo_bloom_extract.use()
        self.ctx.ctx.viewport = (0, 0, half_w, half_h)
        self.ctx.fbo_bloom_extract.clear(0.0, 0.0, 0.0, 0.0)

        scene_texture.use(location=0)
        self._try_set_uniform(self.extract_program, "u_scene", 0)
        self._try_set_uniform(self.extract_program, "u_threshold", self.THRESHOLD)

        self.ctx.set_no_blending()
        self.ctx.render_fullscreen_quad(self.extract_program)

        # --- Iterated Gaussian blur (ping-pong between blur_a / blur_b) ---
        # First iteration reads from the extract texture; subsequent
        # iterations read from the previous output (blur_b).
        source_tex = self.ctx.tex_bloom_extract

        for _iteration in range(self.BLUR_ITERATIONS):
            # Horizontal blur: source -> blur_a
            self.ctx.fbo_blur_a.use()
            self.ctx.ctx.viewport = (0, 0, half_w, half_h)
            self.ctx.fbo_blur_a.clear(0.0, 0.0, 0.0, 0.0)

            source_tex.use(location=0)
            self._try_set_uniform(self.blur_program, "u_texture", 0)
            self._try_set_uniform(
                self.blur_program, "u_direction", (1.0 / half_w, 0.0)
            )
            self.ctx.render_fullscreen_quad(self.blur_program)

            # Vertical blur: blur_a -> blur_b
            self.ctx.fbo_blur_b.use()
            self.ctx.ctx.viewport = (0, 0, half_w, half_h)
            self.ctx.fbo_blur_b.clear(0.0, 0.0, 0.0, 0.0)

            self.ctx.tex_blur_a.use(location=0)
            self._try_set_uniform(self.blur_program, "u_texture", 0)
            self._try_set_uniform(
                self.blur_program, "u_direction", (0.0, 1.0 / half_h)
            )
            self.ctx.render_fullscreen_quad(self.blur_program)

            # Next iteration reads from this iteration's output.
            source_tex = self.ctx.tex_blur_b

        return self.ctx.tex_blur_b

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _try_set_uniform(
        program: moderngl.Program, name: str, value
    ) -> None:
        """Set a uniform if it exists in the program (avoids KeyError)."""
        if name in program:
            program[name].value = value
