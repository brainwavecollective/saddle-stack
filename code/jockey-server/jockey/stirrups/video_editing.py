import os
import ffmpeg
import subprocess
from langchain.tools import tool
from langchain.pydantic_v1 import BaseModel, Field
from typing import List, Dict, Union
from jockey.util import download_video
from jockey.prompts import DEFAULT_VIDEO_EDITING_FILE_PATH
from jockey.stirrups.stirrup import Stirrup


# For Debugging
import logging
logger = logging.getLogger("langgraph_api.graph")
def get_file_info(path):
    """Get detailed file/directory information"""
    try:
        stat = os.stat(path)
        owner = pwd.getpwuid(stat.st_uid).pw_name
        group = grp.getgrgid(stat.st_gid).gr_name
        perms = oct(stat.st_mode)[-3:]
        modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
        return {
            "exists": True,
            "owner": owner,
            "group": group,
            "permissions": perms,
            "size": stat.st_size,
            "last_modified": modified,
            "uid": stat.st_uid,
            "gid": stat.st_gid,
            "mode": oct(stat.st_mode)
        }
    except (FileNotFoundError, KeyError):
        return {
            "exists": False,
            "error": "Path does not exist"
        }


class Clip(BaseModel):
    """Define what constitutes a clip in the context of the video-editing worker."""
    index_id: str = Field(description="A UUID for the index a video belongs to. This is different from the video_id.")
    video_id: str = Field(description="A UUID for the video a clip belongs to.")
    start: float = Field(description="The start time of the clip in seconds.")
    end: float = Field(description="The end time of the clip in seconds.")


class CombineClipsInput(BaseModel):
    """Helps to ensure the video-editing worker providers all required information for clips when using the `combine_clips` tool."""
    clips: List[Clip] = Field(description="List of clips to be edited together. Each clip must have start and end times and a Video ID.")
    output_filename: str = Field(description="The output filename of the combined clips. Must be in the form: [filename].mp4")
    index_id: str = Field(description="Index ID the clips belong to.")


class RemoveSegmentInput(BaseModel):
    """Helps to ensure the video-editing worker providers all required information for clips when using the `remove_segment` tool."""
    video_filepath: str = Field(description="Full path to target video file.")
    start: float = Field(description="""Start time of segment to be removed. Must be in the format of: seconds.milliseconds""")
    end: float = Field(description="""End time of segment to be removed. Must be in the format of: seconds.milliseconds""")

