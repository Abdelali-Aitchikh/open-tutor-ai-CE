"""Planner quality evaluation module."""
from typing import Dict, Any
import json
import logging
from utils.llm_client import get_llm_client
from config import OPENAI_API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

class PlannerEvaluator:
    """Evaluates the quality of scene planning."""
    
    def __init__(self):
        self.client = get_llm_client()
        
    def evaluate_plan(
        self, 
        question: str, 
        solution: Dict[str, Any], 
        scene_plan: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate the quality of the scene plan.
        
        Args:
            question: The original physics question
            solution: The generated solution
            scene_plan: The generated scene plan
            
        Returns:
            Dictionary with evaluation metrics
        """
        try:
            prompt = self._create_evaluation_prompt(question, solution, scene_plan)
            # Use higher max_tokens for GPT-5/o1 models that use reasoning tokens
            response = self.client.generate_response(
                prompt=prompt,
                max_tokens=12000,
                temperature=0.3
            )
            
            logger.info(f"Raw plan evaluation response: {response[:200]}...")
            
            # Try to parse JSON response - handle code blocks
            try:
                import re
                json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response
                
                evaluation = json.loads(json_str)
                
                # Ensure all required fields exist
                if 'overall_score' not in evaluation:
                    scores = [
                        evaluation.get('breakdown_score', 0),
                        evaluation.get('visualization_score', 0),
                        evaluation.get('flow_score', 0)
                    ]
                    evaluation['overall_score'] = sum(scores) / len(scores) if scores else 0
                
                if 'number_of_scenes' not in evaluation:
                    evaluation['number_of_scenes'] = len(scene_plan)
                    
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"JSON parsing error: {e}")
                logger.error(f"Response was: {response}")
                evaluation = {
                    'breakdown_score': 2.5,
                    'visualization_score': 2.5,
                    'flow_score': 2.5,
                    'overall_score': 2.5,
                    'number_of_scenes': len(scene_plan),
                    'feedback': response,
                    'parse_error': str(e)
                }
            
            logger.info(f"Plan evaluation completed. Overall score: {evaluation.get('overall_score', 0)}")
            return evaluation
            
        except Exception as e:
            logger.error(f"Error evaluating plan: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'error': str(e),
                'breakdown_score': 0,
                'visualization_score': 0,
                'flow_score': 0,
                'overall_score': 0,
                'number_of_scenes': len(scene_plan) if scene_plan else 0
            }
    
    def _create_evaluation_prompt(
        self, 
        question: str, 
        solution: Dict[str, Any], 
        scene_plan: List[Dict[str, Any]]
    ) -> str:
        """Create evaluation prompt for the scene plan."""
        return f"""You are an expert in educational video production and physics pedagogy.

QUESTION:
{question}

SOLUTION:
{json.dumps(solution, indent=2)}

SCENE PLAN:
{json.dumps(scene_plan, indent=2)}

Please evaluate how well the scene plan breaks down the solution for visualization:

1. Breakdown Quality (0-5): Are the steps logically divided into manageable scenes?
2. Visualization Potential (0-5): Are the scenes well-suited for visual animation?
3. Flow & Coherence (0-5): Does the sequence of scenes create a clear narrative?

Provide your evaluation in the following JSON format:
{{
    "breakdown_score": <0-5>,
    "visualization_score": <0-5>,
    "flow_score": <0-5>,
    "overall_score": <average of above>,
    "number_of_scenes": <count>,
    "strengths": ["strength 1", "strength 2", ...],
    "weaknesses": ["weakness 1", "weakness 2", ...],
    "suggestions": ["suggestion 1", "suggestion 2", ...],
    "feedback": "Detailed feedback text"
}}"""