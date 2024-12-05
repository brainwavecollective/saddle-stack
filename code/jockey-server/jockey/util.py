import os
import uuid
import sys
import json
import requests
import urllib
import ffmpeg
from typing import TYPE_CHECKING, Any, Dict, List
from rich.padding import Padding
from rich.console import Console
from rich.json import JSON
import tempfile
import subprocess
import traceback
import logging

import httpx
httpx.Client(transport=httpx.HTTPTransport(local_address="0.0.0.0"))
logging.getLogger("httpx").setLevel(logging.DEBUG)

TL_BASE_URL = "https://api.twelvelabs.io/v1.2/"
INDEX_URL = urllib.parse.urljoin(TL_BASE_URL, "indexes/")
REQUIRED_ENVIRONMENT_VARIABLES = set([
    "TWELVE_LABS_API_KEY",
    "HOST_PUBLIC_DIR",
    "LLM_PROVIDER"
])
AZURE_ENVIRONMENT_VARIABLES = set([
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "OPENAI_API_VERSION"
])
OPENAI_ENVIRONMENT_VARIABLES = set([
    "OPENAI_API_KEY"
])
ALL_JOCKEY_ENVIRONMENT_VARIABLES = REQUIRED_ENVIRONMENT_VARIABLES | AZURE_ENVIRONMENT_VARIABLES | OPENAI_ENVIRONMENT_VARIABLES
       
logger = logging.getLogger("jockey_util")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

def parse_langchain_events_terminal(event: dict):
    """Used to parse events emitted from Jockey when called as an API."""
    console = Console()

    if event["event"] == "on_chat_model_stream":
        if isinstance(event["data"]["chunk"], dict):
            content = event["data"]["chunk"]["content"]
        else:
            content = event["data"]["chunk"].content
        
        if content and "instructor" in event["tags"]:
            console.print(f"[red]{content}", end="")
        elif content and "planner" in event["tags"]:
            console.print(f"[yellow]{content}", end="")
        elif content and "supervisor" in event["tags"]:
            console.print(f"[white]{content}", end="")
    elif event["event"] == "on_tool_start":
        tool = event["name"]
        console.print(Padding(f"[cyan]🏇 Using: {tool}", (1, 0, 0, 2)))
        console.print(Padding(f"[cyan]🏇 Inputs:", (0, 2)))
        console.print(Padding(JSON(json.dumps(event["data"]["input"]), indent=2), (1, 6)))
    elif event["event"] == "on_tool_end":
        tool = event["name"]
        console.print(Padding(f"[cyan]🏇 Finished Using: {tool}", (0, 2)))
        console.print(Padding(f"[cyan]🏇 Outputs:", (0, 2)))
        try:
            console.print(Padding(JSON(event["data"]["output"], indent=2), (1, 6)))
        except (json.decoder.JSONDecodeError, TypeError):
            console.print(Padding(str(event["data"]["output"]), (0, 6)))
    elif event["event"] == "on_chat_model_start":
        if "instructor" in event["tags"]:
            console.print(Padding(f"[red]🏇 Instructor: ", (1, 0)), end="")
        elif "planner" in event["tags"]:
            console.print(Padding(f"[yellow]🏇 Planner: ", (1, 0)), end="")
        elif "reflect" in event["tags"]:
            console.print()
            console.print(f"[cyan]🏇 Jockey: ", end="")


def get_video_metadata(index_id: str, video_id: str) -> dict:
    video_url = f"{INDEX_URL}{index_id}/videos/{video_id}"

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "x-api-key": os.environ["TWELVE_LABS_API_KEY"]
    }

    response = requests.get(video_url, headers=headers)

    try:
        assert response.status_code == 200
    except AssertionError:
        error_response = {
                "message": f"There was an error getting the metadata for Video ID: {video_id} in Index ID: {index_id}. "
                "Double check that the Video ID and Index ID are valid and correct.",
                "error": response.text
            }
        return error_response

    return response
    
