import os
import time
import logging

from typing import Optional, Tuple
from pytubefix import YouTube, extract, Playlist

from .decorators import handle_exceptions
from .utils import standardize_name

from config import (AUDIO_FOLDER_TEMP_PATH, 
                    AUDIO_FOLDER_PATH,
                    SPECIAL_PLAYLISTS_PATH)

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
    
    def download_song(self, url: str, path=AUDIO_FOLDER_TEMP_PATH, name=None) -> Optional[Tuple[str, bool]]:
        """
        Downloads a song from the provided YouTube URL. First checks the cache for an 
        existing file and downloads the song only if it is not found in the cache.

        Parameters
        ----------
        url : str
            The YouTube URL of the song to be downloaded.
        
        path : str
            Path where the song will be saved.

        name : str, optional
            The name to be used for the downloaded song file. If not provided, the video ID will be used.

        Returns
        -------
        Optional[Tuple[str, bool]]
            A tuple containing the path to the downloaded song and a boolean indicating 
            whether the file was found in the cache (True) or downloaded (False).
            Returns `None` if the download fails or the song cannot be found in the cache.
        """
        video_id = extract.video_id(url)

        if name: 
            video_id = name  # Ensure `video_id` is replaced with `name` if provided
        
        cached_file = self._check_cache(video_id, path)
        if cached_file:
            logger.info(f"Found cached file: {cached_file}")
            return cached_file, True

        return self._perform_download(url, video_id, path)

    def _perform_download(self, url: str, video_id: str, output_path: str) -> Optional[Tuple[str, bool]]:
        """
        Downloads the song from the YouTube URL if it is not found in the cache.

        Parameters
        ----------
        url : str
            The YouTube URL of the song to be downloaded.
        video_id : str
            The unique ID of the YouTube video.
        output_path: str
            Path where song will be saved.

        Returns
        -------
        Optional[Tuple[str, bool]]
            A tuple containing the path to the downloaded song and a boolean indicating 
            whether the file was downloaded or not.
            Returns `None` if the download fails.
        """
        try:
            video = YouTube(url)
            stream = self._get_best_audio_stream(video)
            if not stream:
                logger.error("No suitable audio stream found")
                return None
                    
            filename = f"{video_id}{self._get_extension(stream)}"
            full_output_path = os.path.join(output_path, filename)  # Combine path and filename here

            logger.info(f"Downloading {url} to {full_output_path}")
            stream.download(output_path=output_path, filename=filename)
            time.sleep(3)  # Wait for file to be ready
                
            return full_output_path, False
                
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None

        
    def _check_cache(self, video_id: str, path=AUDIO_FOLDER_PATH) -> Optional[str]:
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
        for filename in os.listdir(path):
            if video_id in filename:
                return os.path.join(path, filename)
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
    
    @handle_exceptions
    def _get_playlist(self, url):
        playlist = Playlist(url)
        logger.info(f"Found playlist: {url}")
        return playlist.video_urls
    
    def download_playlist(self, url: str, path: str):
        try:
            playlist = self._get_playlist(url)
            
            playlist_path = os.path.join(SPECIAL_PLAYLISTS_PATH, path)
            os.makedirs(playlist_path, exist_ok=True) 
            
            for video in playlist:
                sanitized_title = standardize_name(YouTube(video).title)
                self.download_song(
                    url=video,
                    path=playlist_path,
                    name=sanitized_title
                )
            logger.info(f"Downloaded all songs from playlist: {url}")
            return True
        except Exception as e:
            logger.info(f"Error when downloading songs from playlist: {url} \n {e}")
