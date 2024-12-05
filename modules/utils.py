import os
import logging

from typing import Tuple, Optional
from datetime import datetime, timedelta
from moviepy.editor import AudioFileClip

from .decorators import log_errors

from config import (
    PROMPT_SENTIMENT,
    PROMPT_TRANSCRIPTION,
    BLACKLISTED_SONGS,
    PLAYED_SONGS_FILE
)

logger = logging.getLogger(__name__)

@log_errors
def load_prompts() -> Tuple[str, str]:
    """
    Loads sentiment and transcription prompts from their respective files.

    Parameters
    ----------
    None

    Returns
    -------
    Tuple[str, str]
        A tuple containing the sentiment prompt and the transcription prompt
        read from the corresponding files.

    Raises
    ------
    FileNotFoundError
        If either of the prompt files cannot be found.
    Exception
        If any other error occurs while loading the prompt files.
    """
    try:
        with open(PROMPT_TRANSCRIPTION, 'r', encoding='utf-8') as file:
            prompt_t = file.read()

        with open(PROMPT_SENTIMENT, 'r', encoding='utf-8') as file:
            prompt_s = file.read()
        
        return prompt_s, prompt_t
    except FileNotFoundError as e:
        logger.error(f"Prompt file not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading prompts: {e}")
        raise

@log_errors
def get_song_length(audio_file: str) -> Optional[timedelta]:
    """
    Calculates the length of a song from its audio file.

    Parameters
    ----------
    audio_file : str
        The path to the audio file.

    Returns
    -------
    Optional[timedelta]
        The duration of the song as a `timedelta` object, or `None` if an error occurs
        or the file is not provided.

    Raises
    ------
    Exception
        If an error occurs while reading the audio file or calculating its duration.
    """
    if not audio_file:
        logger.warning("No audio file provided")
        return None
        
    try:
        audio = AudioFileClip(audio_file)
        duration = timedelta(seconds=audio.duration)
        audio.close()
        logger.debug(f"Song duration: {duration}")
        return duration
    except Exception as e:
        logger.error(f"Error calculating duration for {audio_file}: {e}")
        return None

@log_errors
def parse_duration(duration_str: str) -> int:
    """
    Converts a time string in the format "HH:MM:SS" to the total number of seconds.

    Parameters
    ----------
    duration_str : str
        The duration string in the format "HH:MM:SS".

    Returns
    -------
    int
        The total number of seconds represented by the `duration_str`.

    Raises
    ------
    ValueError
        If the `duration_str` does not match the expected format "HH:MM:SS".
    """
    try:
        duration_obj = datetime.strptime(duration_str, "%H:%M:%S") - datetime.strptime("00:00:00", "%H:%M:%S")
        return int(duration_obj.total_seconds())
    except ValueError as e:
        logger.error(f"Invalid duration format: {e}")
        return 0

@log_errors
def handle_rejected_song(downloaded_song: Optional[str], basename: str, reason: str) -> None:
    """
    Removes a rejected song from the system and adds it to the blacklist.

    Parameters
    ----------
    downloaded_song : Optional[str]
        The path to the downloaded song file, or `None` if no file needs to be removed.
    basename : str
        The base name of the song (without the path) to be added to the blacklist.
    reason : str
        The reason why the song was rejected.

    Returns
    -------
    None

    Raises
    ------
    Exception
        If there is an error during the file removal or updating the blacklist.
    """
    if downloaded_song and os.path.exists(downloaded_song):
        try:
            os.remove(downloaded_song)
            logger.info(f"Removed rejected song file: {downloaded_song}")
        except Exception as e:
            logger.error(f"Error removing rejected song file: {e}")

    try:
        with open(BLACKLISTED_SONGS, 'a', encoding='utf-8') as f:
            f.write(f"{basename}\n")
        logger.info(f"Added {basename} to blacklist. Reason: {reason}")
    except Exception as e:
        logger.error(f"Error updating blacklist: {e}")

@log_errors
def ensure_directories_exist() -> None:
    """
    Ensures that required directories exist, creating them if necessary.

    Parameters
    ----------
    None

    Returns
    -------
    None

    Raises
    ------
    Exception
        If there is an error during the creation of directories.
    """
    directories = [
        os.path.dirname(BLACKLISTED_SONGS),
        os.path.dirname(PLAYED_SONGS_FILE),
        "logs",
        "audio",
        "audio_temp",
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Created directory: {directory}")