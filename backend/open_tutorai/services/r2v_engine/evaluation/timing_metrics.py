"""Timing metrics for tracking execution time of different stages."""
import time
from typing import Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TimingMetrics:
    """Track timing for different stages of video generation."""
    
    def __init__(self):
        self.stages = {}
        self.start_times = {}
        self.total_start = None
        
    def start_total(self):
        """Start tracking total execution time."""
        self.total_start = time.time()
        logger.info("Started total execution timer")
        
    def start_stage(self, stage_name: str):
        """Start timing a specific stage."""
        self.start_times[stage_name] = time.time()
        logger.debug(f"Started timer for: {stage_name}")
        
    def end_stage(self, stage_name: str):
        """End timing for a specific stage."""
        if stage_name not in self.start_times:
            logger.warning(f"No start time found for stage: {stage_name}")
            return
            
        duration = time.time() - self.start_times[stage_name]
        self.stages[stage_name] = duration
        logger.info(f"Completed {stage_name}: {duration:.2f}s")
        
    def get_total_time(self) -> float:
        """Get total execution time."""
        if self.total_start is None:
            return 0.0
        return time.time() - self.total_start
    
    def get_timing_summary(self) -> Dict:
        """Get summary of all timings."""
        total_time = self.get_total_time()
        
        return {
            'total_time': total_time,
            'total_time_seconds': total_time,  # Add this key for compatibility
            'total_time_formatted': self._format_duration(total_time),
            'stages': {
                stage: {
                    'duration': duration,
                    'duration_formatted': self._format_duration(duration),
                    'percentage': (duration / total_time * 100) if total_time > 0 else 0
                }
                for stage, duration in self.stages.items()
            }
        }
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.2f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}m {secs:.1f}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def get_timing_report(self) -> str:
        """Generate a formatted timing report."""
        summary = self.get_timing_summary()
        
        report = ["=" * 60]
        report.append("TIMING ANALYSIS REPORT")
        report.append("=" * 60)
        report.append(f"\nTotal Execution Time: {summary['total_time_formatted']}")
        
        if summary['stages']:
            report.append("\nStage Breakdown:")
            report.append("-" * 40)
            
            # Sort by duration (longest first)
            sorted_stages = sorted(
                summary['stages'].items(),
                key=lambda x: x[1]['duration'],
                reverse=True
            )
            
            for stage_name, stage_data in sorted_stages:
                report.append(
                    f"  {stage_name:30s}: {stage_data['duration_formatted']:>12s} "
                    f"({stage_data['percentage']:>5.1f}%)"
                )
        
        report.append("\n" + "=" * 60)
        return "\n".join(report)