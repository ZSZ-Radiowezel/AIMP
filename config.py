
"""
Configuration settings for the application.

This file contains all necessary constants and paths used throughout the application.
It includes API keys, URLs for backend services, paths to important directories and files,
audio device settings, and scheduling times.

### API Keys:
- GEMINI_API_KEY: The API key used to authenticate requests to the Gemini API for sentiment and transcription analysis.
- GEMINI_MODEL: The model name to use with the Gemini API.

### URLs:
- URL_BACKEND: The backend server URL, typically used to handle requests and serve data.
- URL_ADMINPAGE: The URL for the admin page that allows administrative control over the system.

### File Paths:
- BASE_DIR: The base directory of the project.
- AUDIO_FOLDER_PATH: Path to the main audio folder where audio files are stored.
- AUDIO_FOLDER_TEMP_PATH: Path to a temporary audio folder for processing files before final storage.
- AIMP_PLAYLIST_PATH: Path to the AIMP playlist folder.
- PLAYED_SONGS_FILE: Path to the file that logs played songs.
- BLACKLISTED_SONGS: Path to the file containing blacklisted song titles.
- PROMPT_SENTIMENT: Path to the sentiment analysis prompt file.
- PROMPT_TRANSCRIPTION: Path to the transcription prompt file.
- PRIORITY_PLAYLISTS_DIR: Directory for priority playlists, likely for higher priority songs.

### Audio Device Settings:
- AUDIO_DEVICE_NAME: The name of the audio device used in one location.
- MAIN_AUDIO_DEVICE_NAME: The name of the audio device used in the primary location.
- AIMP_VOLUME_INCREMENT: The amount by which to increment the volume.
- AIMP_MAX_VOLUME: The maximum volume value allowed by the AIMP audio player.

### Schedule Times:
- PLAYLIST_UPDATE_TIMES: A list of times when the playlist should be updated throughout the day.
- DEVICE_START_TIMES: A list of times when the audio devices should start playing.
- DEVICE_STOP_TIMES: A list of times when the audio devices should stop playing.
"""
import os

# API Keys
GEMINI_API_KEY = ""
GEMINI_MODEL = "gemini-1.5-flash"

# URLs
URL_BACKEND = "http://127.0.0.1"
URL_ADMINPAGE = "http://127.0.0.1"

# File Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_FOLDER_PATH = os.path.join(BASE_DIR, "audio")
AUDIO_FOLDER_TEMP_PATH = r"E:\AIMP_20_11_2024\aimp_cursor\audio_temp"
AIMP_PLAYLIST_PATH = os.path.join(os.environ['USERPROFILE'], 'AppData', 'Roaming', 'AIMP', 'PLS')
PLAYED_SONGS_FILE = os.path.join(BASE_DIR, "played_songs.txt")
BLACKLISTED_SONGS = os.path.join(BASE_DIR, "blacklisted_songs.txt")
PROMPT_SENTIMENT = os.path.join(BASE_DIR, "prompts", "sentiment_prompt.txt")
PROMPT_TRANSCRIPTION = os.path.join(BASE_DIR, "prompts", "transcription_prompt.txt")
SPECIAL_PLAYLISTS_PATH = os.path.join(BASE_DIR, "special_playlists")

# Audio Device Settings
AUDIO_DEVICE_NAME = "HDTV" # korytarz "Miks Stereo"
MAIN_AUDIO_DEVICE_NAME = "HDTV" # Świetlica
AIMP_VOLUME_INCREMENT = 750
AIMP_MAX_VOLUME = 65535

# Schedule Times
PLAYLIST_UPDATE_TIMES = ["07:45","08:40", "09:35", "10:30", "11:25", "12:25", "13:20", "14:15","15:10", "13:45"]
DEVICE_START_TIMES = ["07:51","08:46", "09:41", "10:36", "11:31", "12:31", "13:26", "14:21","15:16","21:37"]
DEVICE_STOP_TIMES = ["07:59", "08:54", "09:49", "10:44", "11:44", "12:39", "13:34", "14:29","15:24","21:39"]

SCHOOL_BELLS_START = ["07:50","08:45", "09:40", "10:35", "11:30", "12:30", "13:25", "14:20","15:15"]
SCHOOL_BELLS_END = ["08:00", "08:55", "09:50", "10:45", "11:45", "12:40", "13:35", "14:30"]
