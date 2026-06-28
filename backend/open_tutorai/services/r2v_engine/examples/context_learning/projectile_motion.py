# Example: Projectile Motion with Forces
# This example demonstrates how to visualize projectile motion with force vectors

from manim import *
import numpy as np

class ProjectileMotion(Scene):
    def construct(self):
        # Title
        title = Text("Projectile Motion", font_size=48)
        self.play(Write(title))
        self.wait()
        self.play(FadeOut(title))
        
        # Create coordinate system
        axes = Axes(
            x_range=[0, 10, 1],
            y_range=[0, 6, 1],
            x_length=10,
            y_length=6,
            axis_config={"include_tip": True, "include_numbers": True}
        )
        axes_labels = axes.get_axis_labels(x_label="x (m)", y_label="y (m)")
        
        self.play(Create(axes), Write(axes_labels))
        
        # Create projectile (ball)
        ball = Dot(color=BLUE, radius=0.15).move_to(axes.c2p(0, 0))
        
        # Initial velocity vector
        initial_velocity = Arrow(
            start=ball.get_center(),
            end=ball.get_center() + np.array([2, 1.5, 0]),
            buff=0,
            color=GREEN
        )
        velocity_label = Text("v₀", font_size=24, color=GREEN).next_to(initial_velocity, UP)
        
        self.play(
            Create(ball),
            Create(initial_velocity),
            Write(velocity_label)
        )
        self.wait()
        
        # Gravity force vector
        gravity_force = Arrow(
            start=ball.get_center(),
            end=ball.get_center() + DOWN * 1.5,
            buff=0,
            color=RED
        )
        gravity_label = Text("F_g", font_size=24, color=RED).next_to(gravity_force, RIGHT)
        
        self.play(Create(gravity_force), Write(gravity_label))
        self.wait()
        
        # Trajectory path
        def projectile_path(t):
            x = 3 * t
            y = 4 * t - 4.9 * t**2
            return axes.c2p(x, max(0, y))
        
        trajectory = ParametricFunction(
            lambda t: projectile_path(t),
            t_range=[0, 0.82],
            color=YELLOW,
            stroke_width=2
        )
        
        # Animate the motion
        self.play(
            FadeOut(initial_velocity),
            FadeOut(velocity_label),
            MoveAlongPath(ball, trajectory, rate_func=linear),
            gravity_force.animate.move_to(ball),
            gravity_label.animate.next_to(ball, RIGHT),
            Create(trajectory),
            run_time=3
        )
        
        self.wait(2)