# Example: Basic Circuit with Current Flow
# Demonstrates how to create circuit diagrams and show current flow

from manim import *

class CircuitBasics(Scene):
    def construct(self):
        # Title
        title = Text("Ohm's Law Circuit", font_size=42)
        self.play(Write(title))
        self.wait()
        self.play(title.animate.to_edge(UP))
        
        # Battery
        battery = Rectangle(height=1.5, width=0.3, color=WHITE)
        battery.shift(LEFT * 4)
        plus_sign = Text("+", font_size=24, color=RED).next_to(battery, UP, buff=0.1)
        minus_sign = Text("-", font_size=24, color=BLUE).next_to(battery, DOWN, buff=0.1)
        voltage_label = MathTex("V = 12V", font_size=32).next_to(battery, LEFT)
        
        # Resistor (zigzag)
        resistor = VGroup()
        resistor_path = VMobject()
        points = [
            RIGHT * 4,
            RIGHT * 4 + UP * 0.3,
            RIGHT * 4.3 + DOWN * 0.3,
            RIGHT * 4.6 + UP * 0.3,
            RIGHT * 4.9 + DOWN * 0.3,
            RIGHT * 5.2
        ]
        resistor_path.set_points_as_corners(points)
        resistor.add(resistor_path)
        resistor_label = MathTex("R = 4\\Omega", font_size=32).next_to(resistor, UP)
        
        # Wires
        top_wire = Line(battery.get_top(), battery.get_top() + RIGHT * 8, color=WHITE)
        bottom_wire = Line(battery.get_bottom(), battery.get_bottom() + RIGHT * 8, color=WHITE)
        right_wire = Line(
            battery.get_top() + RIGHT * 8,
            battery.get_bottom() + RIGHT * 8,
            color=WHITE
        )
        
        # Animate circuit construction
        self.play(
            Create(battery),
            Write(plus_sign),
            Write(minus_sign),
            Write(voltage_label)
        )
        self.wait()
        
        self.play(Create(top_wire), Create(bottom_wire), Create(right_wire))
        self.wait()
        
        # Add resistor on top wire
        resistor.move_to(top_wire.get_center())
        self.play(Create(resistor), Write(resistor_label))
        self.wait()
        
        # Current flow arrows
        current_arrows = VGroup()
        for i in range(3):
            arrow = Arrow(
                start=ORIGIN,
                end=RIGHT * 0.5,
                color=YELLOW,
                stroke_width=4,
                max_tip_length_to_length_ratio=0.3
            )
            arrow.move_to(top_wire.point_from_proportion(0.2 + i * 0.2))
            current_arrows.add(arrow)
        
        current_label = MathTex("I = \\frac{V}{R} = 3A", font_size=32, color=YELLOW)
        current_label.to_edge(DOWN)
        
        # Animate current flow
        self.play(
            *[GrowArrow(arrow) for arrow in current_arrows],
            Write(current_label)
        )
        self.wait()
        
        # Animate current moving
        self.play(
            *[arrow.animate.shift(RIGHT * 0.3) for arrow in current_arrows],
            rate_func=linear,
            run_time=2
        )
        
        self.wait(2)