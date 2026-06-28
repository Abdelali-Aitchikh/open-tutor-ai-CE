import logging
import re
from config import OPENAI_API_KEY, MODEL_NAME
from utils.llm_client import get_llm_client
from agents.prompts.planner_prompts import get_planner_prompt

logger = logging.getLogger(__name__)

class PlannerAgent:
    def __init__(self):
        self.client = get_llm_client()
        logger.info("Initialized PlannerAgent")
        
    def generate_plan(self, question, solution):
        """Generate a video plan for explaining the physics solution."""
        logger.info(f"Generating plan for physics question")
        
        # Generate the prompt
        prompt = get_planner_prompt(question, solution)
        
        # Get response from the model
        # Use higher max_tokens for GPT-5/o1 models that use reasoning tokens
        response = self.client.generate_response(prompt, max_tokens=16000)
        
        # Extract the scene plan
        plan = self._extract_scene_plan(response)
        
        logger.info(f"Generated plan with {len(plan)} scenes")
        return plan
    
    def _extract_scene_plan(self, response):
        """Extract the scene plan from the model's response."""
        # Find the content between SCENE PLAN BEGIN: and SCENE PLAN END:
        pattern = r"SCENE PLAN BEGIN:(.*?)SCENE PLAN END:"
        match = re.search(pattern, response, re.DOTALL)
        
        if not match:
            logger.warning("Could not find scene plan in response. Using full response.")
            scene_text = response
        else:
            scene_text = match.group(1)
        
        # Split into individual scenes
        scene_blocks = re.split(r'\[Scene \d+\]', scene_text)
        scenes = []
        scene_number = 1
        
        # Process each scene block
        for block in scene_blocks:
            if not block.strip():
                continue
                
            scene = {'number': scene_number}  # Add scene number
            scene_number += 1
            
            # Extract title
            title_match = re.search(r'Title:(.*?)(?=Purpose:|$)', block, re.DOTALL)
            if title_match:
                scene['title'] = title_match.group(1).strip()
            
            # Extract purpose
            purpose_match = re.search(r'Purpose:(.*?)(?=Description:|$)', block, re.DOTALL)
            if purpose_match:
                scene['purpose'] = purpose_match.group(1).strip()
            
            # Extract description
            desc_match = re.search(r'Description:(.*?)(?=Layout:|$)', block, re.DOTALL)
            if desc_match:
                scene['description'] = desc_match.group(1).strip()
            
            # Extract layout
            layout_match = re.search(r'Layout:(.*?)(?=Narration:|$)', block, re.DOTALL)
            if layout_match:
                scene['layout'] = layout_match.group(1).strip()
            
            # Extract narration
            narration_match = re.search(r'Narration:(.*?)(?=\[Scene \d+\]|$)', block, re.DOTALL)
            if narration_match:
                scene['narration'] = narration_match.group(1).strip()
            
            if scene:  # Only add if we extracted something
                scenes.append(scene)
        
        return scenes