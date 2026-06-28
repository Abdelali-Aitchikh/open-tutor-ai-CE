import logging
import re
import os
import glob
from config import OPENAI_API_KEY, MODEL_NAME
from utils.llm_client import get_llm_client
from utils.manim_rag import get_manim_rag
from agents.prompts.coding_prompts import (
    get_coding_prompt,
    get_fix_code_prompt,
    get_screenshot_feedback_prompt
)
from agents.prompts.manim_cheatsheet import get_manim_cheatsheet

logger = logging.getLogger(__name__)

class CodingAgent:
    def __init__(self, use_rag=True, use_context_learning=True, context_learning_path="examples/context_learning"):
        """Initialize CodingAgent with optional RAG support and context learning."""
        self.client = get_llm_client()
        self.use_rag = use_rag
        self.use_context_learning = use_context_learning
        self.context_learning_path = context_learning_path
        self.rag = get_manim_rag() if use_rag else None
        
        # Load context examples if enabled
        self.context_examples = None
        if self.use_context_learning:
            self.context_examples = self._load_context_examples()
            if self.context_examples:
                logger.info(f"Loaded context learning examples from {context_learning_path}")
            else:
                logger.warning(f"No context learning examples found in {context_learning_path}")
        
        if self.use_rag and self.rag:
            logger.info("Initialized CodingAgent with RAG support")
        else:
            logger.info("Initialized CodingAgent without RAG")
    
    def _load_context_examples(self) -> str:
        """Load all context learning examples from the specified directory."""
        if not os.path.exists(self.context_learning_path):
            logger.warning(f"Context learning path does not exist: {self.context_learning_path}")
            return None
        
        examples = []
        example_files = glob.glob(f"{self.context_learning_path}/**/*.py", recursive=True)
        
        if not example_files:
            logger.warning(f"No Python files found in {self.context_learning_path}")
            return None
        
        for example_file in example_files:
            try:
                with open(example_file, 'r') as f:
                    example_code = f.read()
                    filename = os.path.basename(example_file)
                    examples.append(f"# Example from {filename}\n{example_code}\n")
            except Exception as e:
                logger.error(f"Error loading example {example_file}: {e}")
        
        if examples:
            header = """
# CONTEXT LEARNING EXAMPLES
# Below are real-world examples of well-written Manim code for physics visualizations.
# Study these patterns, coding styles, and best practices when generating new code.

"""
            return header + "\n".join(examples)
        
        return None

    def generate_code(self, question, solution, scene_plan, manim_executor=None, output_dir=None):
        """Generate Manim code for the given scene plan."""
        logger.info(f"Generating Manim code for the physics question with {len(scene_plan)} scenes")

        # Retrieve relevant Manim documentation if RAG is enabled
        manim_docs = ""
        if self.rag:
            try:
                scene_descriptions = []
                for scene in scene_plan:
                    if isinstance(scene, dict):
                        scene_descriptions.append(scene.get('description', ''))
                        scene_descriptions.append(scene.get('purpose', ''))
                
                scene_context = " ".join(scene_descriptions)
                
                logger.info("Retrieving Manim documentation from RAG...")
                manim_docs = self.rag.retrieve_for_code_generation(
                    scene_description=scene_context,
                    implementation_plan=str(solution),
                    top_k=5
                )
                
                if not manim_docs:
                    logger.info("No RAG documentation retrieved, using cheatsheet fallback")
                    manim_docs = get_manim_cheatsheet()
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}, falling back to cheatsheet")
                manim_docs = get_manim_cheatsheet()
        else:
            manim_docs = get_manim_cheatsheet()
        
        # Add context learning examples if available
        if self.context_examples:
            manim_docs = manim_docs + "\n\n" + self.context_examples
            logger.info("Added context learning examples to prompt")

        # ======================================================================
        # 🔥 LE SUPER-PROMPT "3BLUE1BROWN" INJECTÉ ICI ! 🔥
        # On force l'IA à utiliser ValueTracker et dessiner de beaux graphiques
        # ======================================================================
        physics_animation_rules = """
# ====================================================================
# CRITICAL ANIMATION RULES FOR PHYSICS (MANDATORY FOR THIS CODE):
# ====================================================================
1. VISUALIZE FIRST: DO NOT just write equations. You MUST draw a visual representation: a coordinate system (`Axes`) or `NumberPlane`.
2. MOTION ANIMATION: To animate physical motion (like a projectile, a falling block), you MUST use a `ValueTracker` to represent time (t).
3. UPDATERS: You MUST use `always_redraw()` to bind vectors (arrows), labels, or objects (Dot, Square) to the `ValueTracker`'s value. 
4. PERFECT PROJECTILE EXAMPLE:
   axes = Axes(x_range=[0, 300, 50], y_range=[0, 150, 50])
   t_tracker = ValueTracker(0)
   projectile = always_redraw(lambda: Dot(axes.c2p(x_func(t_tracker.get_value()), y_func(t_tracker.get_value())), color=YELLOW))
   velocity_vector = always_redraw(lambda: Arrow(start=projectile.get_center(), end=projectile.get_center() + v_func(t_tracker.get_value())))
   self.play(t_tracker.animate.set_value(max_time), run_time=5)
5. TRAJECTORIES: Draw trajectories using `TracedPath` attached to the projectile.
6. STYLE: Make it look like 3Blue1Brown: elegant, clear colored elements (YELLOW for objects, RED for forces/velocity).
# ====================================================================
"""
        manim_docs = manim_docs + "\n\n" + physics_animation_rules
        # ======================================================================

        prompt = get_coding_prompt(question, solution, scene_plan, manim_docs=manim_docs)
        
        try:
            response = self.client.generate_response(prompt, max_tokens=16000)
            logger.info(f"Received response type: {type(response)}, length: {len(response) if response else 0}")
        except Exception as e:
            logger.error(f"Exception during generate_response: {e}")
            return None
        
        if not response:
            return None
            
        code = self._extract_code(response)
        
        if not code:
            return None
            
        return code

    def fix_code(self, scene_plan, code, error_message):
        """Attempt to fix the provided Manim code based on the error message."""
        logger.info("Attempting to fix Manim code")
        
        manim_docs = ""
        if self.rag:
            try:
                manim_docs = self.rag.retrieve_for_error_fixing(
                    error_message=error_message,
                    code_snippet=code[:1000],
                    top_k=3
                )
            except Exception as e:
                logger.warning(f"RAG retrieval for error fixing failed: {e}")
        
        prompt = get_fix_code_prompt(scene_plan, code, error_message, manim_docs=manim_docs)
        response = self.client.generate_response(prompt, max_tokens=16000)
        
        if not response:
            return None
            
        fixed_code = self._extract_code(response)
        return fixed_code if fixed_code else code

    def improve_code_from_screenshots(self, scene_plan, code, visual_feedback):
        """Improve the provided Manim code based on visual feedback from screenshot analysis."""
        logger.info("Improving Manim code based on screenshot visual feedback")
        prompt = get_screenshot_feedback_prompt(scene_plan, code, visual_feedback)
        response = self.client.generate_response(prompt, max_tokens=16000)
        
        if not response:
            return None
            
        improved_code = self._extract_code(response)
        return improved_code if improved_code else code

    def _extract_code(self, response):
        """Extract python code from the model's response."""
        if not response:
            return None
            
        pattern = r"```python(.*?)```"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            code = match.group(1).strip()
            return code
        
        return response.strip()