"""Screenshot analysis module for visual quality evaluation."""
import logging
import os
import base64
from typing import List, Dict, Any
import json
from utils.llm_client import get_llm_client
from config import OPENAI_API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

class ScreenshotAnalyzer:
    """Analyzes screenshots for visual quality using VLM-based rubric evaluation."""
    
    def __init__(self):
        self.client = get_llm_client()
    
    def analyze_screenshot(
        self,
        screenshot_path: str,
        scene_data: Dict[str, Any],
        scene_index: int,
        timestamp_label: str
    ) -> Dict[str, Any]:
        """
        Analyze a single screenshot using LLM.
        
        Args:
            screenshot_path: Path to the screenshot image
            scene_data: The scene plan data for context
            scene_index: Index of the scene
            timestamp_label: Label for the timestamp (start/middle/end)
            
        Returns:
            Dictionary with analysis results
        """
        try:
            if not os.path.exists(screenshot_path):
                logger.error(f"Screenshot not found: {screenshot_path}")
                return {'error': 'Screenshot file not found'}
            
            # Read and encode image
            with open(screenshot_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Create analysis prompt
            prompt = self._create_analysis_prompt(scene_data, scene_index, timestamp_label)
            
            # Try to use vision API if available
            try:
                # Check if the client has vision capability
                if hasattr(self.client, 'generate_response_with_image'):
                    logger.info(f"Using vision API for screenshot analysis of scene {scene_index} ({timestamp_label})")
                    response = self.client.generate_response_with_image(
                        prompt=prompt,
                        image_base64=image_data,
                        max_tokens=8000,
                        temperature=1
                    )
                else:
                    logger.warning("Vision API not available, falling back to text-only analysis (less accurate)")
                    response = self.client.generate_response(
                        prompt=prompt,
                        max_tokens=8000,
                        temperature=1
                    )
            except Exception as e:
                logger.error(f"Vision API failed: {e}, falling back to text-only analysis")
                response = self.client.generate_response(
                    prompt=prompt,
                    max_tokens=8000,
                    temperature=1
                )
            
            logger.info(f"Screenshot analysis response for scene {scene_index} ({timestamp_label}): {response[:150]}...")
            
            # Try to parse JSON response
            try:
                import re
                json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response
                
                analysis = json.loads(json_str)
                
                # Check if scene is evaluable
                if not analysis.get('evaluable', True):
                    logger.info(f"Scene {scene_index} ({timestamp_label}) marked as NOT EVALUABLE: {analysis.get('reason', 'No reason provided')}")
                    # Return special marker for non-evaluable screenshot
                    return {
                        'evaluable': False,
                        'reason': analysis.get('reason', 'Incomplete scene'),
                        'screenshot_path': screenshot_path,
                        'scene_index': scene_index,
                        'timestamp': timestamp_label,
                        'skip_in_aggregation': True
                    }
                
                # Validate required fields for evaluable scenes
                required_fields = [
                    'layout_quality',
                    'text_readability',
                    'equation_rendering',
                    'off_screen_issues',
                    'scene_content_alignment'
                ]
                
                for field in required_fields:
                    if field not in analysis or analysis[field] is None:
                        logger.warning(f"Missing field {field}, setting to 2.5")
                        analysis[field] = 2.5
                
                # Calculate visual quality score if not present
                # Use average of LOWEST 2 scores to prevent inflation from non-applicable metrics
                if 'visual_quality_score' not in analysis or analysis['visual_quality_score'] is None:
                    scores = [
                        analysis['layout_quality'],
                        analysis['text_readability'],
                        analysis['equation_rendering'],
                        analysis['off_screen_issues'],
                        analysis['scene_content_alignment']
                    ]
                    # Sort scores and take average of lowest 2
                    sorted_scores = sorted(scores)
                    lowest_two = sorted_scores[:2]
                    analysis['visual_quality_score'] = sum(lowest_two) / 2.0
                    logger.info(f"Visual quality score calculated from lowest 2 scores: {lowest_two} = {analysis['visual_quality_score']:.2f}")
                    
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Could not parse JSON response: {e}")
                analysis = {
                    'layout_quality': 2.5,
                    'text_readability': 2.5,
                    'equation_rendering': 2.5,
                    'off_screen_issues': 2.5,
                    'scene_content_alignment': 2.5,
                    'visual_quality_score': 2.5,
                    'raw_feedback': response,
                    'confidence': 0
                }
            
            # Add metadata
            analysis['screenshot_path'] = screenshot_path
            analysis['scene_index'] = scene_index
            analysis['timestamp'] = timestamp_label
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing screenshot: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'error': str(e),
                'screenshot_path': screenshot_path,
                'scene_index': scene_index,
                'timestamp': timestamp_label
            }
    
    def _create_analysis_prompt(
        self,
        scene_data: Dict[str, Any],
        scene_index: int,
        timestamp_label: str
    ) -> str:
        """Create VLM analysis prompt with research-grade visual quality rubrics."""
        return f"""You are an expert in educational video production analyzing a Manim animation screenshot for research purposes.

⚠️ CRITICAL FIRST STEP - SCENE COMPLETENESS CHECK:
Before evaluating quality, determine if this screenshot shows a COMPLETE, EVALUABLE scene:

EVALUABLE (proceed with scoring):
- Scene has substantial content: multiple text elements, equations, diagrams, or animations
- Educational content is clearly visible and developed
- Scene appears to be at a meaningful state (not just starting/ending)
- Enough visual elements present to assess layout, readability, and alignment

NOT EVALUABLE (skip scoring, mark as incomplete):
- Nearly blank screen with only 1-2 lines of text appearing/disappearing
- Scene in transition with minimal content visible
- Just a title or single element on screen
- Scene clearly caught mid-animation before content fully appears

IF NOT EVALUABLE: Return JSON with "evaluable": false, "reason": "<why not evaluable>", and set all scores to null.
IF EVALUABLE: Proceed with strict evaluation below.

IMPORTANT SCORING GUIDELINES (for evaluable scenes):
- Use WHOLE NUMBERS ONLY (0, 1, 2, 3, 4, or 5) for individual metrics
- Be very stringent - most animations will have issues
- Look carefully for overlapping elements, text cut-offs, LaTeX rendering errors
- Only give 5 if the screenshot is nearly perfect
- Give 4 for good quality with minor issues
- Give 3 for noticeable problems
- Give 2 for significant issues
- Give 0-1 for serious/severe issues

SCENE {scene_index} INFORMATION:
{json.dumps(scene_data, indent=2)}

SCREENSHOT TIMESTAMP: {timestamp_label}

VISUAL QUALITY RUBRICS (0-5 scale, WHOLE NUMBERS ONLY - BE STRICT, only for EVALUABLE scenes):

CRITICAL: Check for these common issues and penalize heavily:
- Overlapping text or equations (reduce layout_quality by 1-2 points)
- LaTeX rendering errors like "\\text" or broken symbols (reduce equation_rendering by 1-2 points)
- Any content cut off at screen edges (reduce off_screen_issues by 1-2 points)
- Text too small to read comfortably (reduce text_readability by 1-2 points)
- Misaligned equations or text (reduce layout_quality by 1 point)

1. LAYOUT QUALITY (0-5 whole number):
   5: PERFECT spacing, hierarchy, balance; zero crowding, zero overlap, zero empty space issues
   4: Excellent layout with only 1 very minor spacing inconsistency
   3: Good layout but has minor positioning issues or slight overlap
   2: Noticeable spacing/positioning problems, some elements overlap
   1: Multiple overlapping elements, poor spacing, cluttered appearance
   0: Severe overlap, completely cluttered, unusable layout

2. TEXT READABILITY (0-5 whole number):
   5: ALL text perfectly legible, optimal font sizes (not too small/large), excellent contrast
   4: Very readable, one piece of text slightly suboptimal
   3: Mostly readable but some text is too small, too large, or low contrast
   2: Several readability issues, some text hard to read
   1: Multiple text elements illegible or poorly sized
   0: Most text illegible, missing, or completely unreadable

3. EQUATION RENDERING (0-5 whole number):
   5: ALL LaTeX equations perfectly rendered, no errors, perfect alignment and spacing
   4: Excellent rendering with 1 very minor formatting inconsistency
   3: Good but has some misalignment, spacing issues, or minor LaTeX errors
   2: Multiple equation rendering problems, visible LaTeX errors, poor formatting
   1: Serious LaTeX rendering errors, equations malformed or misaligned
   0: Equations completely broken, unreadable, or incorrectly rendered

4. OFF-SCREEN ISSUES (0-5 whole number):
   5: ALL elements fully visible, perfect framing, nothing cut off
   4: One very minor, non-critical element barely touching edge
   3: Some minor elements slightly cut off at edges
   2: Important elements partially off-screen or cut off
   1: Critical content cut off, multiple elements off-screen
   0: Major content missing due to being off-screen

5. SCENE-CONTENT ALIGNMENT (0-5 whole number):
   5: Visuals PERFECTLY match intended content, narration, and scene description
   4: Strong alignment with only 1 very minor mismatch
   3: Good alignment but some visual elements don't fully match description
   2: Several mismatches between visuals and intended content
   1: Significant mismatches, visuals don't represent content well
   0: Visuals completely don't match intended scene content

Provide your analysis in the following strict JSON format:

IF NOT EVALUABLE:
{{
    "evaluable": false,
    "reason": "Specific reason why scene is incomplete/not evaluable",
    "layout_quality": null,
    "text_readability": null,
    "equation_rendering": null,
    "off_screen_issues": null,
    "scene_content_alignment": null,
    "visual_quality_score": null,
    "confidence": 0
}}

IF EVALUABLE:
{{
    "evaluable": true,
    "layout_quality": <whole number 0-5>,
    "layout_quality_evidence": "Specific observations about spacing, overlap, positioning",
    "text_readability": <whole number 0-5>,
    "text_readability_evidence": "Specific observations about font sizes, contrast, legibility",
    "equation_rendering": <whole number 0-5>,
    "equation_rendering_evidence": "Specific observations about LaTeX rendering, errors, alignment",
    "off_screen_issues": <whole number 0-5>,
    "off_screen_issues_evidence": "Specific observations about elements cut off or off-screen",
    "scene_content_alignment": <whole number 0-5>,
    "scene_content_alignment_evidence": "Specific observations about visual-content match",
    "issues": ["specific issue 1 with severity", "specific issue 2 with severity"],
    "suggestions": ["specific actionable suggestion 1", "specific actionable suggestion 2"],
    "confidence": <whole number 0-5>,
    "feedback": "Concise critical summary highlighting all problems found"
}}

NOTE: Do NOT include "visual_quality_score" in your response. It will be calculated automatically as the average of the LOWEST 2 scores from the 5 metrics above (to avoid inflation from non-applicable metrics).

Return ONLY valid JSON. No additional text."""
    
    def analyze_scene_screenshots(
        self,
        screenshots: List[str],
        scene_data: Dict[str, Any],
        scene_index: int
    ) -> Dict[str, Any]:
        """
        Analyze all screenshots for a scene.
        
        Args:
            screenshots: List of screenshot paths
            scene_data: Scene plan data
            scene_index: Index of the scene
            
        Returns:
            Aggregated analysis for the scene
        """
        analyses = []
        
        for screenshot in screenshots:
            # Extract timestamp label from filename
            filename = os.path.basename(screenshot)
            if 'start' in filename:
                timestamp_label = 'start'
            elif 'middle' in filename:
                timestamp_label = 'middle'
            elif 'end' in filename:
                timestamp_label = 'end'
            else:
                timestamp_label = 'unknown'
            
            analysis = self.analyze_screenshot(
                screenshot,
                scene_data,
                scene_index,
                timestamp_label
            )
            analyses.append(analysis)
        
        # Aggregate results
        aggregated = {
            'scene_index': scene_index,
            'num_screenshots': len(screenshots),
            'individual_analyses': analyses,
            'summary': self._aggregate_analyses(analyses)
        }
        
        return aggregated
    
    def _aggregate_analyses(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate multiple screenshot analyses into a summary with 0-5 scale metrics."""
        if not analyses:
            return {}
        
        # Filter out non-evaluable screenshots (incomplete scenes)
        evaluable_analyses = [a for a in analyses if not a.get('skip_in_aggregation', False)]
        non_evaluable_count = len(analyses) - len(evaluable_analyses)
        
        if non_evaluable_count > 0:
            logger.info(f"Skipping {non_evaluable_count} non-evaluable screenshots (incomplete scenes) in aggregation")
            logger.info(f"Using only {len(evaluable_analyses)} out of {len(analyses)} screenshots for scoring")
        
        # If no evaluable screenshots, return default scores
        if not evaluable_analyses:
            logger.warning("No evaluable screenshots found - all were incomplete scenes. Using default scores.")
            return {
                'avg_layout_quality': 3.75,  # Neutral score since we can't evaluate
                'avg_text_readability': 3.75,
                'avg_equation_rendering': 3.75,
                'avg_off_screen_issues': 3.75,
                'avg_scene_content_alignment': 3.75,
                'avg_visual_quality_score': 3.75,
                'avg_confidence': 0,
                'total_screenshots_analyzed': len(analyses),
                'evaluable_screenshots': 0,
                'non_evaluable_screenshots': non_evaluable_count,
                'min_layout_quality': 0,
                'max_layout_quality': 0,
                'min_visual_quality': 0,
                'max_visual_quality': 0
            }
        
        # Aggregate scores across evaluable screenshots only
        layout_scores = []
        text_scores = []
        equation_scores = []
        offscreen_scores = []
        alignment_scores = []
        visual_scores = []
        confidence_scores = []
        
        for analysis in evaluable_analyses:
            if 'layout_quality' in analysis:
                layout_scores.append(analysis['layout_quality'])
            if 'text_readability' in analysis:
                text_scores.append(analysis['text_readability'])
            if 'equation_rendering' in analysis:
                equation_scores.append(analysis['equation_rendering'])
            if 'off_screen_issues' in analysis:
                offscreen_scores.append(analysis['off_screen_issues'])
            if 'scene_content_alignment' in analysis:
                alignment_scores.append(analysis['scene_content_alignment'])
            if 'visual_quality_score' in analysis:
                visual_scores.append(analysis['visual_quality_score'])
            if 'confidence' in analysis:
                confidence_scores.append(analysis['confidence'])
        
        summary = {
            'avg_layout_quality': sum(layout_scores) / len(layout_scores) if layout_scores else 3.75,
            'avg_text_readability': sum(text_scores) / len(text_scores) if text_scores else 3.75,
            'avg_equation_rendering': sum(equation_scores) / len(equation_scores) if equation_scores else 3.75,
            'avg_off_screen_issues': sum(offscreen_scores) / len(offscreen_scores) if offscreen_scores else 3.75,
            'avg_scene_content_alignment': sum(alignment_scores) / len(alignment_scores) if alignment_scores else 3.75,
            'avg_visual_quality_score': sum(visual_scores) / len(visual_scores) if visual_scores else 3.75,
            'avg_confidence': sum(confidence_scores) / len(confidence_scores) if confidence_scores else 2.5,
            'total_screenshots_analyzed': len(analyses),
            'evaluable_screenshots': len(evaluable_analyses),
            'non_evaluable_screenshots': non_evaluable_count,
            'min_layout_quality': min(layout_scores) if layout_scores else 0,
            'max_layout_quality': max(layout_scores) if layout_scores else 0,
            'min_visual_quality': min(visual_scores) if visual_scores else 0,
            'max_visual_quality': max(visual_scores) if visual_scores else 0
        }
        
        return summary