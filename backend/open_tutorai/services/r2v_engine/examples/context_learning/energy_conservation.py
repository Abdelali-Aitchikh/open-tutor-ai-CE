# Example: Energy Conservation - Pendulum
# Shows kinetic and potential energy transformation

from manim import *
import numpy as np

class EnergyConservation(Scene):
    def construct(self):
        # Title
        title = Text("Conservation of Energy", font_size=42)
        self.play(Write(title))
        self.wait()
        self.play(title.animate.to_edge(UP))
        
        # Pendulum pivot point
        pivot = Dot(point=UP * 3, color=WHITE)
        
        # Pendulum bob
        bob = Dot(radius=0.2, color=BLUE)
        bob.move_to(pivot.get_center() + DOWN * 3)
        
        # String
        string = Line(pivot.get_center(), bob.get_center(), color=WHITE)
        
        self.play(Create(pivot), Create(bob), Create(string))
        self.wait()
        
        # Energy bars
        ke_bar = Rectangle(height=0, width=0.8, color=RED, fill_opacity=0.7)
        ke_bar.to_edge(LEFT).shift(DOWN * 2)
        ke_label = Text("KE", font_size=24, color=RED).next_to(ke_bar, DOWN)
        
        pe_bar = Rectangle(height=3, width=0.8, color=GREEN, fill_opacity=0.7)
        pe_bar.next_to(ke_bar, RIGHT, buff=1).align_to(ke_bar, DOWN)
        pe_label = Text("PE", font_size=24, color=GREEN).next_to(pe_bar, DOWN)
        
        total_label = Text("Total Energy = Constant", font_size=28)
        total_label.to_edge(DOWN)
        
        self.play(
            Create(ke_bar),
            Create(pe_bar),
            Write(ke_label),
            Write(pe_label),
            Write(total_label)
        )
        self.wait()
        
        # Animate pendulum swing
        def update_string(mob):
            new_string = Line(pivot.get_center(), bob.get_center(), color=WHITE)
            mob.become(new_string)
        
        def update_energy_bars(mob):
            # Calculate height
            height = bob.get_center()[1] - (pivot.get_center()[1] - 3)
            # PE proportional to height (normalized to 0-3)
            pe_height = (height + 1.5) / 1.5 * 1.5
            # KE is complement (total = 3)
            ke_height = 3 - pe_height
            
            # Update bar heights
            new_ke_bar = Rectangle(
                height=max(0, ke_height),
                width=0.8,
                color=RED,
                fill_opacity=0.7
            )
            new_ke_bar.align_to(ke_bar, DOWN).align_to(ke_bar, LEFT)
            ke_bar.become(new_ke_bar)
            
            new_pe_bar = Rectangle(
                height=max(0, pe_height),
                width=0.8,
                color=GREEN,
                fill_opacity=0.7
            )
            new_pe_bar.align_to(pe_bar, DOWN).align_to(pe_bar, LEFT)
            pe_bar.become(new_pe_bar)
        
        string.add_updater(update_string)
        
        # Swing pendulum
        angle = PI / 3
        self.play(
            Rotate(
                bob,
                angle=-angle,
                about_point=pivot.get_center()
            ),
            run_time=1
        )
        
        # Oscillation
        for _ in range(2):
            self.play(
                Rotate(
                    bob,
                    angle=2 * angle,
                    about_point=pivot.get_center()
                ),
                run_time=2,
                rate_func=there_and_back
            )
        
        self.wait(2)