def download_video(video_id: str, index_id: str, start: float, end: float) -> str:
    """Download a video for a given video in a given index and get the filepath.
    Should only be used when the user explicitly requests video editing functionalities."""
    try:
        headers = {
            "x-api-key": os.environ["TWELVE_LABS_API_KEY"],
            "accept": "application/json",
            "Content-Type": "application/json"
        }

        video_url = f"https://api.twelvelabs.io/v1.2/indexes/{index_id}/videos/{video_id}"

        response = requests.get(video_url, headers=headers)
        if response.status_code != 200:
            logger.error("Failed to get video URL", extra={
                "video_id": video_id,
                "index_id": index_id,
                "status_code": response.status_code,
                "response_body": response.text
            })
            return {
                "message": f"Failed to get video URL. Status code: {response.status_code}",
                "error": response.text
            }

        hls_uri = response.json()["hls"]["video_url"]
        
        # Enhanced URL validation with redirect handling
        url_response = requests.head(hls_uri, timeout=5, allow_redirects=True)
        logger.info("HLS URI check results", extra={
            "status_code": url_response.status_code,
            "headers": dict(url_response.headers),
            "history": [r.status_code for r in url_response.history],
            "final_url": url_response.url,
            "content_type": url_response.headers.get("content-type")
        })

        # Directory handling
        video_dir = os.path.join(os.environ["HOST_PUBLIC_DIR"], index_id)
        if not os.path.isdir(video_dir):
            os.makedirs(video_dir, exist_ok=True)
            logger.info("Directory created successfully", extra={
                "video_dir": video_dir,
                "permissions": oct(os.stat(video_dir).st_mode)[-3:]
            })

        video_filename = f"{video_id}_{start}_{end}.mp4"
        video_path = os.path.join(video_dir, video_filename)

        if not os.path.isfile(video_path):
            try:
                duration = end - start
                buffer = 1  # Add a 1-second buffer on each side
                
                # Initial download with buffer
                logger.info("Starting FFmpeg download", extra={
                    "start": start,
                    "end": end,
                    "duration": duration,
                    "buffer": buffer
                })
                
                (ffmpeg
                    .input(hls_uri, ss=max(0, start-buffer), t=duration+2*buffer, strict="experimental")
                    .output(video_path, 
                           vcodec="libx264",
                           acodec="aac",
                           avoid_negative_ts="make_zero",
                           fflags="+genpts")
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True))

                logger.info("Initial download complete", extra={
                    "file_path": video_path,
                    "file_size": os.path.getsize(video_path)
                })

                # Precise trimming
                output_trimmed = f"{os.path.splitext(video_path)[0]}_trimmed.mp4"
                (ffmpeg
                    .input(video_path, ss=buffer, t=duration)
                    .output(output_trimmed,
                           vcodec="copy",
                           acodec="copy")
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True))

                # Replace original with trimmed version
                os.replace(output_trimmed, video_path)
                
                logger.info("Video processing completed successfully", extra={
                    "final_path": video_path,
                    "final_size": os.path.getsize(video_path)
                })

            except ffmpeg.Error as e:
                stderr = e.stderr.decode() if e.stderr else "No stderr"
                stdout = e.stdout.decode() if e.stdout else "No stdout"
                logger.error("FFmpeg processing failed", extra={
                    "error": str(e),
                    "stderr": stderr,
                    "stdout": stdout,
                    "video_path": video_path
                })
                return {
                    "message": "FFmpeg processing failed",
                    "error": stderr
                }

        return video_path

    except Exception as error:
        logger.exception("Unexpected error in download_video", extra={
            "video_id": video_id,
            "index_id": index_id,
            "error_type": type(error).__name__,
            "error_str": str(error)
        })
        return {
            "message": "Unexpected error in download_video",
            "error": str(error)
        }

def check_environment_variables():
    """Check that a .env file contains the required environment variables.
    Uses the current working directory tree to search for a .env file."""
    # Assume the .env file is someone on the current working directory tree.
    # load_dotenv(find_dotenv(usecwd=True))

    if REQUIRED_ENVIRONMENT_VARIABLES & os.environ.keys() != REQUIRED_ENVIRONMENT_VARIABLES:
        missing_environment_variables = REQUIRED_ENVIRONMENT_VARIABLES - os.environ.keys()
        print(f"Expected the following environment variables:\n\t{str.join(', ', REQUIRED_ENVIRONMENT_VARIABLES)}")
        print(f"Missing:\n\t{str.join(', ', missing_environment_variables)}")
        sys.exit("Missing required environment variables.")

    if AZURE_ENVIRONMENT_VARIABLES & os.environ.keys() != AZURE_ENVIRONMENT_VARIABLES and \
        OPENAI_ENVIRONMENT_VARIABLES & os.environ.keys() != OPENAI_ENVIRONMENT_VARIABLES:
        missing_azure_environment_variables = AZURE_ENVIRONMENT_VARIABLES - os.environ.keys()
        missing_openai_environment_variables = OPENAI_ENVIRONMENT_VARIABLES - os.environ.keys()
        print(f"If using Azure, Expected the following environment variables:\n\t{str.join(', ', AZURE_ENVIRONMENT_VARIABLES)}")
        print(f"Missing:\n\t{str.join(', ', missing_azure_environment_variables)}")

        print(f"If using Open AI, Expected the following environment variables:\n\t{str.join(', ', OPENAI_ENVIRONMENT_VARIABLES)}")
        print(f"Missing:\n\t{str.join(', ', missing_openai_environment_variables)}")
        sys.exit("Missing Azure or Open AI environment variables.")

