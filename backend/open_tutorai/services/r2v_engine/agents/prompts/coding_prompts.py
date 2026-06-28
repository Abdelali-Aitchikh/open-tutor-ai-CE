"""Prompt templates for coding agent."""

PHYSICS_CODING_PROMPT_TEMPLATE = """
You are an expert Manim (Community Edition) developer specializing in physics visualizations. Generate executable Manim code implementing animations as specified in the scene plan below. The code should create a video that explains the physics solution in a clear, visually appealing way.

=== MANIM REFERENCE GUIDE ===
Use the following Manim classes and patterns for physics visualizations:

CORE ANIMATION CLASSES:
- Write, Create, FadeIn, FadeOut: Basic animations
- Transform, ReplacementTransform: Morphing objects
- Indicate, Circumscribe: Highlighting
- MoveAlongPath, Rotate: Motion and transformations

ESSENTIAL MOBJECTS:
- Text, MathTex: Text and equations (use MathTex for formulas!)
- Arrow, Vector, Line: Vectors and paths
- Circle, Dot, Rectangle, Polygon: Shapes
- Axes, NumberPlane: Coordinate systems
- VGroup: Group related objects

POSITIONING:
- .next_to(obj, direction, buff=0.25)
- .to_edge(direction), .to_corner()
- .shift(), .move_to(), .align_to()
- .arrange(direction, buff=0.25)

PHYSICS PATTERNS:
```python
# Force vector
force = Arrow(ORIGIN, 2*RIGHT, color=RED, buff=0)
label = MathTex("F").next_to(force, UP)

# Motion path
path = Line(LEFT*3, RIGHT*3)
obj = Dot().move_to(path.get_start())
self.play(MoveAlongPath(obj, path))
```

MANIM-PHYSICS PLUGIN (optional):
- Available for advanced physics (pendulums, fields)
- Import: from manim_physics import *
- Use only if needed for complex simulations

PROBLEM INFORMATION:
Question: {question}
Solution: {solution}

SCENE PLAN:
{scene_plan}

SPECIFIC REQUIREMENTS AND RESTRICTIONS:
1. Use Manim Community Edition syntax.
2. Create a single Python file with all necessary classes and imports.
3. CRITICAL - VOICEOVER SETUP (MUST BE EXACT):
   ```python
   from manim import *
   from manim_voiceover import VoiceoverScene
   import sys
   import os
   # CRITICAL: Add project root to Python path (4 levels up from code directory)
   current_dir = os.path.dirname(os.path.abspath(__file__))
   project_root = os.path.abspath(os.path.join(current_dir, '../../../..'))
   if project_root not in sys.path:
       sys.path.insert(0, project_root)
   from utils.kokoro_voiceover import KokoroService
   ```
4. Each scene should be a separate class inheriting from VoiceoverScene.
5. In EVERY scene's construct() method, FIRST LINE must initialize speech service:
   self.set_speech_service(KokoroService(voice="af_bella", speed=1.0, lang="en-us"))
6. Use self.voiceover(text="...") context manager for narration synchronized with animations.
7. IMPORTANT NARRATION STYLE:
   - First scene should start with a teacher-like introduction: "Today, we will learn about [topic]..." or "Hello! Today we're going to understand..."
   - Last scene should end with a teacher-like conclusion: "I hope you understand the solution now." or "That's how we solve this problem. I hope this was clear!"
   - Use warm, encouraging teaching language throughout
8. Include detailed comments explaining the code.
9. Use MathTex for all mathematical equations and formulas for better rendering.
10. DO NOT use ImageMobject or load any external images.
11. Use ONLY geometric shapes, lines, Text, MathTex, and other built-in Manim objects.
12. Ensure all animation code is complete and doesn't cut off mid-statement.
13. Create visually engaging animations for physics concepts (e.g., moving objects, vectors for forces, graphs for motion).

EXAMPLE MANIM CODE FORMAT:
```python
from manim import *
from manim_voiceover import VoiceoverScene
import sys
import os
# CRITICAL: Add project root to Python path to find utils module (4 levels up)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from utils.kokoro_voiceover import KokoroService

class IntroScene(VoiceoverScene):
    def construct(self):
        # Initialize speech service with Kokoro TTS - MUST BE FIRST
        self.set_speech_service(KokoroService(voice="af_bella", speed=1.0, lang="en-us"))
        
        # Title
        title = Text("Newton's Second Law")
        
        with self.voiceover(text="Hello! Today we will learn about kinematics and how to solve motion problems.") as tracker:
            self.play(Write(title), run_time=tracker.duration * 0.8)
            self.wait(tracker.duration * 0.2)
        
        self.play(title.animate.to_edge(UP))

        # Problem Text
        question_text = Text("A car accelerates uniformly from rest...", font_size=24)
        
        with self.voiceover(text="A car starts from rest and accelerates uniformly.") as tracker:
            self.play(Write(question_text), run_time=tracker.duration)

        # Diagram
        car = Square(side_length=0.5, color=BLUE)
        
        with self.voiceover(text="We can visualize this motion.") as tracker:
            self.play(Create(car))
            self.play(car.animate.shift(RIGHT*3), run_time=tracker.duration * 0.8)

class Scene2_Calculations(VoiceoverScene):
    def construct(self):
        # Initialize speech service with Kokoro TTS
        self.set_speech_service(KokoroService(voice="af_bella", speed=1.0, lang="en-us"))
        
        # Equations using MathTex
        equation = MathTex("v = u + at", font_size=36)
        
        with self.voiceover(text="We use the equation v equals u plus a t.") as tracker:
            self.play(Write(equation), run_time=tracker.duration)

if __name__ == "__main__":
    # This will be handled by the system
    pass
```

IMPORTANT:
- Your code must be complete, executable, and error-free.
- Use MathTex for equations.
- FOCUS on creating clear physics visualizations.
- IMPLEMENT all scenes from the scene plan.
"""

