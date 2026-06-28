"""Manim cheatsheet and documentation for code generation assistance."""

MANIM_CHEATSHEET = """
=== MANIM CORE DOCUMENTATION REFERENCE ===

IMPORTANT ANIMATION CLASSES:
- Write, Create, FadeIn, FadeOut: Basic creation/removal animations
- Transform, ReplacementTransform: Morphing between objects
- MoveToTarget, ApplyMethod: Object transformations
- Indicate, Circumscribe, Flash: Highlighting/emphasis
- Rotate, ScaleInPlace: Geometric transformations
- ShowPassingFlash, ShowCreationThenFadeOut: Transient effects

CORE MOBJECT CLASSES:
- VMobject: Base class for vector graphics (most 2D shapes)
- Text, Tex, MathTex: Text and mathematical notation
- Line, Arrow, Vector, DoubleArrow: Linear objects
- Circle, Arc, Dot, Annulus: Circular objects  
- Square, Rectangle, Polygon, Triangle: Polygonal shapes
- VGroup: Container for grouping multiple mobjects
- NumberLine, Axes, NumberPlane: Coordinate systems

POSITIONING METHODS:
- .next_to(mobject, direction, buff=0.25): Position relative to another object
- .to_edge(direction, buff=0.5): Move to screen edge
- .to_corner(corner): Move to screen corner
- .shift(vector): Move by offset vector
- .move_to(point_or_mobject): Center on point/mobject
- .align_to(mobject, direction): Align edge with another object
- .arrange(direction, buff=0.25): Arrange group members

COMMON CONSTANTS:
- Directions: UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR
- Origin: ORIGIN = np.array([0, 0, 0])
- Colors: RED, BLUE, GREEN, YELLOW, ORANGE, PURPLE, WHITE, GRAY, etc.

PHYSICS-SPECIFIC TIPS:
- Use Arrow() or Vector() for force vectors
- Use Dot() for point masses or particles
- Use Line() or DashedLine() for trajectories
- Use Arc() for circular motion paths
- Use NumberPlane() or Axes() for graphs
- Use MathTex() for equations (better rendering than Tex())
- Use VGroup() to group related physics elements together

MANIM-PHYSICS PLUGIN (for physics problems):
Available for physics visualizations:
- Vector fields, pendulums, projectile motion
- Import: from manim_physics import *

COMMON PATTERNS FOR PHYSICS:
```python
# Force vector
force_vector = Arrow(start=ORIGIN, end=2*RIGHT, color=RED, buff=0)
force_label = MathTex("F").next_to(force_vector, UP)

# Motion diagram  
object_dot = Dot(color=BLUE)
path = Line(start=LEFT*3, end=RIGHT*3, color=GRAY)
self.play(MoveAlongPath(object_dot, path))

# Equation display
equation = MathTex(r"F = ma")
equation.to_edge(UP)
self.play(Write(equation))

# Graph with axes
axes = Axes(
    x_range=[0, 10, 1],
    y_range=[0, 100, 10],
    x_length=6,
    y_length=4
)
graph = axes.plot(lambda x: x**2, color=YELLOW)
self.play(Create(axes), Create(graph))
```

KEY INHERITANCE RELATIONSHIPS:
```
Mobject (base)
  ├── VMobject (vector graphics)
  │     ├── Text, MathTex, Tex
  │     ├── Line, Arrow, Vector
  │     ├── Arc, Circle, Dot
  │     ├── Polygon, Rectangle, Square, Triangle
  │     ├── VGroup (container)
  │     └── NumberLine, Axes, NumberPlane
  ├── PMobject (point-based)
  └── Group (general container)

Animation (base)
  ├── Write, Create, Uncreate
  ├── FadeIn, FadeOut, FadeTransform
  ├── Transform, ReplacementTransform
  ├── MoveAlongPath, Rotate
  ├── Indicate, Circumscribe, Flash
  └── AnimationGroup, Succession
```

VOICEOVER INTEGRATION:
```python
from manim_voiceover import VoiceoverScene

class MyScene(VoiceoverScene):
    def construct(self):
        self.set_speech_service(KokoroService(voice="af_bella", speed=1.0))
        
        with self.voiceover(text="Hello, let's learn physics!") as tracker:
            title = Text("Physics Demo")
            self.play(Write(title), run_time=tracker.duration)
```

COMMON PITFALLS TO AVOID:
1. Don't use ImageMobject or external files (use built-in shapes)
2. Always import necessary classes (don't assume they're available)
3. Use MathTex for equations, not Text
4. Initialize VoiceoverScene with set_speech_service()
5. Use proper buff parameters in next_to() to avoid overlaps
6. Remember to import sys/os for path setup when using custom utils
"""

PHYSICS_PLUGIN_INFO = """
=== MANIM-PHYSICS PLUGIN ===

The manim-physics plugin provides specialized tools for physics visualizations.

Installation: pip install manim-physics
Import: from manim_physics import *

KEY FEATURES:
- Rigid body mechanics (masses, springs, pendulums)
- Electric fields and magnetic fields
- Optical elements (lenses, mirrors)
- Wave mechanics
- Particle systems

EXAMPLE USAGE:
```python
from manim import *
from manim_physics import *

class PhysicsDemo(VoiceoverScene):
    def construct(self):
        # Pendulum
        pendulum = Pendulum()
        self.play(Create(pendulum))
        
        # Electric field  
        charge = Charge(-1, LEFT)
        field = ElectricField(charge)
        self.add(charge, field)
```

WHEN TO USE:
- Complex physics simulations (pendulums, springs)
- Field visualizations (electric, magnetic)
- When basic Manim shapes aren't sufficient

WHEN NOT TO USE:
- Simple vector arrows (use Arrow instead)
- Basic motion (use MoveAlongPath instead)
- Static diagrams (use basic shapes instead)
"""

def get_manim_cheatsheet() -> str:
    """Get the Manim cheatsheet for code generation."""
    return MANIM_CHEATSHEET

def get_physics_plugin_info() -> str:
    """Get physics plugin information."""
    return PHYSICS_PLUGIN_INFO