"""Explanation quality evaluation module with pedagogical rubrics."""
from typing import Dict, Any, List
import json
import logging
from utils.llm_client import get_llm_client
from config import OPENAI_API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

class ExplanationEvaluator:
    """Evaluates pedagogical quality of explanations using research-grade rubrics."""
    
    def __init__(self):
        self.client = get_llm_client()
        
    def evaluate_explanation(
        self, 
        question: str, 
        solution: Dict[str, Any], 
        scene_plan: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate explanation quality using pedagogical rubrics (0-5 scale).
        
        Metrics:
        - Logical Flow
        - Pedagogical Clarity
        - Visualization Alignment
        - Intuition Building
        - Pacing & Accessibility
        
        Args:
            question: The original physics question
            solution: The generated solution
            scene_plan: The scene breakdown plan
            
        Returns:
            Dictionary with evaluation metrics (0-5 scale)
        """
        try:
            prompt = self._create_evaluation_prompt(question, solution, scene_plan)
            # Use higher max_tokens for GPT-5/o1 models that use reasoning tokens
            response = self.client.generate_response(
                prompt=prompt,
                max_tokens=16000
            )
            
            logger.info(f"Raw explanation evaluation response: {response[:200]}...")
            
            # Parse JSON response
            try:
                import re
                json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response
                
                evaluation = json.loads(json_str)
                
                # Validate required fields
                required_fields = [
                    'logical_flow',
                    'pedagogical_clarity',
                    'visualization_alignment',
                    'intuition_building',
                    'pacing_accessibility'
                ]
                
                for field in required_fields:
                    if field not in evaluation:
                        logger.warning(f"Missing field {field}, setting to 0")
                        evaluation[field] = 0
                
                # Calculate overall score (simple average)
                if 'overall_score' not in evaluation:
                    scores = [
                        evaluation['logical_flow'],
                        evaluation['pedagogical_clarity'],
                        evaluation['visualization_alignment'],
                        evaluation['intuition_building'],
                        evaluation['pacing_accessibility']
                    ]
                    evaluation['overall_score'] = sum(scores) / len(scores)
                    
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"JSON parsing error: {e}")
                logger.error(f"Response was: {response}")
                evaluation = {
                    'logical_flow': 2.5,
                    'pedagogical_clarity': 2.5,
                    'visualization_alignment': 2.5,
                    'intuition_building': 2.5,
                    'pacing_accessibility': 2.5,
                    'overall_score': 2.5,
                    'feedback': response,
                    'parse_error': str(e),
                    'confidence': 0
                }
            
            logger.info(f"Explanation evaluation completed. Overall score: {evaluation.get('overall_score', 0):.2f}/5")
            return evaluation
            
        except Exception as e:
            logger.error(f"Error evaluating explanation: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'error': str(e),
                'logical_flow': 0,
                'pedagogical_clarity': 0,
                'visualization_alignment': 0,
                'intuition_building': 0,
                'pacing_accessibility': 0,
                'overall_score': 0,
                'confidence': 0
            }
    
    def _create_evaluation_prompt(
        self, 
        question: str, 
        solution: Dict[str, Any], 
        scene_plan: List[Dict[str, Any]]
    ) -> str:
        """Create pedagogical evaluation prompt with explicit rubrics."""
        return f"""You are an expert in physics pedagogy and educational psychology evaluating an explanation for research purposes.
Use the explicit rubrics below to score the explanation on a 0-5 scale for each metric.

QUESTION:
{question}

SOLUTION:
{json.dumps(solution, indent=2)}

SCENE PLAN (Explanation Breakdown):
{json.dumps(scene_plan, indent=2)}

EVALUATION RUBRICS (0-5 scale):

1. LOGICAL FLOW (0-5):
   5: Perfect progression from problem to solution, each step builds on previous
   4: Clear flow with 1 minor transition issue
   3: Generally logical but 1-2 jumps or unclear transitions
   2: Multiple logical gaps or confusing sequence
   1: Disorganized, hard to follow progression
   0: No logical flow, completely scattered

2. PEDAGOGICAL CLARITY (0-5):
   5: Concepts explained at appropriate level, clear language, no ambiguity
   4: Very clear with 1 minor terminology/explanation issue
   3: Mostly clear but some jargon or unexplained terms
   2: Several unclear explanations or confusing statements
   1: Unclear, uses unexplained jargon, assumes too much knowledge
   0: Completely unclear or incomprehensible

3. VISUALIZATION ALIGNMENT (0-5):
   5: Each scene has clear visual purpose, animations match explanation perfectly
   4: Strong alignment with 1 minor mismatch
   3: Good alignment but some scenes lack clear visual purpose
   2: Several mismatches between visuals and explanation
   1: Poor alignment, visuals do not support understanding
   0: No alignment between visuals and explanation

4. INTUITION BUILDING (0-5):
   5: Builds deep understanding, connects to prior knowledge, provides insights
   4: Good intuition building with 1 missed opportunity
   3: Some intuition provided but could be deeper
   2: Limited intuition, mostly procedural
   1: No intuition building, purely mechanical
   0: Completely procedural, no understanding fostered

5. PACING & ACCESSIBILITY (0-5):
   5: Perfect pacing for target audience, appropriate difficulty progression
   4: Good pacing with 1 scene too fast/slow
   3: Generally appropriate but some pacing issues
   2: Multiple pacing problems, difficulty jumps
   1: Poor pacing, inappropriate for audience level
   0: Completely inappropriate pacing or difficulty

Provide your evaluation in the following strict JSON format:
{{
    "logical_flow": <0-5>,
    "logical_flow_evidence": "Brief justification",
    "pedagogical_clarity": <0-5>,
    "pedagogical_clarity_evidence": "Brief justification",
    "visualization_alignment": <0-5>,
    "visualization_alignment_evidence": "Brief justification",
    "intuition_building": <0-5>,
    "intuition_building_evidence": "Brief justification",
    "pacing_accessibility": <0-5>,
    "pacing_accessibility_evidence": "Brief justification",
    "overall_score": <average of above 5 metrics>,
    "strengths": ["specific strength 1", "specific strength 2"],
    "weaknesses": ["specific weakness 1", "specific weakness 2"],
    "suggestions": ["specific suggestion 1", "specific suggestion 2"],
    "confidence": <0-5>,
    "feedback": "Concise summary"
}}

Return ONLY valid JSON. No additional text."""