PHYSICS_SINGLE_SCENE_CODING_TEMPLATE = """
You are an expert Manim (Community Edition) developer specializing in physics visualizations. Generate executable Manim code for a SINGLE SCENE as specified below.

PROBLEM INFORMATION:
Question: {question}
Solution: {solution}

SCENE INFORMATION:
Scene Number: {scene_number}
Scene Title: {scene_title}
Scene Purpose: {scene_purpose}
Scene Description: {scene_description}
Scene Layout: {scene_layout}
Scene Narration: {scene_narration}

SPECIFIC REQUIREMENTS AND RESTRICTIONS:
1. Use Manim Community Edition syntax.
2. Create ONLY ONE scene class inheriting from VoiceoverScene (import from manim_voiceover).
3. IMPORTANT: Add sys.path setup at the top:
   import sys
   import os
   sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
4. In the construct() method, initialize KokoroService with: self.set_speech_service(KokoroService(voice="af_bella", speed=1.0, lang="en-us"))
5. Use self.voiceover(text="...") context manager for narration synchronized with animations.
6. Include detailed comments.
7. Use MathTex for all mathematical equations.
8. DO NOT use ImageMobject or load any external images.
8. Use ONLY geometric shapes, lines, Text, MathTex, and other built-in Manim objects.
9. NAME THE CLASS using the scene title in CamelCase followed by "_Scene{scene_number}".
10. Create visually engaging animations for physics concepts.

Return only the Python code for the scene.
"""

PHYSICS_FIX_CODE_PROMPT_TEMPLATE = """
You are an expert Manim (Community Edition) developer specializing in debugging physics animations. The following Manim code failed to execute. Analyze the error message and the code, then provide a corrected version.

SCENE PLAN:
{scene_plan}

FAILED CODE:
```python
{code}
```

ERROR MESSAGE:
{error_message}

SPECIFIC REQUIREMENTS FOR FIXING:
1. Identify the cause of the error.
2. Correct the code to resolve the error.
3. Ensure the corrected code still meets the original scene requirements.
4. Use Manim Community Edition syntax.
5. Use MathTex for all mathematical equations.
6. CRITICAL - If ModuleNotFoundError for 'utils', add this EXACT code at the top after imports:
   ```python
   from manim import *
   from manim_voiceover import VoiceoverScene
   import sys
   import os
   # CRITICAL: Add project root to Python path (4 levels up from code directory)
   current_dir = os.path.dirname(os.path.abspath(__file__))
   project_root = os.path.abspath(os.path.join(current_dir, '../../../..'))
   if project_root not in sys.path:
       sys.path.insert(0, project_root)
   from utils.kokoro_voiceover import KokoroService
   ```
7. Ensure EVERY scene class has this as FIRST LINE in construct():
   self.set_speech_service(KokoroService(voice="af_bella", speed=1.0, lang="en-us"))
8. DO NOT create mock/fake KokoroService classes - use the real one from utils.kokoro_voiceover
9. DO NOT remove manim_voiceover imports - VoiceoverScene is required for audio
10. Return only the full, corrected Python code. Do not include explanations outside the code comments.

Corrected Code:
"""

