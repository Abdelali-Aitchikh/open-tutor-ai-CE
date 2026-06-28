import os
import logging
import subprocess
import json
from gtts import gTTS

logger = logging.getLogger(__name__)

class TTSHandler:
    def __init__(self, output_dir="audio"):
        """Initialize the Text-to-Speech handler."""
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"Initialized TTSHandler with output directory: {self.output_dir}")
    
    def generate_audio(self, text, filename=None, lang="en", speed_factor=1.7):
        """
        Generate audio from text using TTS.
        
        Args:
            text: Text to convert to speech
            filename: Output filename (optional)
            lang: Language code (default: "en")
            speed_factor: Speed multiplier (default: 1.7 for 70% faster, range: 0.5-2.0)
        """
        try:
            if filename is None:
                # Create a temporary filename
                temp_filename = f"narration_{hash(text) % 10000:04d}.mp3"
                filename = os.path.join(self.output_dir, temp_filename)
            
            word_count = len(text.split())
            logger.info(f"Generating audio for text ({word_count} words)")
            
            # Convert text to speech
            tts = gTTS(text=text, lang=lang, slow=False)
            temp_filename = filename + ".temp.mp3"
            tts.save(temp_filename)
            
            # Adjust speed using ffmpeg (only if speed_factor is not 1.0)
            if abs(speed_factor - 1.0) > 0.01:  # Only apply if speed change is significant
                # Clamp speed factor to reasonable range
                speed_factor = max(0.5, min(2.0, speed_factor))
                subprocess.run([
                    "ffmpeg", "-i", temp_filename,
                    "-filter:a", f"atempo={speed_factor}",
                    "-y", filename
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            else:
                # No speed change needed, just rename
                os.rename(temp_filename, filename)
                temp_filename = None
            
            # Clean up temporary file
            if temp_filename and os.path.exists(temp_filename):
                os.remove(temp_filename)
            
            logger.info(f"Audio saved to {filename} (speed: {speed_factor}x)")
            return filename
            
        except Exception as e:
            logger.error(f"Error generating audio: {str(e)}")
            # Clean up on error
            if temp_filename and os.path.exists(temp_filename):
                os.remove(temp_filename)
            return None
    
    def get_audio_duration(self, audio_file):
        """
        Get the duration of an audio file in seconds.
        
        Args:
            audio_file: Path to the audio file
            
        Returns:
            Duration in seconds, or None if error
        """
        try:
            if not os.path.exists(audio_file):
                logger.error(f"Audio file not found: {audio_file}")
                return None
            
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 
                 'format=duration', '-of', 'json', audio_file],
                capture_output=True,
                text=True,
                check=True
            )
            
            info = json.loads(result.stdout)
            duration = float(info['format']['duration'])
            logger.debug(f"Audio duration for {audio_file}: {duration:.2f}s")
            return duration
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFprobe error for {audio_file}: {e.stderr}")
            return None
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing audio duration: {str(e)}")
            return None
    
    def generate_scene_audio(self, scene_plan):
        """Generate audio for each scene in the plan."""
        audio_files = {}
        
        for i, scene in enumerate(scene_plan):
            narration = scene.get("narration", "")
            
            if narration:
                # Clean narration text (remove quotes, etc.)
                narration = narration.strip('"\'')
                
                # Generate scene-specific filename
                filename = os.path.join(self.output_dir, f"scene_{i+1:02d}.mp3")
                
                # Generate the audio
                audio_file = self.generate_audio(narration, filename)
                
                if audio_file:
                    audio_files[i] = audio_file
            
        logger.info(f"Generated {len(audio_files)} audio files for {len(scene_plan)} scenes")
        return audio_files