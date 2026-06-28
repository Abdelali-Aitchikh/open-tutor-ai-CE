"""CSV exporter for evaluation metrics."""
import csv
import os
import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class EvaluationCSVExporter:
    """Exports evaluation metrics to CSV file for analysis and tracking."""
    
    def __init__(self, csv_path: str = "evaluation_metrics.csv"):
        """
        Initialize CSV exporter.
        
        Args:
            csv_path: Path to the CSV file (default: evaluation_metrics.csv in current directory)
        """
        self.csv_path = csv_path
        self.fieldnames = self._get_fieldnames()
        self._ensure_csv_exists()
    
    def _get_fieldnames(self) -> List[str]:
        """Define all CSV column headers."""
        return [
            # Metadata
            'timestamp',
            'version',
            'question',
            'question_length',
            
            # Solution Quality Metrics
            'solution_score',
            'solution_correctness',
            'solution_explanation_quality',
            'solution_step_by_step_clarity',
            'solution_mathematical_rigor',
            
            # Explanation/Narration Quality Metrics
            'explanation_score',
            'logical_flow',
            'pedagogical_clarity',
            'visualization_alignment',
            'pacing_accessibility',
            
            # Visual Quality Metrics (Screenshot Analysis)
            'visual_quality_score',
            'layout_quality',
            'text_readability',
            'equation_rendering',
            'off_screen_issues',
            'scene_content_alignment',
            'num_screenshots_analyzed',
            
            # Scene-by-Scene Metrics
            'num_scenes',
            'avg_scene_visual_quality',
            'min_scene_visual_quality',
            'max_scene_visual_quality',
            
            # Individual Scene Scores (up to 25 scenes)
            'scene1_score', 'scene2_score', 'scene3_score', 'scene4_score', 'scene5_score',
            'scene6_score', 'scene7_score', 'scene8_score', 'scene9_score', 'scene10_score',
            'scene11_score', 'scene12_score', 'scene13_score', 'scene14_score', 'scene15_score',
            'scene16_score', 'scene17_score', 'scene18_score', 'scene19_score', 'scene20_score',
            'scene21_score', 'scene22_score', 'scene23_score', 'scene24_score', 'scene25_score',
            
            # Error Metrics
            'error_penalty_score',
            'total_errors',
            'error_rate',
            'manim_errors',
            'other_errors',
            
            # Timing Metrics (Simplified)
            'initial_video_generation_time',
            'correction_time',
            'total_execution_time',
            
            # Final Scores
            'overall_score',
            'weighted_quality_score',
            
            # Issues and Suggestions
            'critical_issues_count',
            'major_issues_count',
            'minor_issues_count',
            'top_issues',
            'top_suggestions',
            
            # Additional Context
            'has_video_output',
            'success_status'
        ]
    
    def _ensure_csv_exists(self):
        """Create CSV file with headers if it doesn't exist."""
        if not os.path.exists(self.csv_path):
            try:
                with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=self.fieldnames, quoting=csv.QUOTE_ALL)
                    writer.writeheader()
                logger.info(f"Created new CSV file: {self.csv_path}")
            except Exception as e:
                logger.error(f"Error creating CSV file: {e}")
    
    def export_evaluation(self, report: Dict[str, Any], question: str = "", version: int = 1):
        """
        Export evaluation report to CSV.
        
        Args:
            report: The evaluation report dictionary
            question: The original question/problem
            version: Version number (1 for initial, 2 for corrected)
        """
        try:
            # Extract metrics from report
            row = self._extract_metrics(report, question, version)
            
            # Append to CSV with proper quoting
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames, quoting=csv.QUOTE_ALL)
                writer.writerow(row)
            
            logger.info(f"Exported evaluation metrics (version {version}) to {self.csv_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _extract_metrics(self, report: Dict[str, Any], question: str, version: int = 1) -> Dict[str, Any]:
        """Extract all metrics from evaluation report into a flat dictionary."""
        
        eval_data = report.get('evaluation', {})
        metadata = report.get('metadata', {})
        
        # Initialize row with defaults
        row = {field: '' for field in self.fieldnames}
        
        # Metadata
        row['timestamp'] = datetime.now().isoformat()
        row['version'] = version  # 1 for initial, 2 for corrected
        # Clean question: remove newlines and limit length
        clean_question = question.replace('\n', ' ').replace('\r', ' ') if question else metadata.get('question', '').replace('\n', ' ').replace('\r', ' ')
        row['question'] = clean_question[:500]  # Truncate long questions
        row['question_length'] = len(question) if question else len(metadata.get('question', ''))
        
        # Solution Quality (Updated to match new structure)
        solution = eval_data.get('solution_correctness', {})
        row['solution_score'] = solution.get('overall_score', 0)
        
        row['solution_correctness'] = solution.get('equation_correctness', 0)
        row['solution_explanation_quality'] = solution.get('numerical_accuracy', 0)
        row['solution_step_by_step_clarity'] = solution.get('step_completeness', 0)
        row['solution_mathematical_rigor'] = solution.get('mathematical_rigor', 0)
        
        # Explanation/Narration Quality - evaluates teaching quality and narration
        explanation = eval_data.get('explanation_quality', {})
        row['explanation_score'] = explanation.get('overall_score', 0)
        
        row['logical_flow'] = explanation.get('logical_flow', 0)
        row['pedagogical_clarity'] = explanation.get('pedagogical_clarity', 0)
        row['visualization_alignment'] = explanation.get('visualization_alignment', 0)
        row['pacing_accessibility'] = explanation.get('pacing_accessibility', 0)
        
        # Visual Quality - aggregate from all scenes (Updated structure)
        visual_data = eval_data.get('visual_quality', {})
        screenshot_analyses = visual_data.get('per_scene_analysis', {})
        if screenshot_analyses:
            visual_scores = []
            layout_scores = []
            text_scores = []
            equation_scores = []
            offscreen_scores = []
            alignment_scores = []
            total_screenshots = 0
            
            for scene_idx, analysis in screenshot_analyses.items():
                if isinstance(analysis, dict):
                    summary = analysis.get('summary', {})
                    if summary:
                        if 'avg_visual_quality_score' in summary:
                            visual_scores.append(summary['avg_visual_quality_score'])
                        if 'avg_layout_quality' in summary:
                            layout_scores.append(summary['avg_layout_quality'])
                        if 'avg_text_readability' in summary:
                            text_scores.append(summary['avg_text_readability'])
                        if 'avg_equation_rendering' in summary:
                            equation_scores.append(summary['avg_equation_rendering'])
                        if 'avg_off_screen_issues' in summary:
                            offscreen_scores.append(summary['avg_off_screen_issues'])
                        if 'avg_scene_content_alignment' in summary:
                            alignment_scores.append(summary['avg_scene_content_alignment'])
                        
                        total_screenshots += summary.get('total_screenshots_analyzed', 0)
            
            row['visual_quality_score'] = sum(visual_scores) / len(visual_scores) if visual_scores else 0
            row['layout_quality'] = sum(layout_scores) / len(layout_scores) if layout_scores else 0
            row['text_readability'] = sum(text_scores) / len(text_scores) if text_scores else 0
            row['equation_rendering'] = sum(equation_scores) / len(equation_scores) if equation_scores else 0
            row['off_screen_issues'] = sum(offscreen_scores) / len(offscreen_scores) if offscreen_scores else 0
            row['scene_content_alignment'] = sum(alignment_scores) / len(alignment_scores) if alignment_scores else 0
            row['num_screenshots_analyzed'] = total_screenshots
            row['num_scenes'] = len(visual_scores)
            row['avg_scene_visual_quality'] = sum(visual_scores) / len(visual_scores) if visual_scores else 0
            row['min_scene_visual_quality'] = min(visual_scores) if visual_scores else 0
            row['max_scene_visual_quality'] = max(visual_scores) if visual_scores else 0
            
            # Populate individual scene scores (up to 25 scenes)
            for i in range(25):
                scene_col = f'scene{i+1}_score'
                if i < len(visual_scores):
                    row[scene_col] = visual_scores[i]
                else:
                    row[scene_col] = ''  # Empty for scenes that don't exist
        
        # Error Metrics (Updated structure)
        error_data = eval_data.get('error_penalty', {})
        row['error_penalty_score'] = error_data.get('score', 100)
        
        error_details = error_data.get('details', {})
        row['total_errors'] = error_details.get('total_errors', 0)
        row['error_rate'] = error_data.get('error_rate', 0)
        
        # Get error counts and map categories (simplified to manim vs other)
        error_counts = error_details.get('error_counts', {})
        # All categories except 'other' are considered manim errors
        row['manim_errors'] = error_counts.get('manim', 0)
        row['other_errors'] = error_counts.get('other', 0)
        
        # Timing Metrics (Simplified)
        efficiency_data = eval_data.get('efficiency', {})
        timing_details = efficiency_data.get('details', {})
        stages = timing_details.get('stages', {})
        
        # Total execution time
        row['total_execution_time'] = efficiency_data.get('total_time_seconds', 0)
        
        # Initial video generation time (solution + planning + code + manim + audio + assembly + first evaluation)
        initial_time = (
            stages.get('solution_generation', {}).get('duration', 0) +
            stages.get('scene_planning', {}).get('duration', 0) +
            stages.get('code_generation', {}).get('duration', 0) +
            stages.get('manim_execution', {}).get('duration', 0) +
            stages.get('audio_generation', {}).get('duration', 0) +
            stages.get('video_assembly', {}).get('duration', 0) +
            stages.get('evaluation', {}).get('duration', 0)
        )
        row['initial_video_generation_time'] = initial_time
        
        # Correction time (screenshot feedback loop - code fix + manim + assembly + evaluation)
        correction_time = stages.get('screenshot_feedback', {}).get('duration', 0)
        row['correction_time'] = correction_time
        
        # Final Scores
        # Overall Score: Simple average (equal weighting: 25% each component)
        row['overall_score'] = eval_data.get('overall_score', 0)
        
        # Weighted Quality Score: Custom weighted average
        # Weights: Solution=5%, Explanation=10%, Visual=60%, Error=25%
        weighted_quality_score = (
            0.05 * row['solution_score'] +       # 5%
            0.10 * row['explanation_score'] +    # 10%
            0.60 * row['visual_quality_score'] + # 60%
            0.25 * row['error_penalty_score']    # 25%
        )
        row['weighted_quality_score'] = weighted_quality_score
        
        # Issues and Suggestions (Updated to extract from solution and explanation)
        solution_issues = solution.get('weaknesses', [])
        explanation_issues = explanation.get('weaknesses', [])
        all_issues = solution_issues + explanation_issues
        
        # Count issues by severity (look for keywords)
        critical = [i for i in all_issues if isinstance(i, str) and ('critical' in i.lower() or 'severe' in i.lower())]
        major = [i for i in all_issues if isinstance(i, str) and ('major' in i.lower() or 'important' in i.lower())]
        minor = [i for i in all_issues if isinstance(i, str) and i not in critical and i not in major]
        
        row['critical_issues_count'] = len(critical)
        row['major_issues_count'] = len(major)
        row['minor_issues_count'] = len(minor)
        row['top_issues'] = '; '.join([str(i) for i in all_issues[:3]]) if all_issues else ''
        
        solution_suggestions = solution.get('suggestions', [])
        explanation_suggestions = explanation.get('suggestions', [])
        all_suggestions = solution_suggestions + explanation_suggestions
        row['top_suggestions'] = '; '.join([str(s) for s in all_suggestions[:3]]) if all_suggestions else ''
        
        # Additional Context
        row['has_video_output'] = 'yes' if metadata.get('video_path') else 'no'
        row['success_status'] = metadata.get('status', 'unknown')
        
        # Round all numeric values to 2 decimal places
        for key, value in row.items():
            if isinstance(value, float):
                row[key] = round(value, 2)
        
        return row
    
    def get_csv_path(self) -> str:
        """Return the path to the CSV file."""
        return os.path.abspath(self.csv_path)