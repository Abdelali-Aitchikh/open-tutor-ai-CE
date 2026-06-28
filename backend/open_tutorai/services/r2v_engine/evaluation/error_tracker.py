"""Error tracking and categorization for Manim code generation."""
import re
from typing import Dict, List, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class ErrorTracker:
    """Track and categorize errors during video generation."""
    
    # Simplified error categories: manim-related vs other
    MANIM_ERROR_KEYWORDS = [
        # LaTeX errors
        'latex', 'mathtex', 'tex', 'math mode', 'missing $', 'undefined control sequence',
        # Manim-specific errors
        'scene', 'animation', 'mobject', 'vmobject', 'from manim', 'manim import',
        # File/render errors
        'not found', 'no such file', 'cannot find', 'does not exist',
        # Syntax and indentation (usually in Manim code)
        'syntaxerror', 'indentationerror', 'taberror', 'expected an indented block', 'unexpected indent',
        # Common Manim runtime errors
        'attributeerror', 'nameerror', 'typeerror', 'valueerror',
        'runtimeerror', 'exception',
        # Rendering errors
        'render', 'ffmpeg', 'video', 'codec'
    ]
    
    def __init__(self):
        self.errors: List[Dict[str, str]] = []
        self.error_counts = defaultdict(int)
        self.attempt_errors = []  # Track errors per attempt
        
    def track_error(self, error_message: str, attempt: int = 1, context: str = ""):
        """Track an error with categorization."""
        category = self._categorize_error(error_message)
        
        error_info = {
            'attempt': attempt,
            'category': category,
            'message': error_message,
            'context': context
        }
        
        self.errors.append(error_info)
        self.error_counts[category] += 1
        
        # Track by attempt
        while len(self.attempt_errors) < attempt:
            self.attempt_errors.append([])
        self.attempt_errors[attempt - 1].append(error_info)
        
        logger.info(f"Tracked {category} error (attempt {attempt}): {error_message[:100]}...")
        
    def _categorize_error(self, error_message: str) -> str:
        """Categorize error as 'manim' or 'other'."""
        error_lower = error_message.lower()
        
        # Check if it's a manim-related error
        for keyword in self.MANIM_ERROR_KEYWORDS:
            if keyword in error_lower:
                return 'manim'
        
        # Everything else is 'other'
        return 'other'
    
    def get_error_summary(self) -> Dict:
        """Get a summary of all errors."""
        total_errors = len(self.errors)
        total_attempts = len(self.attempt_errors) if self.attempt_errors else 1
        
        # Calculate error rate as: total_errors / (total_attempts * 10)
        # Assuming max 10 errors per attempt would be 100% error rate
        # This gives a 0.0 to 1.0 range for error_rate
        max_errors_per_attempt = 5  # Reasonable threshold
        error_rate = min(1.0, total_errors / (total_attempts * max_errors_per_attempt)) if total_attempts > 0 else 0.0
        
        return {
            'total_errors': total_errors,
            'total_attempts': total_attempts,
            'error_rate': error_rate,  # 0.0 to 1.0 (0% to 100%)
            'error_counts': dict(self.error_counts),
            'errors_by_attempt': [
                {
                    'attempt': i + 1,
                    'count': len(errors),
                    'categories': self._count_categories(errors)
                }
                for i, errors in enumerate(self.attempt_errors)
            ],
            'all_errors': self.errors
        }
    
    def _count_categories(self, errors: List[Dict]) -> Dict[str, int]:
        """Count errors by category for a list of errors."""
        counts = defaultdict(int)
        for error in errors:
            counts[error['category']] += 1
        return dict(counts)
    
    def get_error_report(self) -> str:
        """Generate a formatted error report."""
        summary = self.get_error_summary()
        
        report = ["=" * 60]
        report.append("ERROR ANALYSIS REPORT")
        report.append("=" * 60)
        report.append(f"\nTotal Errors: {summary['total_errors']}")
        
        if summary['total_errors'] == 0:
            report.append("\n✓ No errors encountered during generation!")
            return "\n".join(report)
        
        report.append("\nError Categories:")
        report.append("-" * 40)
        for category, count in sorted(summary['error_counts'].items(), key=lambda x: x[1], reverse=True):
            report.append(f"  {category.capitalize()}: {count}")
        
        report.append("\nErrors by Attempt:")
        report.append("-" * 40)
        for attempt_data in summary['errors_by_attempt']:
            report.append(f"\n  Attempt {attempt_data['attempt']}: {attempt_data['count']} error(s)")
            if attempt_data['categories']:
                for cat, cnt in attempt_data['categories'].items():
                    report.append(f"    - {cat}: {cnt}")
        
        report.append("\n" + "=" * 60)
        return "\n".join(report)