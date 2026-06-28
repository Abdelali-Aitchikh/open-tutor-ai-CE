"""Physics solution agent responsible for solving JEE-level physics questions."""
import logging
import re
from config import OPENAI_API_KEY, MODEL_NAME
from utils.llm_client import get_llm_client
from agents.prompts.solution_prompts import get_solution_prompt

logger = logging.getLogger(__name__)

class PhysicsSolutionAgent:
    def __init__(self):
        self.client = get_llm_client()
        logger.info("Initialized PhysicsSolutionAgent")

    def solve_question(self, question_text):
        """Solve a JEE physics question and generate a solution strategy."""
        try:
            logger.info(f"Solving physics question: {question_text[:100]}...")

            # Generate the solution prompt
            prompt = get_solution_prompt(question_text)
            logger.info(f"Using model: {self.client.model_name}")
            logger.info(f"Generated prompt: {prompt[:500]}...")
            logger.info(f"API key: {OPENAI_API_KEY[:10]}...")

            # Get solution from the model
            try:
                # Use higher max_tokens for GPT-5/o1 models that use reasoning tokens
                response = self.client.generate_response(prompt, max_tokens=16000)
            except Exception as e:
                logger.error(f"Failed to generate solution response: {str(e)}")
                raise RuntimeError(f"Model generation failed: {str(e)}")

            # Extract the solution plan
            try:
                solution = self._extract_solution_plan(response)
                if not solution:
                    logger.error("Failed to extract valid solution from response")
                    raise ValueError("No valid solution steps found in response")
            except Exception as e:
                logger.error(f"Failed to extract solution plan: {str(e)}")
                logger.debug(f"Response was: {response[:500]}...")
                raise RuntimeError(f"Solution extraction failed: {str(e)}")

            logger.info(f"Generated solution with {len(solution)} steps")
            return solution
            
        except Exception as e:
            logger.error(f"Failed to solve physics question: {str(e)}")
            raise

    def _extract_solution_plan(self, response):
        """Extract the structured solution from the model's response."""
        # Find the content between SOLUTION BEGIN: and SOLUTION END:
        pattern = r"SOLUTION BEGIN:(.*?)SOLUTION END:"
        match = re.search(pattern, response, re.DOTALL)

        if not match:
            logger.warning("Could not find solution markers in response. Using full response.")
            solution_text = response
        else:
            solution_text = match.group(1)

        # Split into solution steps
        step_blocks = re.split(r'\[Step \d+\]', solution_text)
        solution = []

        # Process each solution step
        for block in step_blocks:
            if not block.strip():
                continue

            step = {}

            # Extract approach/concept
            approach_match = re.search(r'Approach/Concept:(.*?)(?=Equation/Formula:|$)', block, re.DOTALL)
            if approach_match:
                step['approach'] = approach_match.group(1).strip()

            # Extract equations/formulas
            equation_match = re.search(r'Equation/Formula:(.*?)(?=Calculation:|$)', block, re.DOTALL)
            if equation_match:
                step['equation'] = equation_match.group(1).strip()

            # Extract calculation
            calc_match = re.search(r'Calculation:(.*?)(?=Explanation:|$)', block, re.DOTALL)
            if calc_match:
                step['calculation'] = calc_match.group(1).strip()

            # Extract explanation
            explain_match = re.search(r'Explanation:(.*?)(?=\[Step \d+\]|$)', block, re.DOTALL)
            if explain_match:
                step['explanation'] = explain_match.group(1).strip()

            # Add visualization hints if present
            viz_match = re.search(r'Visualization:(.*?)(?=\[Step \d+\]|$)', block, re.DOTALL)
            if viz_match:
                step['visualization'] = viz_match.group(1).strip()

            if step:  # Only add if we extracted something
                solution.append(step)

        return solution