"""Solution quality evaluation module with research-grade LLM-as-Judge."""
from typing import Dict, Any
import json
import logging
from utils.llm_client import get_llm_client
from config import OPENAI_API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

class SolutionEvaluator:
    """Evaluates the quality of physics solutions using LLM-as-Judge with rubric-based scoring."""
    
    def __init__(self):
        self.client = get_llm_client()
        
    def evaluate_solution(self, question: str, solution: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate the quality of a physics solution using research-grade rubrics.
        
        Uses LLM-as-Judge with deterministic prompting (temperature=0) and
        strict rubric-based scoring on 0-5 scale for 5 metrics:
        - Equation Correctness
        - Numerical Accuracy  
        - Step Completeness
        - Physics Concept Coverage
        - Mathematical Rigor
        
        Args:
            question: The original physics question
            solution: The generated solution
            
        Returns:
            Dictionary with evaluation metrics (0-5 scale)
        """
        try:
            prompt = self._create_evaluation_prompt(question, solution)
            # Use higher max_tokens for GPT-5/o1 models that use reasoning tokens
            response = self.client.generate_response(
                prompt=prompt,
                max_tokens=16000
            )
            
            logger.info(f"Raw evaluation response: {response[:200]}...")
            
            # Parse JSON response
            try:
                import re
                json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response
                
                evaluation = json.loads(json_str)
                
                # Validate all required fields exist
                required_fields = [
                    'equation_correctness',
                    'numerical_accuracy',
                    'step_completeness',
                    'concept_coverage',
                    'mathematical_rigor'
                ]
                
                for field in required_fields:
                    if field not in evaluation:
                        logger.warning(f"Missing field {field}, setting to 0")
                        evaluation[field] = 0
                
                # Calculate overall score (simple average of all metrics)
                if 'overall_score' not in evaluation:
                    scores = [
                        evaluation['equation_correctness'],
                        evaluation['numerical_accuracy'],
                        evaluation['step_completeness'],
                        evaluation['concept_coverage'],
                        evaluation['mathematical_rigor']
                    ]
                    evaluation['overall_score'] = sum(scores) / len(scores)
                    
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"JSON parsing error: {e}")
                logger.error(f"Response was: {response}")
                # Fallback to neutral evaluation
                evaluation = {
                    'equation_correctness': 2.5,
                    'numerical_accuracy': 2.5,
                    'step_completeness': 2.5,
                    'concept_coverage': 2.5,
                    'mathematical_rigor': 2.5,
                    'overall_score': 2.5,
                    'feedback': response,
                    'parse_error': str(e),
                    'confidence': 0
                }
            
            logger.info(f"Solution evaluation completed. Overall score: {evaluation.get('overall_score', 0):.2f}/5")
            return evaluation
            
        except Exception as e:
            logger.error(f"Error evaluating solution: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'error': str(e),
                'equation_correctness': 0,
                'numerical_accuracy': 0,
                'step_completeness': 0,
                'concept_coverage': 0,
                'mathematical_rigor': 0,
                'overall_score': 0,
                'confidence': 0
            }
    
    def _create_evaluation_prompt(self, question: str, solution: Dict[str, Any]) -> str:
        """Create research-grade evaluation prompt with explicit rubrics."""
        return f"""You are an expert physics professor evaluating a solution for research purposes.
Use the explicit rubrics below to score the solution on a 0-5 scale for each metric.
Be objective, deterministic, and justify your scores with evidence.

QUESTION:
{question}

SOLUTION:
{json.dumps(solution, indent=2)}

EVALUATION RUBRICS (0-5 scale):

1. EQUATION CORRECTNESS (0-5):
   5: All equations correct, properly derived, LaTeX formatted
   4: Minor notation issues or missing intermediate steps
   3: 1-2 major equation errors but approach correct
   2: Multiple equation errors, flawed approach
   1: Fundamentally wrong equations or missing
   0: No equations or completely incorrect

2. NUMERICAL ACCURACY (0-5):
   5: All numerical answers correct within 1% tolerance
   4: Correct within 5% tolerance
   3: Correct method, minor calculation errors
   2: Correct approach, significant calculation errors
   1: Wrong final answers due to conceptual errors
   0: Completely incorrect numerical results

3. STEP COMPLETENESS (0-5):
   5: All required steps present and explained
   4: Missing 1 minor step
   3: Missing 1 major step but derivable
   2: Missing 2+ major steps
   1: Solution jumps to answer without proper steps
   0: No steps shown, just final answer

4. PHYSICS CONCEPT COVERAGE (0-5):
   5: All relevant concepts explicitly mentioned and applied
   4: 1 minor concept implied but not stated
   3: 1 major concept missing or incorrect
   2: 2+ concepts missing
   1: Fundamental concepts misunderstood
   0: No relevant physics concepts mentioned

5. MATHEMATICAL RIGOR (0-5):
   5: Proper notation, clear derivations
   4: Minor notation inconsistencies
   3: Some unclear or poorly justified steps
   2: Logical gaps in derivation
   1: Mathematically unsound reasoning
   0: No mathematical justification

Provide your evaluation in the following strict JSON format:
{{
    "equation_correctness": <0-5>,
    "equation_correctness_evidence": "Brief justification with specific examples",
    "numerical_accuracy": <0-5>,
    "numerical_accuracy_evidence": "Brief justification with specific examples",
    "step_completeness": <0-5>,
    "step_completness_evidence": "Brief justification with specific examples",
    "concept_coverage": <0-5>,
    "concept_coverage_evidence": "Brief justification with specific examples",
    "mathematical_rigor": <0-5>,
    "mathematical_rigor_evidence": "Brief justification with specific examples",
    "overall_score": <average of above 5 metrics>,
    "strengths": ["specific strength 1", "specific strength 2"],
    "weaknesses": ["specific weakness 1", "specific weakness 2"],
    "confidence": <0-5, your confidence in this evaluation>,
    "feedback": "Concise summary of evaluation"
}}

Return ONLY valid JSON. No additional text."""