PHYSICS_SCREENSHOT_FEEDBACK_PROMPT_TEMPLATE = """
You are an expert Manim (Community Edition) developer specializing in visual quality and layout optimization for physics animations. The following Manim code has been rendered and screenshots were analyzed. Based on the visual feedback from the screenshot analysis, improve the code to address layout, spacing, overlap, and visibility issues.

SCENE PLAN:
{scene_plan}

CURRENT CODE:
```python
{code}
```

VISUAL FEEDBACK FROM SCREENSHOT ANALYSIS:
{visual_feedback}

SPECIFIC REQUIREMENTS FOR VISUAL IMPROVEMENTS:
1. **Overlap Issues**: If text or objects overlap, adjust positions, font sizes, or use `arrange()` and `next_to()` to create proper spacing.
2. **Spacing and Layout**: Ensure equations, text, and diagrams have clear visual hierarchy and sufficient whitespace.
3. **Font Size**: Increase or decrease font_size for Text and MathTex objects to improve readability.
4. **Positioning**: Use `to_edge()`, `shift()`, `next_to()`, `arrange()`, and alignment constants (UP, DOWN, LEFT, RIGHT) to optimize object placement.
5. **Color and Contrast**: Ensure colors provide good contrast and visibility (e.g., avoid light colors on white backgrounds).
6. **Animation Timing**: Adjust wait times if elements appear too quickly or slowly.
7. **Visual Clarity**: Simplify overly complex scenes by breaking them into smaller parts or removing unnecessary elements.
8. **Scene Relevance**: Ensure all visual elements support the narration and learning objectives.

IMPORTANT GUIDELINES:
- Use Manim Community Edition syntax only.
- Use MathTex for all mathematical equations.
- Ensure KokoroService is initialized: self.set_speech_service(KokoroService(voice="af_bella", speed=1.0, lang="en-us"))
- DO NOT use ImageMobject or load external images.
- Maintain the original scene structure and content while improving layout and spacing.
- Include detailed comments explaining the visual improvements made.
- Return only the full, improved Python code. Do not include explanations outside the code comments.

EXAMPLE IMPROVEMENTS:
- If "Scene1: high overlap detected" → Add `.arrange(DOWN, buff=0.5)` or use `next_to()` with appropriate buffers
- If "text too small" → Increase `font_size=36` to `font_size=48`
- If "equation off-screen" → Use `.to_edge(UP)` or `.shift(UP*0.5)`
- If "elements clustered" → Use `VGroup()` with `.arrange()` to distribute elements evenly

Improved Code:
"""

def get_coding_prompt(question, solution, scene_plan, manim_docs=""):
    """Generate a prompt for the coding agent to create the full Manim script.
    
    Args:
        question: The physics question
        solution: The solution details
        scene_plan: The scene plan
        manim_docs: RAG-retrieved Manim documentation (optional)
    """
    prompt = PHYSICS_CODING_PROMPT_TEMPLATE.format(
        question=question,
        solution=solution,
        scene_plan=scene_plan
    )
    
    # Append RAG-retrieved documentation if available
    if manim_docs:
        prompt += f"\n\n=== RELEVANT MANIM DOCUMENTATION ===\n{manim_docs}\n"
        prompt += "\nUse the above documentation as reference for Manim classes, methods, and best practices.\n"
    
    return prompt

def get_single_scene_coding_prompt(question, solution, scene_info, manim_docs=""):
    """Generate a prompt for the coding agent to create a single Manim scene.
    
    Args:
        question: The physics question
        solution: The solution details
        scene_info: Scene information dictionary
        manim_docs: RAG-retrieved Manim documentation (optional)
    """
    prompt = PHYSICS_SINGLE_SCENE_CODING_TEMPLATE.format(
        question=question,
        solution=solution,
        scene_number=scene_info.get('number', 'N/A'),
        scene_title=scene_info.get('title', 'Untitled'),
        scene_purpose=scene_info.get('purpose', ''),
        scene_description=scene_info.get('description', ''),
        scene_layout=scene_info.get('layout', ''),
        scene_narration=scene_info.get('narration', '')
    )
    
    # Append RAG-retrieved documentation if available
    if manim_docs:
        prompt += f"\n\n=== RELEVANT MANIM DOCUMENTATION ===\n{manim_docs}\n"
        prompt += "\nUse the above documentation as reference for Manim classes, methods, and best practices.\n"
    
    return prompt

def get_fix_code_prompt(scene_plan, code, error_message, manim_docs=""):
    """Generate a prompt for the coding agent to fix a broken Manim script.
    
    Args:
        scene_plan: The scene plan
        code: The broken code
        error_message: The error message
        manim_docs: RAG-retrieved Manim documentation for error fixing (optional)
    """
    prompt = PHYSICS_FIX_CODE_PROMPT_TEMPLATE.format(
        scene_plan=scene_plan,
        code=code,
        error_message=error_message
    )
    
    # Append RAG-retrieved documentation if available
    if manim_docs:
        prompt += f"\n\n{manim_docs}\n"
        prompt += "\nRefer to the above Manim documentation to fix the error correctly.\n"
    
    return prompt

def get_screenshot_feedback_prompt(scene_plan, code, visual_feedback):
    """Generate a prompt for the coding agent to improve code based on screenshot visual feedback."""
    return PHYSICS_SCREENSHOT_FEEDBACK_PROMPT_TEMPLATE.format(
        scene_plan=scene_plan,
        code=code,
        visual_feedback=visual_feedback
    )
