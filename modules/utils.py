import os
import logging
import re

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
        "special_playlists"
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Created directory: {directory}")

def sanitize_name(name):
    """
    Sanitizes a file or directory name for Windows. Replaces spaces with underscores,
    removes trailing dots and spaces, and validates against forbidden characters and reserved names.
    
    Args:
        name (str): The original name.
    
    Returns:
        str: The sanitized name.
    
    Raises:
        ValueError: If the name contains forbidden characters, is reserved, or exceeds path length limits.
    """
    name= str(name)
    sanitized_name = name.replace(' ', '_')
    invalid_chars = r'[<>:"/\\|?*]'
    if re.search(invalid_chars, sanitized_name):
        logging.error(f"Forbidden characters found in name: {name}")
        return [False,f"Zawiera niedozwolone znaki"]
    
    sanitized_name = sanitized_name.rstrip('. ')
    if is_reserved_name(sanitized_name)[0]:
        logging.error(f"Name is reserved: {sanitized_name}")
        return [False,f"Zawiera fragment zarezerwowany dla systemu windows: {is_reserved_name(sanitized_name[1])}"]
    
    if not is_valid_path_length(sanitized_name):
        logging.error(f"Path exceeds the maximum length: {sanitized_name}")
        return [False, f"Zbyt długa nazwa: {sanitized_name}"]
    
    logging.info(f"Sanitized name successfully: {sanitized_name}")
    return [True, sanitized_name]

def is_reserved_name(name):
    """
    Checks if the given name is reserved in Windows and identifies the reserved fragment if applicable.
    
    Args:
        name (str): The name to check.
    
    Returns:
        tuple: A tuple containing a boolean indicating if the name is reserved and the reserved fragment (or None).
    """
    reserved_names = {
        "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", 
        "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", 
        "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
    }
    base_name = name.split('.')[0].upper()
    if base_name in reserved_names:
        return [True, base_name]
    return [False, None]

def is_valid_path_length(path, max_length=260):
    """
    Checks if the absolute path length is within the allowed limit for Windows.
    
    Args:
        path (str): The path to check.
        max_length (int): The maximum allowed length (default: 260).
    
    Returns:
        bool: True if the path length is valid, False otherwise.
    """
    return len(os.path.abspath(path)) <= max_length

import re

def standardize_name(name: str) -> str:
    """
    The function removes all characters that are not allowed in file names.
    It also removes initial and final spaces and replaces spaces with underscores.
    
    Parameters
    ----------
    name : str
        The name we want to convert.
        
    Returns
    -------
    str
        Normalized name.
    """
    forbidden_chars = r'[<>:"/\\|?*]' 
    
    name = re.sub(forbidden_chars, '', name)
    name = name.replace(" ", "_")
    name = name.strip()
    
    return name
