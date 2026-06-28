"""Screenshot capture utility for video evaluation."""
import os
from typing import List, Optional
from moviepy.editor import VideoFileClip
from PIL import Image
import numpy as np
import logging

logger = logging.getLogger(__name__)

class ScreenshotCapture:
    """Capture screenshots from videos at specific timestamps."""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def capture_scene_screenshots(
        self, 
        video_path: str, 
        scene_name: str,
        scene_index: int
    ) -> List[str]:
        """
        Capture screenshots at start+2s, middle, and end-2s.
        
        Args:
            video_path: Path to the video file
            scene_name: Name of the scene
            scene_index: Index of the scene
            
        Returns:
            List of paths to captured screenshots
        """
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return []
        
        try:
            clip = VideoFileClip(video_path)
            duration = clip.duration
            
            # Create scene-specific directory
            scene_dir = os.path.join(self.output_dir, f"scene_{scene_index}_{scene_name}")
            os.makedirs(scene_dir, exist_ok=True)
            
            screenshots = []
            
            # Define timestamps: start+2s, middle, end-2s
            timestamps = self._get_timestamps(duration)
            
            for i, (time_point, label) in enumerate(timestamps):
                try:
                    # Get frame at timestamp
                    frame = clip.get_frame(time_point)
                    
                    # Convert to PIL Image and save
                    img = Image.fromarray(frame.astype('uint8'))
                    screenshot_path = os.path.join(
                        scene_dir, 
                        f"{label}_t{time_point:.2f}s.png"
                    )
                    img.save(screenshot_path)
                    screenshots.append(screenshot_path)
                    
                    logger.info(f"Captured screenshot for {scene_name} at {time_point:.2f}s ({label})")
                    
                except Exception as e:
                    logger.error(f"Error capturing screenshot at {time_point}s: {e}")
            
            clip.close()
            return screenshots
            
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {e}")
            return []
    
    def _get_timestamps(self, duration: float) -> List[tuple]:
        """
        Calculate timestamps for screenshots.
        
        Args:
            duration: Video duration in seconds
            
        Returns:
            List of (timestamp, label) tuples
        """
        timestamps = []
        
        # Start + 2s (or start if video < 2s)
        start_time = min(2.0, duration * 0.1)
        timestamps.append((start_time, "start"))
        
        # Middle
        middle_time = duration / 2
        timestamps.append((middle_time, "middle"))
        
        # End - 2s (or end if video < 2s)
        end_time = max(duration - 2.0, duration * 0.9)
        if end_time > 0:
            timestamps.append((end_time, "end"))
        
        return timestamps
    
    def capture_all_scenes(
        self, 
        video_files: List[str], 
        scene_names: List[str]
    ) -> dict:
        """
        Capture screenshots for all scenes.
        
        Args:
            video_files: List of video file paths
            scene_names: List of scene names
            
        Returns:
            Dictionary mapping scene names to screenshot paths
        """
        all_screenshots = {}
        
        for i, (video_path, scene_name) in enumerate(zip(video_files, scene_names)):
            screenshots = self.capture_scene_screenshots(
                video_path, 
                scene_name, 
                i + 1
            )
            all_screenshots[scene_name] = screenshots
        
        logger.info(f"Captured screenshots for {len(all_screenshots)} scenes")
        return all_screenshots