@tool("combine-clips", args_schema=CombineClipsInput)
def combine_clips(clips: List[Dict], output_filename: str, index_id: str) -> Union[str, Dict]:
    """Combine or edit multiple clips together based on their start and end times and video IDs."""
    try:
        input_streams = []
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.join(os.environ["HOST_PUBLIC_DIR"], index_id), exist_ok=True)

        for clip in clips:
            video_filepath = os.path.join(os.environ["HOST_PUBLIC_DIR"], index_id, f"{clip.video_id}_{clip.start}_{clip.end}.mp4")

            if not os.path.isfile(video_filepath):
                result = download_video(video_id=clip.video_id, index_id=index_id, start=clip.start, end=clip.end)
                if isinstance(result, dict) and "error" in result:
                    return result

            # Ensure file exists after download attempt
            if not os.path.isfile(video_filepath):
                output_dir = os.path.dirname(video_filepath)
                host_public_dir = os.environ.get("HOST_PUBLIC_DIR", "not_set")
                
                # Get current process user info
                try:
                    current_user = pwd.getpwuid(os.getuid())
                    user_info = {
                        "name": current_user.pw_name,
                        "uid": current_user.pw_uid,
                        "gid": current_user.pw_gid,
                        "home": current_user.pw_dir,
                        "groups": [g.gr_name for g in grp.getgrall() if current_user.pw_name in g.gr_mem]
                    }
                except Exception as e:
                    user_info = {"user info error": str(e)}

                logger.error("Video file missing after download attempt", extra={
                    "api_revision": "f3f1d77",
                    "api_variant": "local",
                    "debug_info": {
                        "file_path": video_filepath,
                        "directory_path": output_dir,
                        "process_info": {
                            "current_user": user_info,
                            "cwd": os.getcwd(),
                            "pid": os.getpid(),
                            "environment": {
                                "HOST_PUBLIC_DIR": host_public_dir,
                                "PWD": os.environ.get("PWD", "not_set"),
                                "HOME": os.environ.get("HOME", "not_set"),
                                "USER": os.environ.get("USER", "not_set")
                            }
                        },
                        "host_public_dir_info": get_file_info(host_public_dir),
                        "target_dir_info": get_file_info(output_dir),
                        "directory_contents": {
                            "host_public_dir": os.listdir(host_public_dir) if os.path.exists(host_public_dir) else "directory_missing",
                            "target_dir": os.listdir(output_dir) if os.path.exists(output_dir) else "directory_missing"
                        },
                        "clip_info": {
                            "video_id": clip.video_id,
                            "index_id": index_id,
                            "start": clip.start,
                            "end": clip.end
                        }
                    }
                })
                
                return {
                    "message": "Video file missing after download",
                    "error": f"Could not locate video file: {video_filepath}"
                }
                

            try:
                input_stream = ffmpeg.input(filename=video_filepath, loglevel="error")
                input_streams.extend([
                    input_stream.video.filter("setpts", "PTS-STARTPTS"),
                    input_stream.audio.filter("asetpts", "PTS-STARTPTS")
                ])
            except Exception as e:
                return {
                    "message": "FFmpeg stream creation error",
                    "error": str(e),
                    "filepath": video_filepath
                }

        # Ensure output filename has .mp4 extension
        if not output_filename.endswith('.mp4'):
            output_filename += '.mp4'
            
        output_filepath = os.path.join(os.environ["HOST_PUBLIC_DIR"], index_id, output_filename)
        
        try:
            ffmpeg.concat(*input_streams, v=1, a=1).output(
                output_filepath, 
                vcodec="libx264",   
                acodec="libmp3lame", 
                video_bitrate="1M",
                audio_bitrate="192k"
            ).overwrite_output().run(capture_stdout=True, capture_stderr=True)
            
            return output_filepath

        except subprocess.CalledProcessError as e:
            return {
                "message": "FFmpeg processing error",
                "error": f"FFmpeg error: {str(e)}\n"
                    f"stdout: {e.stdout.decode('utf-8') if e.stdout else 'No stdout'}\n"
                    f"stderr: {e.stderr.decode('utf-8') if e.stderr else 'No stderr'}"
            }

    except Exception as error:
        return {
            "message": "Unexpected video editing error",
            "error": str(error)
        }


@tool("remove-segment", args_schema=RemoveSegmentInput)
def remove_segment(video_filepath: str, start: float, end: float) -> Union[str, Dict]:
    """Remove a segment from a video at specified start and end times."""
    try:
        output_filepath = f"{os.path.splitext(video_filepath)[0]}_clipped.mp4"
        
        if not os.path.isfile(video_filepath):
            return {
                "message": "Input video file not found",
                "error": f"Could not locate video file: {video_filepath}"
            }

        try:
            # Create streams for before and after the segment to remove
            left_cut = ffmpeg.input(filename=video_filepath, loglevel="quiet")
            right_cut = ffmpeg.input(filename=video_filepath, loglevel="quiet")
            
            streams = [
                left_cut.video.filter("trim", start=0, end=start).filter("setpts", "PTS-STARTPTS"),
                left_cut.audio.filter("atrim", start=0, end=start).filter("asetpts", "PTS-STARTPTS"),
                right_cut.video.filter("trim", start=end).filter("setpts", "PTS-STARTPTS"),
                right_cut.audio.filter("atrim", start=end).filter("asetpts", "PTS-STARTPTS")
            ]

            ffmpeg.concat(*streams, v=1, a=1).output(
                filename=output_filepath, 
                acodec="libmp3lame"
            ).overwrite_output().run(capture_stdout=True, capture_stderr=True)
            
            return output_filepath

        except subprocess.CalledProcessError as e:
            return {
                "message": "FFmpeg processing error",
                "error": f"FFmpeg error: {str(e)}\n"
                    f"stdout: {e.stdout.decode('utf-8') if e.stdout else 'No stdout'}\n"
                    f"stderr: {e.stderr.decode('utf-8') if e.stderr else 'No stderr'}"
            }

    except Exception as error:
        return {
            "message": "Unexpected video editing error",
            "error": str(error)
        }


# Construct a valid worker for a Jockey instance.
video_editing_worker_config = {
    "tools": [combine_clips, remove_segment],
    "worker_prompt_file_path": DEFAULT_VIDEO_EDITING_FILE_PATH,
    "worker_name": "video-editing"
}
VideoEditingWorker = Stirrup(**video_editing_worker_config)