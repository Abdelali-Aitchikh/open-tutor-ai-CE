# Example: Force Vectors and Free Body Diagrams
# Shows best practices for creating force vectors on objects

from manim import *

class ForceVectorExample(Scene):
    def construct(self):
        # Create object
        box = Square(side_length=1, color=BLUE, fill_opacity=0.5)
        box_label = Text("m", font_size=36).move_to(box.get_center())
        object_group = VGroup(box, box_label)
        
        self.play(Create(box), Write(box_label))
        self.wait()
        
        # Force vectors originating from center
        forces = VGroup()
        
        # Normal force (upward)
        normal_force = Arrow(
            start=box.get_center(),
            end=box.get_center() + UP * 2,
            buff=0,
            color=GREEN,
            stroke_width=6
        )
        normal_label = MathTex("F_N", color=GREEN).next_to(normal_force, RIGHT)
        
        # Weight (downward)
        weight = Arrow(
            start=box.get_center(),
            end=box.get_center() + DOWN * 2,
            buff=0,
            color=RED,
            stroke_width=6
        )
        weight_label = MathTex("F_g = mg", color=RED).next_to(weight, RIGHT)
        
        # Applied force (horizontal)
        applied_force = Arrow(
            start=box.get_center(),
            end=box.get_center() + RIGHT * 2.5,
            buff=0,
            color=YELLOW,
            stroke_width=6
        )
        applied_label = MathTex("F_a", color=YELLOW).next_to(applied_force, UP)
        
        # Friction force (opposite to motion)
        friction = Arrow(
            start=box.get_center(),
            end=box.get_center() + LEFT * 1.5,
            buff=0,
            color=ORANGE,
            stroke_width=6
        )
        friction_label = MathTex("F_f", color=ORANGE).next_to(friction, UP)
        
        # Animate forces one by one
        self.play(Create(normal_force), Write(normal_label))
        self.wait(0.5)
        self.play(Create(weight), Write(weight_label))
        self.wait(0.5)
        self.play(Create(applied_force), Write(applied_label))
        self.wait(0.5)
        self.play(Create(friction), Write(friction_label))
        self.wait()
        
        # Show net force
        net_force = Arrow(
            start=box.get_center(),
            end=box.get_center() + RIGHT * 1,
            buff=0,
            color=PURPLE,
            stroke_width=8
        )
        net_label = MathTex("F_{net}", color=PURPLE).next_to(net_force, DOWN)
        
        self.play(
            Create(net_force),
            Write(net_label),
            applied_force.animate.set_opacity(0.3),
            friction.animate.set_opacity(0.3)
        )
        self.wait(2)