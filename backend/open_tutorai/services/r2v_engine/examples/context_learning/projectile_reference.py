# Example from projectile_reference.py
# This is a GOLDEN standard for projectile motion animations.
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService
import math

class ProjectileMotion(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService(lang="en"))
        
        # 1. SETUP AXES (Left side)
        axes = Axes(
            x_range=[0, 260, 50],
            y_range=[0, 60, 10],
            axis_config={"color": GREY},
        ).scale(0.7).to_edge(LEFT, buff=0.5)
        
        labels = axes.get_axis_labels(x_label="x", y_label="y")
        
        with self.voiceover(text="Let's visualize the projectile motion on a coordinate system.") as tr:
            self.play(Create(axes), Write(labels), run_time=tr.duration)

        # 2. VECTORS (Initial Velocity)
        v0 = 50
        angle = 37 * DEGREES
        
        start_point = axes.c2p(0, 0)
        v0_vector = Arrow(start_point, axes.c2p(v0 * math.cos(angle), v0 * math.sin(angle)), color=BLUE, buff=0)
        
        with self.voiceover(text="A projectile is launched with an initial velocity of 50 meters per second at an angle of 37 degrees.") as tr:
            self.play(GrowArrow(v0_vector), run_time=tr.duration)

        # 3. VECTOR COMPONENTS
        v0x_vector = Arrow(start_point, axes.c2p(v0 * math.cos(angle), 0), color=GREEN, buff=0)
        v0y_vector = Arrow(axes.c2p(v0 * math.cos(angle), 0), axes.c2p(v0 * math.cos(angle), v0 * math.sin(angle)), color=RED, buff=0)
        
        # Text on the right
        calc_text = MathTex(
            "v_{0x} = 50 \\cos(37^\\circ) = 40 \\text{ m/s}\\\\",
            "v_{0y} = 50 \\sin(37^\\circ) = 30 \\text{ m/s}"
        ).scale(0.7).to_edge(RIGHT, buff=0.5).shift(UP*1)

        with self.voiceover(text="We can break this velocity into its horizontal and vertical components.") as tr:
            self.play(TransformFromCopy(v0_vector, v0x_vector), TransformFromCopy(v0_vector, v0y_vector))
            self.play(Write(calc_text), run_time=tr.duration - 1)

        # 4. ANIMATING THE TRAJECTORY (The 3Blue1Brown way)
        t_tracker = ValueTracker(0)
        
        def get_projectile_pos():
            t = t_tracker.get_value()
            x = v0 * math.cos(angle) * t
            y = v0 * math.sin(angle) * t - 0.5 * 10 * t**2
            return axes.c2p(x, y)

        projectile = always_redraw(lambda: Dot(get_projectile_pos(), color=YELLOW))
        path = TracedPath(projectile.get_center, stroke_color=YELLOW, stroke_width=4)

        with self.voiceover(text="As time passes, gravity acts on the vertical velocity, creating a parabolic trajectory.") as tr:
            self.add(path, projectile)
            self.play(t_tracker.animate.set_value(6), run_time=tr.duration, rate_func=linear)

        # 5. RESULTS
        max_height_text = Text("Max Height = 45 m", font_size=24, color=YELLOW).next_to(calc_text, DOWN, buff=1)
        range_text = Text("Range = 240 m", font_size=24, color=GREEN).next_to(max_height_text, DOWN, buff=0.5)

        with self.voiceover(text="The maximum height reached is 45 meters, and the total horizontal range is 240 meters.") as tr:
            self.play(Write(max_height_text), Write(range_text), run_time=tr.duration)

        self.wait(2)
        self.play(FadeOut(*self.mobjects))