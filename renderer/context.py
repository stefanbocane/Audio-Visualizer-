"""ModernGL context setup, FBO management, and rendering helpers."""

import os
import struct

import moderngl
import numpy as np


# Path to the shaders directory (sibling of the renderer package).
_SHADER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shaders")


class RenderContext:
    """Wraps a ModernGL context created from an existing pygame OpenGL surface.

    Manages:
    * A fullscreen-quad VAO used by post-processing passes.
    * All offscreen FBOs (scene, bloom, blur, motion-blur feedback).
    * Convenience helpers for shader loading, blending modes, and rendering.
    """

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

        # Create context from the current pygame/OpenGL window.
        self.ctx = moderngl.create_context()
        self.ctx.enable(moderngl.BLEND)

        # Build the shared fullscreen-quad geometry.
        self._quad_vbo, self._quad_ibo, self._quad_vao_content = self._create_quad_buffers()

        # Allocate all offscreen framebuffers.
        self._create_fbos()

    # ------------------------------------------------------------------
    # FBO creation
    # ------------------------------------------------------------------

    def _create_fbos(self) -> None:
        """Create (or recreate) every offscreen FBO at current resolution."""
        w, h = self.width, self.height
        hw, hh = max(w // 2, 1), max(h // 2, 1)

        # -- Full-resolution scene FBO (RGBA16F + depth) ----------------
        self.tex_scene = self.ctx.texture((w, h), 4, dtype="f2")
        self.tex_scene.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.depth_scene = self.ctx.depth_renderbuffer((w, h))
        self.fbo_scene = self.ctx.framebuffer(
            color_attachments=[self.tex_scene],
            depth_attachment=self.depth_scene,
        )

        # -- Half-resolution bloom / blur FBOs (RGBA16F, no depth) ------
        self.tex_bloom_extract = self.ctx.texture((hw, hh), 4, dtype="f2")
        self.tex_bloom_extract.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.fbo_bloom_extract = self.ctx.framebuffer(
            color_attachments=[self.tex_bloom_extract],
        )

        self.tex_blur_a = self.ctx.texture((hw, hh), 4, dtype="f2")
        self.tex_blur_a.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.fbo_blur_a = self.ctx.framebuffer(
            color_attachments=[self.tex_blur_a],
        )

        self.tex_blur_b = self.ctx.texture((hw, hh), 4, dtype="f2")
        self.tex_blur_b.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.fbo_blur_b = self.ctx.framebuffer(
            color_attachments=[self.tex_blur_b],
        )

        # -- Previous-frame FBO for motion blur feedback (RGBA8) --------
        self.tex_previous = self.ctx.texture((w, h), 4)
        self.tex_previous.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.fbo_previous = self.ctx.framebuffer(
            color_attachments=[self.tex_previous],
        )

    # ------------------------------------------------------------------
    # Fullscreen quad
    # ------------------------------------------------------------------

    def _create_quad_buffers(self):
        """Build a fullscreen quad covering NDC [-1, 1] with UV [0, 1].

        Vertex layout: vec2 position, vec2 texcoord (4 floats per vertex).
        Index buffer draws two triangles via 6 indices.

        Returns the VBO, IBO, and a content list suitable for passing to
        ``ctx.vertex_array`` together with any shader program.
        """
        #                 x     y    u    v
        vertices = [
            -1.0, -1.0, 0.0, 0.0,   # bottom-left
             1.0, -1.0, 1.0, 0.0,   # bottom-right
            -1.0,  1.0, 0.0, 1.0,   # top-left
             1.0,  1.0, 1.0, 1.0,   # top-right
        ]
        indices = [0, 1, 2, 2, 1, 3]

        vbo = self.ctx.buffer(struct.pack(f"{len(vertices)}f", *vertices))
        ibo = self.ctx.buffer(struct.pack(f"{len(indices)}I", *indices))

        # Content descriptor for ctx.vertex_array — will be paired with a
        # program later in ``_build_quad_vao``.
        content = (vbo, "2f 2f", "in_position", "in_texcoord")

        return vbo, ibo, content

    def _build_quad_vao(self, program: moderngl.Program) -> moderngl.VertexArray:
        """Create a VAO that binds the shared quad buffers to *program*."""
        return self.ctx.vertex_array(
            program,
            [self._quad_vao_content],
            index_buffer=self._quad_ibo,
            index_element_size=4,
        )

    # ------------------------------------------------------------------
    # Shader loading
    # ------------------------------------------------------------------

    def load_shader(self, name: str) -> str:
        """Read a shader source file from the ``shaders/`` directory.

        Parameters
        ----------
        name : str
            Filename (e.g. ``"fullscreen_quad.vert"``).

        Returns
        -------
        str
            The shader source code.

        Raises
        ------
        FileNotFoundError
            If the shader file does not exist.
        """
        path = os.path.join(_SHADER_DIR, name)
        with open(path, "r") as fh:
            return fh.read()

    def create_program(self, vert_name: str, frag_name: str) -> moderngl.Program:
        """Load vertex and fragment shaders by filename and compile a program.

        Parameters
        ----------
        vert_name : str
            Vertex shader filename inside ``shaders/``.
        frag_name : str
            Fragment shader filename inside ``shaders/``.

        Returns
        -------
        moderngl.Program
        """
        vert_src = self.load_shader(vert_name)
        frag_src = self.load_shader(frag_name)
        return self.ctx.program(vertex_shader=vert_src, fragment_shader=frag_src)

    def create_program_from_source(
        self, vert_src: str, frag_src: str
    ) -> moderngl.Program:
        """Compile a shader program from source strings.

        Parameters
        ----------
        vert_src : str
            Vertex shader GLSL source.
        frag_src : str
            Fragment shader GLSL source.

        Returns
        -------
        moderngl.Program
        """
        return self.ctx.program(vertex_shader=vert_src, fragment_shader=frag_src)

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def render_fullscreen_quad(self, program: moderngl.Program) -> None:
        """Render a fullscreen quad with the given shader *program*.

        A per-program VAO is created on first use and cached on the program
        object to avoid repeated allocation.
        """
        # Cache the VAO on the program object itself to avoid rebuilding it
        # every frame.
        cache_attr = "_rctx_quad_vao"
        vao = getattr(program, cache_attr, None)
        if vao is None:
            vao = self._build_quad_vao(program)
            setattr(program, cache_attr, vao)
        vao.render(moderngl.TRIANGLES)

    # ------------------------------------------------------------------
    # Blending modes
    # ------------------------------------------------------------------

    @staticmethod
    def set_uniform(program: moderngl.Program, name: str, value) -> None:
        """Set a uniform if it exists in the compiled program, otherwise skip."""
        if name in program:
            program[name].value = value

    def set_additive_blending(self) -> None:
        """Enable additive blending (GL_ONE, GL_ONE)."""
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.ONE, moderngl.ONE)

    def set_alpha_blending(self) -> None:
        """Enable standard alpha blending (GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)."""
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (
            moderngl.SRC_ALPHA,
            moderngl.ONE_MINUS_SRC_ALPHA,
        )

    def set_no_blending(self) -> None:
        """Disable blending entirely."""
        self.ctx.disable(moderngl.BLEND)

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resize(self, width: int, height: int) -> None:
        """Recreate all FBOs at a new resolution.

        Parameters
        ----------
        width : int
            New framebuffer width in pixels.
        height : int
            New framebuffer height in pixels.
        """
        if width == self.width and height == self.height:
            return

        self.width = width
        self.height = height

        # Release existing GPU resources before reallocating.
        self._release_fbos()
        self._create_fbos()

    def _release_fbos(self) -> None:
        """Release all FBO-related GPU resources."""
        for attr in (
            "fbo_scene",
            "fbo_bloom_extract",
            "fbo_blur_a",
            "fbo_blur_b",
            "fbo_previous",
            "tex_scene",
            "tex_bloom_extract",
            "tex_blur_a",
            "tex_blur_b",
            "tex_previous",
            "depth_scene",
        ):
            obj = getattr(self, attr, None)
            if obj is not None:
                obj.release()
