import os
import time
import logging

from typing import Optional, Tuple
from pytubefix import YouTube, extract

from .decorators import handle_exceptions

from config import (AUDIO_FOLDER_TEMP_PATH, 
                    AUDIO_FOLDER_PATH)

logger = logging.getLogger(__name__)

class YoutubeDownloader:

    def __init__(self):
        """
        A class responsible for downloading songs from YouTube and caching them locally.

        Attributes
        ----------
        download_path : str
            The path where the downloaded songs are temporarily stored.
        cache_path : str
            The path where previously downloaded songs are cached.
        """
        self.download_path = AUDIO_FOLDER_TEMP_PATH
        self.cache_path = AUDIO_FOLDER_PATH
        
        # Create directories if they don't exist
        os.makedirs(self.download_path, exist_ok=True)
        os.makedirs(self.cache_path, exist_ok=True)
    
    @handle_exceptions
    def download_song(self, url: str) -> Optional[Tuple[str, bool]]:
        """
        Downloads a song from the provided YouTube URL. First checks the cache for an 
        existing file and downloads the song only if it is not found in the cache.

        Parameters
        ----------
        url : str
            The YouTube URL of the song to be downloaded.

        Returns
        -------
        Optional[Tuple[str, bool]]
            A tuple containing the path to the downloaded song and a boolean indicating 
            whether the file was found in the cache (True) or downloaded (False).
            Returns `None` if the download fails or the song cannot be found in the cache.

        Raises
        ------
        Exception
            If any error occurs during the download process or cache check.
        """
        video_id = extract.video_id(url)
        
        # Check cache first
        cached_file = self._check_cache(video_id)
        if cached_file:
            logger.info(f"Found cached file: {cached_file}")
            return cached_file, True
            
        # Download if not cached
        return self._perform_download(url, video_id)
        
    def _check_cache(self, video_id: str) -> Optional[str]:
        """
        Checks the cache directory for an existing file corresponding to the provided
        video ID.

        Parameters
        ----------
        video_id : str
            The unique ID of the YouTube video.

        Returns
        -------
        Optional[str]
            The path to the cached file if it exists, or `None` if no cached file is found.
        """
        for filename in os.listdir(self.cache_path):
            if video_id in filename:
                return os.path.join(self.cache_path, filename)
        return None
        
    def _perform_download(self, url: str, video_id: str) -> Optional[Tuple[str, bool]]:
        """
        Downloads the song from the YouTube URL if it is not found in the cache.

        Parameters
        ----------
        url : str
            The YouTube URL of the song to be downloaded.
        video_id : str
            The unique ID of the YouTube video.

        Returns
        -------
        Optional[Tuple[str, bool]]
            A tuple containing the path to the downloaded song and a boolean indicating 
            whether the file was downloaded or not.
            Returns `None` if the download fails.

        Raises
        ------
        Exception
            If there is an error during the download process.
        """
        try:
            video = YouTube(url)
            stream = self._get_best_audio_stream(video)
            if not stream:
                logger.error("No suitable audio stream found")
                return None
                
            filename = f"{video_id}{self._get_extension(stream)}"
            output_path = os.path.join(self.download_path, filename)
            
            logger.info(f"Downloading {url} to {output_path}")
            stream.download(output_path=self.download_path, filename=filename)
            time.sleep(3)  # Wait for file to be ready
            
            return output_path, False
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None
            
    @staticmethod
    def _get_best_audio_stream(video: YouTube):
        """
        Finds the best available audio stream for the YouTube video.

        Parameters
        ----------
        video : YouTube
            The `YouTube` object representing the video from which to extract audio.

        Returns
        -------
        stream
            The best available audio stream for the video, or `None` if no suitable stream 
            is found.
        """
        for mime_type in ["audio/webm", "audio/mp3"]:
            stream = video.streams.filter(mime_type=mime_type).first()
            if stream:
                return stream
        return None
        
    @staticmethod
    def _get_extension(stream) -> str:
        """
        Determines the file extension based on the MIME type of the audio stream.

        Parameters
        ----------
        stream
            The audio stream from which to determine the file extension.

        Returns
        -------
        str
            The appropriate file extension (either ".webm" or ".mp3").
        """
        return ".webm" if stream.mime_type == "audio/webm" else ".mp3"