"""Comprehensive evaluation report generator."""
import os
import json
from typing import Dict, Any, List
from datetime import datetime
import logging

from .error_tracker import ErrorTracker
from .timing_metrics import TimingMetrics
from .solution_evaluator import SolutionEvaluator
from .explanation_evaluator import ExplanationEvaluator
from .screenshot_capture import ScreenshotCapture
from .screenshot_analyzer import ScreenshotAnalyzer
from .csv_exporter import EvaluationCSVExporter

logger = logging.getLogger(__name__)

class EvaluationReport:
    """Generates comprehensive research-grade evaluation reports for video generation."""
    
    def __init__(self, output_dir: str, csv_path: str = "evaluation_metrics.csv"):
        self.output_dir = output_dir
        self.eval_dir = os.path.join(output_dir, "evaluation")
        os.makedirs(self.eval_dir, exist_ok=True)
        
        # Initialize components
        self.error_tracker = ErrorTracker()
        self.timing_metrics = TimingMetrics()
        self.solution_evaluator = SolutionEvaluator()
        self.explanation_evaluator = ExplanationEvaluator()
        self.screenshot_capture = ScreenshotCapture(self.eval_dir)
        
        # Initialize CSV exporter - use provided path or default to root directory
        # If csv_path is relative, it will be relative to current working directory (project root)
        self.csv_exporter = EvaluationCSVExporter(csv_path)
        self.screenshot_analyzer = ScreenshotAnalyzer()
        
        logger.info(f"Initialized EvaluationReport in {self.eval_dir}")
    
    def generate_report(
        self,
        question: str,
        solution: Dict[str, Any],
        scene_plan: List[Dict[str, Any]],
        video_files: List[str],
        scene_names: List[str] = None,
        final_video_path: str = None,
        success_status: str = "success",
        version: int = 1
    ) -> Dict[str, Any]:
        """
        Generate comprehensive evaluation report.
        
        Args:
            question: The physics question
            solution: Generated solution
            scene_plan: Generated scene plan
            video_files: List of generated video files
            scene_names: Optional list of scene names
            final_video_path: Path to the final assembled video
            success_status: Status of the video generation (success/partial/failed)
            version: Version number (1 for initial, 2 for corrected)
            
        Returns:
            Complete evaluation report
        """
        logger.info("Generating comprehensive evaluation report...")
        
        # Extract scene names if not provided
        if scene_names is None:
            scene_names = [f"Scene{i+1}" for i in range(len(video_files))]
        
        # 1. Evaluate solution correctness (0-100 scale)
        logger.info("Evaluating solution correctness...")
        solution_eval = self.solution_evaluator.evaluate_solution(question, solution)
        
        # 2. Evaluate explanation quality (0-100 scale)
        logger.info("Evaluating explanation quality...")
        explanation_eval = self.explanation_evaluator.evaluate_explanation(question, solution, scene_plan)
        
        # 3. Capture screenshots
        logger.info("Capturing screenshots from videos...")
        screenshots = self.screenshot_capture.capture_all_scenes(video_files, scene_names)
        
        # 4. Analyze screenshots with LLM
        logger.info("Analyzing screenshots with LLM...")
        screenshot_analyses = {}
        for i, (scene_name, scene_screenshots) in enumerate(screenshots.items()):
            scene_data = scene_plan[i] if i < len(scene_plan) else {}
            analysis = self.screenshot_analyzer.analyze_scene_screenshots(
                scene_screenshots,
                scene_data,
                i + 1  # Scene numbers start from 1, not 0
            )
            screenshot_analyses[scene_name] = analysis
        
        # Calculate average visual quality from screenshot analyses
        visual_quality_scores = []
        for scene_name, analysis in screenshot_analyses.items():
            # Check in summary first (preferred location)
            summary = analysis.get('summary', {})
            if 'avg_visual_quality_score' in summary:
                visual_quality_scores.append(summary['avg_visual_quality_score'])
            elif 'avg_visual_quality' in summary:
                visual_quality_scores.append(summary['avg_visual_quality'])
            # Fallback to top-level keys (older structure)
            elif 'average_visual_quality' in analysis:
                visual_quality_scores.append(analysis['average_visual_quality'])
            elif 'visual_quality_score' in analysis:
                visual_quality_scores.append(analysis['visual_quality_score'])
        
        avg_visual_quality = sum(visual_quality_scores) / len(visual_quality_scores) if visual_quality_scores else 2.5
        logger.info(f"Average visual quality score: {avg_visual_quality:.2f}")
        logger.info(f"Calculated from {len(visual_quality_scores)} scene scores: {visual_quality_scores}")
        
        # 5. Calculate overall research-grade score
        logger.info("Calculating overall research-grade score...")
        
        # Extract error penalty (0-5, where 5 = no errors)
        # Each error deducts 1 point, capped at 0
        error_summary = self.error_tracker.get_error_summary()
        total_errors = error_summary.get('total_errors', 0)
        error_penalty = max(0, 5 - total_errors)  # 1 error = 1 point deduction
        
        # Extract efficiency score (0-5, based on timing vs baseline)
        timing_summary = self.timing_metrics.get_timing_summary()
        total_time = timing_summary.get('total_time_seconds', 0)
        # Baseline: 600 seconds (10 minutes) - adjust based on your dataset
        baseline_time = 600
        # efficiency_score: 5 if time <= baseline, scales down proportionally
        efficiency_score = min(5, (baseline_time / max(total_time, 1)) * 5) if total_time > 0 else 5
        
        # Overall Score: Simple average of all component scores (0-5 scale)
        overall_score = (
            solution_eval.get('overall_score', 0) +
            explanation_eval.get('overall_score', 0) +
            avg_visual_quality +
            error_penalty
        ) / 4
        
        # Weighted Quality Score: Custom weighted average
        # Weights: Solution=5%, Explanation=10%, Visual=60%, Error=25%
        weighted_quality_score = (
            0.05 * solution_eval.get('overall_score', 0) +
            0.10 * explanation_eval.get('overall_score', 0) +
            0.60 * avg_visual_quality +
            0.25 * error_penalty
        )
        
        # 5. Compile complete report
        report = {
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'evaluation': {
                'solution_correctness': solution_eval,
                'explanation_quality': explanation_eval,
                'visual_quality': {
                    'average_score': avg_visual_quality,
                    'per_scene_analysis': screenshot_analyses
                },
                'error_penalty': {
                    'score': error_penalty,
                    'total_errors': total_errors,
                    'details': error_summary
                },
                'efficiency': {
                    'score': efficiency_score,
                    'total_time_seconds': total_time,
                    'baseline_time_seconds': baseline_time,
                    'details': timing_summary
                },
                'overall_score': overall_score,
                'weighted_quality_score': weighted_quality_score,
                'score_breakdown': {
                    'solution_correctness': solution_eval.get('overall_score', 0),
                    'explanation_quality': explanation_eval.get('overall_score', 0),
                    'visual_quality': avg_visual_quality,
                    'error_penalty': error_penalty
                },
                'weighted_score_breakdown': {
                    'solution_correctness_weighted': 0.05 * solution_eval.get('overall_score', 0),
                    'explanation_quality_weighted': 0.10 * explanation_eval.get('overall_score', 0),
                    'visual_quality_weighted': 0.60 * avg_visual_quality,
                    'error_penalty_weighted': 0.25 * error_penalty
                }
            },
            'screenshots': screenshots,
            'metadata': {
                'num_scenes': len(scene_plan),
                'num_videos': len(video_files),
                'num_screenshots': sum(len(ss) for ss in screenshots.values()),
                'evaluation_version': '2.0-research-grade',
                'question': question,
                'video_path': final_video_path,
                'status': success_status
            }
        }
        
        # 6. Save report files
        self._save_report_files(report, version)
        
        logger.info("Evaluation report generated successfully")
        return report
    
    def _save_report_files(self, report: Dict[str, Any], version: int = 1):
        """Save report in multiple formats.
        
        Args:
            report: The evaluation report dictionary
            version: Version number (1 for initial, 2 for corrected)
        """
        
        # Save JSON report
        json_path = os.path.join(self.eval_dir, "evaluation_report.json")
        with open(json_path, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Saved JSON report: {json_path}")
        
        # Save text report
        text_path = os.path.join(self.eval_dir, "evaluation_report.txt")
        with open(text_path, 'w') as f:
            f.write(self._format_text_report(report))
        logger.info(f"Saved text report: {text_path}")
        
        # Export to CSV with version
        question = report.get('metadata', {}).get('question', '')
        if self.csv_exporter.export_evaluation(report, question, version):
            logger.info(f"Exported metrics (version {version}) to CSV: {self.csv_exporter.get_csv_path()}")
        else:
            logger.warning("Failed to export metrics to CSV")
    
    def _format_text_report(self, report: Dict[str, Any]) -> str:
        """Format evaluation report as readable text (research-grade format).
        
        Args:
            report: Complete evaluation report dictionary with 0-5 scale metrics
            
        Returns:
            Formatted text report with comprehensive metric breakdown
        """
        lines = []
        lines.append("=" * 80)
        lines.append("RESEARCH-GRADE EVALUATION REPORT")
        lines.append("=" * 80)
        lines.append(f"\nTimestamp: {report['timestamp']}")
        lines.append(f"Question: {report['question']}\n")
        
        # Overall Score Section
        lines.append("=" * 80)
        lines.append("OVERALL SCORES (0-5 Scale)")
        lines.append("=" * 80)
        lines.append(f"Overall Score (Average):        {report['evaluation']['overall_score']:.2f}/5")
        lines.append(f"Weighted Quality Score:         {report['evaluation']['weighted_quality_score']:.2f}/5\n")
        lines.append("Score Breakdown (equal weighting - 25% each):")
        lines.append(f"  • Solution Correctness: {report['evaluation']['score_breakdown']['solution_correctness']:.2f}/5")
        lines.append(f"  • Explanation Quality:  {report['evaluation']['score_breakdown']['explanation_quality']:.2f}/5")
        lines.append(f"  • Visual Quality:       {report['evaluation']['score_breakdown']['visual_quality']:.2f}/5")
        lines.append(f"  • Error Penalty:        {report['evaluation']['score_breakdown']['error_penalty']:.2f}/5\n")
        lines.append("Weighted Score Breakdown (custom weights):")
        lines.append(f"  • Solution (5%):        {report['evaluation']['weighted_score_breakdown']['solution_correctness_weighted']:.2f}/5")
        lines.append(f"  • Explanation (10%):    {report['evaluation']['weighted_score_breakdown']['explanation_quality_weighted']:.2f}/5")
        lines.append(f"  • Visual (60%):         {report['evaluation']['weighted_score_breakdown']['visual_quality_weighted']:.2f}/5")
        lines.append(f"  • Error (25%):          {report['evaluation']['weighted_score_breakdown']['error_penalty_weighted']:.2f}/5\n")
        
        # Solution Correctness Section
        lines.append("=" * 80)
        lines.append("SOLUTION CORRECTNESS EVALUATION")
        lines.append("=" * 80)
        solution = report['evaluation']['solution_correctness']
        lines.append(f"Overall Score: {solution['overall_score']:.2f}/5\n")
        lines.append("Metric Scores:")
        lines.append(f"  • Equation Correctness: {solution.get('equation_correctness', 0):.2f}/5")
        lines.append(f"    Evidence: {solution.get('equation_correctness_evidence', 'N/A')}")
        lines.append(f"  • Numerical Accuracy: {solution.get('numerical_accuracy', 0):.2f}/5")
        lines.append(f"    Evidence: {solution.get('numerical_accuracy_evidence', 'N/A')}")
        lines.append(f"  • Step Completeness: {solution.get('step_completeness', 0):.2f}/5")
        lines.append(f"    Evidence: {solution.get('step_completeness_evidence', 'N/A')}")
        lines.append(f"  • Physics Concept Coverage: {solution.get('concept_coverage', 0):.2f}/5")
        lines.append(f"    Evidence: {solution.get('concept_coverage_evidence', 'N/A')}")
        lines.append(f"  • Mathematical Rigor: {solution.get('mathematical_rigor', 0):.2f}/5")
        lines.append(f"    Evidence: {solution.get('mathematical_rigor_evidence', 'N/A')}\n")
        
        if 'strengths' in solution and solution['strengths']:
            lines.append("Strengths:")
            for strength in solution['strengths']:
                lines.append(f"  + {strength}")
        
        if 'weaknesses' in solution and solution['weaknesses']:
            lines.append("Weaknesses:")
            for weakness in solution['weaknesses']:
                lines.append(f"  - {weakness}")
        lines.append("")
        
        # Explanation Quality Section
        lines.append("=" * 80)
        lines.append("EXPLANATION QUALITY EVALUATION")
        lines.append("=" * 80)
        explanation = report['evaluation']['explanation_quality']
        lines.append(f"Overall Score: {explanation['overall_score']:.2f}/5\n")
        lines.append("Metric Scores:")
        lines.append(f"  • Logical Flow: {explanation.get('logical_flow', 0):.2f}/5")
        lines.append(f"    Evidence: {explanation.get('logical_flow_evidence', 'N/A')}")
        lines.append(f"  • Pedagogical Clarity: {explanation.get('pedagogical_clarity', 0):.2f}/5")
        lines.append(f"    Evidence: {explanation.get('pedagogical_clarity_evidence', 'N/A')}")
        lines.append(f"  • Visualization Alignment: {explanation.get('visualization_alignment', 0):.2f}/5")
        lines.append(f"    Evidence: {explanation.get('visualization_alignment_evidence', 'N/A')}")
        lines.append(f"  • Intuition Building: {explanation.get('intuition_building', 0):.2f}/5")
        lines.append(f"    Evidence: {explanation.get('intuition_building_evidence', 'N/A')}")
        lines.append(f"  • Pacing & Accessibility: {explanation.get('pacing_accessibility', 0):.2f}/5")
        lines.append(f"    Evidence: {explanation.get('pacing_accessibility_evidence', 'N/A')}\n")
        
        if 'strengths' in explanation and explanation['strengths']:
            lines.append("Strengths:")
            for strength in explanation['strengths']:
                lines.append(f"  + {strength}")
        
        if 'weaknesses' in explanation and explanation['weaknesses']:
            lines.append("Weaknesses:")
            for weakness in explanation['weaknesses']:
                lines.append(f"  - {weakness}")
        lines.append("")
        
        # Visual Quality Section
        lines.append("=" * 80)
        lines.append("VISUAL QUALITY EVALUATION")
        lines.append("=" * 80)
        lines.append(f"Average Visual Score: {report['evaluation']['visual_quality']['average_score']:.2f}/5\n")
        
        for scene_name, analysis in report['evaluation']['visual_quality']['per_scene_analysis'].items():
            lines.append(f"\nScene: {scene_name}")
            
            # Calculate average score from individual analyses
            individual_analyses = analysis.get('individual_analyses', [])
            if individual_analyses:
                # Average all visual quality scores from the individual screenshots
                scores = []
                for indiv in individual_analyses:
                    layout = indiv.get('layout_quality', 0)
                    text = indiv.get('text_readability', 0)
                    equation = indiv.get('equation_rendering', 0)
                    overlap = indiv.get('overlap_issues', 0)
                    relevance = indiv.get('relevance_to_narration', 0)
                    
                    # Calculate average of available metrics
                    available_scores = [s for s in [layout, text, equation, overlap, relevance] if s > 0]
                    if available_scores:
                        scores.append(sum(available_scores) / len(available_scores))
                
                avg_scene_score = sum(scores) / len(scores) if scores else 0
                lines.append(f"  Average Score: {avg_scene_score:.2f}/5")
                lines.append(f"  Screenshots Analyzed: {len(individual_analyses)}")
                
                # Show summary if available
                summary = analysis.get('summary', {})
                if summary:
                    lines.append(f"  Summary:")
                    if 'avg_visual_quality' in summary:
                        lines.append(f"    • Visual Quality: {summary['avg_visual_quality']:.2f}/5")
                    if 'overlap_assessment' in summary:
                        lines.append(f"    • Overlap: {summary['overlap_assessment']}")
                    if 'relevance_assessment' in summary:
                        lines.append(f"    • Relevance: {summary['relevance_assessment']}")
            else:
                lines.append(f"  Average Score: 0.00/5")
                lines.append(f"  No screenshot analysis available")
            
            if analysis.get('visual_issues'):
                lines.append(f"  Issues: {', '.join(analysis['visual_issues'])}")
            if analysis.get('improvement_suggestions'):
                lines.append(f"  Suggestions: {', '.join(analysis['improvement_suggestions'])}")
        
        # Error & Efficiency Analysis
        lines.append("\n" + "=" * 80)
        lines.append("ERROR & EFFICIENCY ANALYSIS")
        lines.append("=" * 80)
        lines.append(f"Error Penalty Score: {report['evaluation']['error_penalty']['score']:.2f}/5")
        lines.append(f"Total Errors: {report['evaluation']['error_penalty'].get('total_errors', 0)} (each error deducts 1 point)")
        
        # Error Details
        error_details = report['evaluation']['error_penalty']['details']
        lines.append(f"\nTotal Errors Encountered: {error_details.get('total_errors', 0)}")
        lines.append(f"Total Attempts: {error_details.get('total_attempts', 0)}")
        
        # Error Categories Breakdown
        error_counts = error_details.get('error_counts', {})
        if error_counts:
            lines.append("\nError Types:")
            for category, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  • {category.capitalize()}: {count}")
        
        # Errors by Attempt
        errors_by_attempt = error_details.get('errors_by_attempt', [])
        if errors_by_attempt:
            lines.append("\nErrors by Attempt:")
            for attempt_data in errors_by_attempt:
                attempt_num = attempt_data.get('attempt', 0)
                error_count = attempt_data.get('count', 0)
                categories = attempt_data.get('categories', {})
                
                lines.append(f"  Attempt {attempt_num}: {error_count} error(s)")
                if categories:
                    for cat, cnt in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                        lines.append(f"    - {cat}: {cnt}")
        
        # Show detailed error messages (limit to first 5 to avoid clutter)
        all_errors = error_details.get('all_errors', [])
        if all_errors:
            lines.append("\nDetailed Error Messages:")
            for i, error in enumerate(all_errors[:5]):  # Show first 5 errors
                attempt = error.get('attempt', 0)
                category = error.get('category', 'unknown')
                message = error.get('message', 'No message')
                # Truncate long messages
                if len(message) > 150:
                    message = message[:150] + "..."
                lines.append(f"  [{attempt}] {category.capitalize()}: {message}")
            
            if len(all_errors) > 5:
                lines.append(f"  ... and {len(all_errors) - 5} more error(s)")
        
        if error_details.get('total_errors', 0) == 0:
            lines.append("\n✓ No errors encountered during generation!")
        
        # Efficiency section
        lines.append(f"\nEfficiency Score: {report['evaluation']['efficiency']['score']:.2f}/5")
        total_time = report['evaluation']['efficiency']['total_time_seconds']
        baseline_time = report['evaluation']['efficiency']['baseline_time_seconds']
        lines.append(f"Total Time: {total_time:.2f}s")
        lines.append(f"Baseline Time: {baseline_time:.2f}s")
        
        if total_time <= baseline_time:
            lines.append(f"✓ Completed within baseline time!")
        else:
            lines.append(f"⚠ Exceeded baseline by {total_time - baseline_time:.2f}s")
        lines.append("")
        
        # Metadata
        lines.append("=" * 80)
        lines.append("METADATA")
        lines.append("=" * 80)
        lines.append(f"Number of Scenes: {report['metadata']['num_scenes']}")
        lines.append(f"Number of Videos: {report['metadata']['num_videos']}")
        lines.append(f"Number of Screenshots: {report['metadata']['num_screenshots']}")
        lines.append(f"Evaluation Version: {report['metadata']['evaluation_version']}")
        lines.append("=" * 80)
        
        return "\n".join(lines)