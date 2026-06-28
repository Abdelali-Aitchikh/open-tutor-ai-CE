import os
import logging
import argparse
import subprocess
import traceback
import json
import tempfile
from collections import OrderedDict
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

logger = logging.getLogger(__name__)

class VideoAssembler:
    def __init__(self, output_dir="videos", error_tracker=None):
        """Initialize the Video Assembler."""
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.temp_files = []  # Track intermediate files for cleanup
        self.error_tracker = error_tracker
        logger.info(f"Initialized VideoAssembler with output directory: {self.output_dir}")
    
    def track_error(self, error, context=None):
        """Track error if error tracker is available."""
        if self.error_tracker:
            self.error_tracker.track_error(error, f"Video Assembly: {context}")
        logger.error(f"Video Assembly Error ({context}): {str(error)}")

    def cleanup_intermediate_files(self):
        """Clean up all intermediate files after successful video assembly."""
        logger.info("Cleaning up intermediate files...")
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"Removed intermediate file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove file {file_path}: {e}")
        self.temp_files = []

    def combine_audio_video(self, video_path, audio_path, output_path):
        """Combine audio and video files."""
        # Track input files for cleanup
        self.temp_files.extend([video_path, audio_path])
        try:
            audio = AudioFileClip(audio_path)
            video = VideoFileClip(video_path)
            
            # Get durations
            audio_duration = audio.duration
            video_duration = video.duration
            
            # If audio is longer than video, extend video by freezing last frame
            if audio_duration > video_duration:
                with tempfile.TemporaryDirectory() as temp_dir:
                    last_frame = os.path.join(temp_dir, "last_frame.png")
                    cmd = [
                        'ffmpeg', '-i', video_path,
                        '-vf', 'select=gte(n\\,n_frames-1)',
                        '-vframes', '1', '-y', last_frame
                    ]
                    subprocess.run(cmd, check=True)
                    
                    # Create extended video
                    extended = os.path.join(temp_dir, "extended.mp4")
                    cmd = [
                        'ffmpeg', '-i', video_path,
                        '-loop', '1', '-i', last_frame,
                        '-t', str(audio_duration),
                        '-filter_complex', f'[0:v][1:v]concat=n=2:v=1:a=0',
                        '-y', extended
                    ]
                    subprocess.run(cmd, check=True)
                    video_path = extended
                    video = VideoFileClip(video_path)
            video = video.with_audio(audio)
            
            logger.info(f"Writing combined video to {output_path}")
            video.write_videofile(output_path, codec="libx264", audio_codec="aac")
            return True
        except Exception as e:
            self.track_error(e, f"Audio-Video Combination ({os.path.basename(video_path)})")
            return False
            return False

    def get_duration(self, file_path):
        """Get the duration of a media file in seconds."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries",
            "format=duration",
            "-of", "json",
            file_path
        ]
        try:
            output = subprocess.check_output(cmd, universal_newlines=True).strip()
            data = json.loads(output)
            duration = float(data['format']['duration'])
            return duration
        except Exception as e:
            logger.error(f"Error getting duration for {file_path}: {str(e)}")
            return 0.0

    def extend_video_duration(self, video_path, target_duration, output_path):
        """Extend a video to a target duration by freezing the last frame."""
        try:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp()
            
            # Get video properties for matching in the output
            properties = self.get_video_properties(video_path)
            
            # Calculate how much freeze time we need
            video_duration = self.get_duration(video_path)
            freeze_duration = max(0, target_duration - video_duration)
            
            if freeze_duration <= 0:
                # No need to extend, just copy the video
                cmd = ["ffmpeg", "-i", video_path, "-c", "copy", "-y", output_path]
                subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return output_path
                
            # Extract the last frame
            duration = self.get_duration(video_path)
            last_frame = os.path.join(temp_dir, "last_frame.png")
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-vf", "select=gte(n\\,n_frames-1)",
                "-vframes", "1",
                "-y",
                last_frame
            ]
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Create freeze frame video
            freeze_video = os.path.join(temp_dir, "freeze.mp4")
            cmd = [
                "ffmpeg",
                "-loop", "1",
                "-i", last_frame,
                "-t", str(freeze_duration),
                "-vf", f"fps={properties['fps']}",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-y",
                freeze_video
            ]
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Concatenate original video with freeze frame video
            concat_file = os.path.join(temp_dir, "concat.txt")
            with open(concat_file, "w") as f:
                f.write(f"file '{os.path.abspath(video_path)}'\n")
                f.write(f"file '{os.path.abspath(freeze_video)}'\n")
            
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                "-y",
                output_path
            ]
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Clean up temporary files
            for temp_file in [last_frame, freeze_video, concat_file]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            os.rmdir(temp_dir)
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error extending video duration: {str(e)}")
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    def get_video_properties(self, video_path):
        """Get video properties like resolution, fps, etc."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,codec_name",
            "-of", "json",
            video_path
        ]
        try:
            output = subprocess.check_output(cmd, universal_newlines=True).strip()
            data = json.loads(output)
            if 'streams' in data and data['streams']:
                stream = data['streams'][0]

                # Parse frame rate which might be in "num/den" format
                fps = stream.get('r_frame_rate', '30/1')
                if '/' in fps:
                    num, den = map(int, fps.split('/'))
                    fps = num / den if den != 0 else 30
                else:
                    fps = float(fps)

                return {
                    'width': stream.get('width', 1280),
                    'height': stream.get('height', 720),
                    'fps': fps,
                    'codec': stream.get('codec_name', 'h264')
                }
        except Exception as e:
            logger.error(f"Error getting video properties for {video_path}: {str(e)}")

        # Return defaults if anything fails
        return {'width': 1280, 'height': 720, 'fps': 30, 'codec': 'h264'}

    def assemble_final_video(self, video_files, audio_files=None, output_filename=None):
        """Assemble the final video from multiple clips using simple concatenation."""
        try:
            if not video_files:
                logger.error("No video files provided.")
                return None

            if output_filename is None:
                output_filename = os.path.join(self.output_dir, "theorem_explanation.mp4")

            # Since audio is already embedded in the video files from manim-voiceover,
            # we just need to concatenate them without any processing
            logger.info(f"Concatenating {len(video_files)} video segments with embedded audio")
            
            temp_dir = os.path.join(self.output_dir, "temp")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Create file list for ffmpeg concat
            file_list_path = os.path.join(temp_dir, "concat_list.txt")
            with open(file_list_path, "w") as f:
                for video_file in video_files:
                    if os.path.exists(video_file):
                        f.write(f"file '{os.path.abspath(video_file)}'\n")
                    else:
                        logger.warning(f"Video file not found: {video_file}")
            
            # Use concat demuxer with stream copy - this is the fastest and most reliable
            # It joins videos exactly as they are without any re-encoding
            concat_cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", file_list_path,
                "-c", "copy",  # Copy streams directly - no re-encoding, preserves everything
                "-movflags", "+faststart",  # Optimize for streaming
                "-y",
                output_filename
            ]
            
            logger.info("Concatenating videos with stream copy (no re-encoding)...")
            result = subprocess.run(concat_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"✓ Final video assembled successfully at {output_filename}")
                
                # Clean up temp directory
                import shutil
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                
                return output_filename
            else:
                # If stream copy fails, log the error and return None
                logger.error(f"FFmpeg concatenation failed: {result.stderr}")
                logger.error("All individual scene videos should have the same codec settings from Manim")
                
                # Clean up temp directory
                import shutil
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                
                return None

        except Exception as e:
            logger.error(f"Error in video assembly: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
            # Extract the last frame - use a more robust method than -sseof
            # First get the duration from ffprobe
            duration = self.get_duration(video_path)

            # Use this duration to extract the last frame
            last_frame = os.path.join(temp_dir, "last_frame.png")
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-ss", str(max(0, duration - 0.1)),  # Seek to the last 0.1 seconds
                "-vframes", "1",  # Extract just one frame
                "-y",
                last_frame
            ]

            try:
                subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                # If that fails, try without seeking
                logger.warning("Failed to extract last frame with seeking, trying simpler method")
                cmd = [
                    "ffmpeg",
                    "-i", video_path,
                    "-vframes", "1",  # Just grab the first frame if all else fails
                    "-y",
                    last_frame
                ]
                subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Create a video from the last frame with matching properties
            freeze_video = os.path.join(temp_dir, "freeze.mp4")
            cmd = [
                "ffmpeg",
                "-loop", "1",
                "-i", last_frame,
                "-t", str(freeze_duration),
                "-vf", f"fps={properties['fps']}",  # Match original FPS
                "-c:v", "libx264",  # Use a high-quality intermediate codec
                "-pix_fmt", "yuv420p",
                "-preset", "medium",
                "-b:v", "5000k",    # Use high bitrate for quality
                "-y",
                freeze_video
            ]
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Create a silent audio track if needed
            silent_audio = os.path.join(temp_dir, "silence.mp3")
            cmd = [
                "ffmpeg",
                "-f", "lavfi",
                "-i", "anullsrc=r=44100:cl=stereo",
                "-t", str(freeze_duration),
                "-y",
                silent_audio
            ]
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Add silent audio to freeze video
            freeze_with_audio = os.path.join(temp_dir, "freeze_with_audio.mp4")
            cmd = [
                "ffmpeg",
                "-i", freeze_video,
                "-i", silent_audio,
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                "-y",
                freeze_with_audio
            ]
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Try simplest and most reliable concat approach
            concat_file = os.path.join(temp_dir, "concat.txt")
            with open(concat_file, "w") as f:
                f.write(f"file '{os.path.abspath(video_path)}'\n")
                f.write(f"file '{os.path.abspath(freeze_with_audio)}'\n")

            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                "-c:a", "aac",
                "-b:a", "192k",
                "-y",
                output_path
            ]
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return output_path

    def assemble_video(self, video_files, audio_files, output_filename):
        """Assemble the final video from scene clips and audio."""
        if not video_files:
            logger.error("No video files provided for assembly.")
            return None

        # Create a temporary directory for intermediate files
        temp_dir = os.path.join(self.output_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Initialize list to track temporary files
        self.temp_files = []
        self.temp_files.append(temp_dir)  # Track the temp directory itself

        # Process each segment
        segment_files = []
        for i, (video_path, audio_path) in enumerate(zip(video_files, audio_files)):
            if not video_path:
                logger.warning(f"Skipping segment {i} due to missing video file.")
                continue

            segment_output_path = os.path.join(temp_dir, f"segment_{i}.mp4")
            
            if audio_path:
                # Combine video with new audio
                logger.info(f"Combining video {video_path} with audio {audio_path}")
                
                # Ensure audio and video are extended to match durations
                audio_duration = self.get_duration(audio_path)
                video_duration = self.get_duration(video_path)
                
                target_duration = max(audio_duration, video_duration)
                
                # Extend video if needed
                if video_duration < target_duration:
                    extended_video_path = os.path.join(temp_dir, f"extended_video_{i}.mp4")
                    self.extend_video_duration(video_path, target_duration, extended_video_path)
                    video_path = extended_video_path
                    self.temp_files.append(extended_video_path)  # Track extended video file
                
                # Combine with audio
                cmd = [
                    "ffmpeg",
                    "-i", video_path,
                    "-i", audio_path,
                    "-c:v", "libx264",
                    "-crf", "18",
                    "-preset", "medium",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest", # End when the shorter input ends
                    "-y",
                    segment_output_path
                ]
                
            else:
                # No new audio, just copy the video
                logger.info(f"No audio file for segment {i}, using original video")
                cmd = [
                    "ffmpeg",
                    "-i", video_path,
                    "-c:v", "libx264",
                    "-crf", "18",
                    "-preset", "medium",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-y",
                    segment_output_path
                ]

            try:
                subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                segment_files.append(segment_output_path)
                self.temp_files.append(segment_output_path)  # Track segment file
            except subprocess.CalledProcessError as e:
                logger.error(f"Error assembling video: {e}")
                # Fallback to moviepy for this segment
                try:
                    logger.info("Falling back to moviepy for segment assembly")
                    video_clip = VideoFileClip(video_path)
                    if audio_path:
                        audio_clip = AudioFileClip(audio_path)
                        video_clip = video_clip.set_audio(audio_clip)
                    
                    video_clip.write_videofile(segment_output_path, codec="libx264", audio_codec="aac")
                    segment_files.append(segment_output_path)
                except Exception as moviepy_e:
                    logger.error(f"Moviepy fallback also failed: {moviepy_e}")
                    return None

        if not segment_files:
            logger.error("No segments were successfully created.")
            return None

        # Concatenate all segments
        final_video_path = os.path.join(self.output_dir, output_filename)
        
        # Create a file list for ffmpeg
        file_list_path = os.path.join(temp_dir, "file_list.txt")
        with open(file_list_path, "w") as f:
            for segment in segment_files:
                f.write(f"file '{os.path.abspath(segment)}'\n")
        self.temp_files.append(file_list_path)  # Track the file list
    
        concat_cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", file_list_path,
            "-c", "copy",  # Copy both video and audio without re-encoding
            "-y",
            final_video_path
        ]
        
        try:
            subprocess.check_call(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(f"Final video assembled at {final_video_path}")
            return final_video_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Error concatenating video segments: {e}")
            # Fallback to moviepy for concatenation
            try:
                logger.info("Falling back to moviepy for concatenation")
                clips = [VideoFileClip(f) for f in segment_files]
                final_clip = concatenate_videoclips(clips)
                final_clip.write_videofile(final_video_path, codec="libx264", audio_codec="aac")
                return final_video_path
            except Exception as moviepy_e:
                logger.error(f"Moviepy concatenation fallback failed: {moviepy_e}")
                return None
        finally:
            # Clean up all tracked temporary files and directory
            try:
                # Clean up individual files first
                for temp_file in self.temp_files:
                    if temp_file != temp_dir and os.path.exists(temp_file):  # Don't remove directory yet
                        try:
                            os.remove(temp_file)
                        except Exception as e:
                            logger.warning(f"Could not remove temporary file {temp_file}: {e}")

                # Clean up the temp directory last
                if os.path.exists(temp_dir):
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")
            
            # Clear the temp files list
            self.temp_files = []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assemble video using ffmpeg with provided file lists")
    parser.add_argument("--videos", type=str, required=True,
                        help="Path to a text file containing video file paths (one per line)")
    parser.add_argument("--audio", type=str,
                        help="Path to a JSON file mapping indices to audio file paths")
    parser.add_argument("--output", type=str, default=None,
                        help="Output filename (optional)")
    parser.add_argument("--output_dir", type=str, default="final",
                        help="Output directory")

    args = parser.parse_args()

    # Read video file paths from the provided text file.
    with open(args.videos, "r") as vf:
        video_files = [line.strip() for line in vf if line.strip()]

    # If an audio file is provided, read the JSON mapping.
    audio_files = None
    if args.audio:
        if args.audio.endswith('.json'):
            with open(args.audio, 'r') as af:
                audio_files = json.load(af)
        else:
            # Backward compatibility: single audio file
            audio_files = {0: args.audio}

    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s - %(levelname)s - %(message)s")

    assembler = VideoAssembler(output_dir=args.output_dir)
    result = assembler.assemble_video(video_files=video_files, audio_files=audio_files, output_filename=args.output)
    if result:
        print(f"Video assembled successfully: {result}")
    else:
        print("Failed to assemble video.")