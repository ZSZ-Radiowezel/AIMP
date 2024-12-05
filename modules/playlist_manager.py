import os
import shutil
import logging

from time import sleep
from random import choice
from typing import List, Optional
from datetime import timedelta, datetime
from moviepy.editor import AudioFileClip

from .decorators import handle_exceptions
from .decorators import log_errors, handle_exceptions
from .exceptions import PlaylistUpdateError

from config import (
    AUDIO_FOLDER_PATH,
    AUDIO_FOLDER_TEMP_PATH,
    BLACKLISTED_SONGS,
    PLAYED_SONGS_FILE,
    BASE_DIR
)

logger = logging.getLogger(__name__)

class PlaylistManager:

    def __init__(self, aimp_controller, youtube_downloader, text_analyzer, 
                 transcript_api, sentiment_api, request_manager):
        
        """
        A class that manages playlist updates, song processing, and local playlist management.

        Attributes:
        aimp_controller (AimpController): The controller for managing AIMP player.
        youtube_downloader (YouTubeDownloader): The downloader for YouTube songs.
        text_analyzer (TextAnalyzer): The analyzer for song lyrics.
        transcript_api (TranscriptAPI): The API for generating song lyrics.
        sentiment_api (SentimentAPI): The API for sentiment analysis of song lyrics.
        request_manager (RequestManager): The manager for handling requests to the backend.
        """
        self.aimp_controller = aimp_controller
        self.youtube_downloader = youtube_downloader
        self.text_analyzer = text_analyzer
        self.transcript_api = transcript_api
        self.sentiment_api = sentiment_api
        self.request_manager = request_manager

    def _clear_temp_folder(self):
        """
        Clears the temporary folder used for song downloads.

        This method removes all files from the temporary folder defined in the 
        AUDIO_FOLDER_TEMP_PATH configuration.
        """
        if os.path.exists(AUDIO_FOLDER_TEMP_PATH):
            for file in os.listdir(AUDIO_FOLDER_TEMP_PATH):
                file_path = os.path.join(AUDIO_FOLDER_TEMP_PATH, file)
                self._remove_file(file_path)

    def _remove_file(self, file_path):
        """
        Removes a file from the filesystem.

        Parameters
        ----------
        file_path : str
            The full path to the file to be removed.
        """
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Error removing temp file {os.path.basename(file_path)}: {e}")

    @log_errors
    def update_playlist(self):
        """
        Updates the playlist by processing the songs fetched from the backend.

        This method prepares for the playlist update, processes the songs 
        from the backend, checks for existing songs in the audio folder, 
        and ensures the total playlist duration meets the required length.

        It also processes local songs to ensure the playlist duration 
        reaches the target.
        """
        try:
            self.aimp_controller.prepare_for_update()
            self._clear_temp_folder()
            
            playlist_data = self.request_manager.fetch_songs_from_backend()
            total_duration = timedelta()
            
            if playlist_data:
                for song in playlist_data:
                    if self._process_song(song['url']):
                        song_path = os.path.join(AUDIO_FOLDER_PATH, f"{self._extract_video_id(song['url'])}.webm")
                        if os.path.exists(song_path):
                            duration = self._get_song_duration(song_path)
                            if duration:
                                total_duration += duration
                                logger.debug(f"Added duration for existing song: {os.path.basename(song_path)} ({duration})")
            
            logger.info(f"Duration after processing backend songs: {total_duration}")
            total_duration = self._add_local_songs_until_duration(total_duration, timedelta(minutes=55))
            logger.info(f"Final playlist duration: {total_duration}")
            
        except Exception as e:
            logger.error(f"Error updating playlist: {e}")

    def _add_local_songs_until_duration(self, current_duration, target_duration):
        """
        Adds local songs to the playlist until the total duration reaches the target.

        Parameters
        ----------
        current_duration : timedelta
            The current duration of the playlist.
        target_duration : timedelta
            The target duration that the playlist should reach.

        Returns
        -------
        timedelta
            The updated total duration after adding local songs.
        """
        logger.debug(f"Starting _add_local_songs_until_duration with current_duration: {current_duration}, target: {target_duration}")
        
        while current_duration < target_duration:
            song_path = self._get_random_local_song()
            if not song_path:
                logger.warning("No more songs available to add")
                break
            
            duration = self._get_song_duration(song_path)
            if duration:
                current_duration += duration
                logger.info(f"Added local song {os.path.basename(song_path)} to playlist (duration: {duration})")
                logger.debug(f"Current total duration: {current_duration}")
            else:
                logger.warning(f"Could not get duration for {os.path.basename(song_path)}")
        
        return current_duration

    @log_errors
    def _process_song(self, url: str) -> bool:
        """
        Processes a song from a given URL.

        The method downloads the song, extracts its lyrics, performs 
        text analysis, and sentiment analysis, and adds it to the playlist 
        if the song is deemed acceptable.

        Parameters
        ----------
        url : str
            The URL of the song to be processed.

        Returns
        -------
        bool
            True if the song was successfully processed and added to the playlist, 
            False otherwise.
        """
        try:
            video_id = self._extract_video_id(url)
            if self._is_blacklisted(video_id):
                return False

            download_result = self.youtube_downloader.download_song(url)
            if not download_result:
                return False
            
            temp_path, is_cached = download_result
            basename = os.path.basename(temp_path)

            if self._is_already_played(basename, temp_path, is_cached):
                return False

            if self._is_existing_in_audio_folder(basename, temp_path, is_cached):
                return True

            lyrics = self.transcript_api.generate_response(temp_path)
            if not lyrics:
                return self._handle_no_lyrics(basename, temp_path)

            if not self._is_acceptable_text(lyrics, basename, temp_path):
                return False

            return self._handle_sentiment_analysis(lyrics, basename, temp_path)
        except Exception as e:
            logger.error(f"Error processing song: {e}")
            return False

    def _extract_video_id(self, url):
        """
        Extracts the video ID from a YouTube URL.

        Parameters
        ----------
        url : str
            The URL of the YouTube video.

        Returns
        -------
        str
            The extracted video ID.
        """
        from pytubefix import extract
        return extract.video_id(url)

    def _is_blacklisted(self, video_id):
        """
        Checks if a song is blacklisted based on its video ID.

        Parameters
        ----------
        video_id : str
            The ID of the video to check.

        Returns
        -------
        bool
            True if the song is blacklisted, False otherwise.
        """
        blacklisted_songs = self._get_blacklisted_songs()
        if any(video_id in song for song in blacklisted_songs):
            logger.info(f"Song with video_id {video_id} is blacklisted - skipping download")
            return True
        return False

    def _is_already_played(self, basename, temp_path, is_cached):
        """
        Checks if a song has already been played.

        Parameters
        ----------
        basename : str
            The name of the song file.
        temp_path : str
            The path to the temporary song file.
        is_cached : bool
            Whether the song is cached.

        Returns
        -------
        bool
            True if the song has already been played, False otherwise.
        """
        if basename in self.get_played_songs():
            logger.info(f"Song {basename} already played")
            self._remove_temp_file(temp_path, is_cached)
            return True
        return False

    def _is_existing_in_audio_folder(self, basename, temp_path, is_cached):
        """
        Checks if a song already exists in the audio folder.

        Parameters
        ----------
        basename : str
            The name of the song file.
        temp_path : str
            The path to the temporary song file.
        is_cached : bool
            Whether the song is cached.

        Returns
        -------
        bool
            True if the song exists in the audio folder, False otherwise.
        """
        existing_path = os.path.join(AUDIO_FOLDER_PATH, basename)
        if os.path.exists(existing_path):
            logger.info(f"Song {basename} already exists in audio folder")
            self._remove_temp_file(temp_path, is_cached)
            self.aimp_controller.add_song_to_playlist(existing_path)
            self.add_to_played_songs(basename)
            
            duration = self._get_song_duration(existing_path)
            if duration:
                logger.debug(f"Duration for existing song {basename}: {duration}")
            
            return True
        return False

    def _handle_no_lyrics(self, basename, temp_path):
        """
        Handles the case when no lyrics are found for a song.

        Parameters
        ----------
        basename : str
            The name of the song file.
        temp_path : str
            The path to the temporary song file.

        Returns
        -------
        bool
            False to indicate the song was not processed.
        """
        self._add_to_blacklist(basename)
        self._remove_temp_file(temp_path)
        logger.info(f"No lyrics found for {basename}")
        return False

    def _is_acceptable_text(self, lyrics, basename, temp_path):
        """
        Checks if the song lyrics are acceptable based on text analysis.

        Parameters
        ----------
        lyrics : str
            The lyrics of the song.
        basename : str
            The name of the song file.
        temp_path : str
            The path to the temporary song file.

        Returns
        -------
        bool
            True if the lyrics are acceptable, False otherwise.
        """
        analysis_result = self.text_analyzer.analyze_text(lyrics)
        if not analysis_result['is_acceptable']:
            self._add_to_blacklist(basename)
            self._remove_temp_file(temp_path)
            logger.info(f"Text analysis failed for {basename}, {analysis_result['profanity_result']}")
            return False
        return True

    def _handle_sentiment_analysis(self, lyrics, basename, temp_path):
        """
        Handles sentiment analysis of the song lyrics.

        Parameters
        ----------
        lyrics : str
            The lyrics of the song.
        basename : str
            The name of the song file.
        temp_path : str
            The path to the temporary song file.

        Returns
        -------
        bool
            True if the song is deemed acceptable after sentiment analysis, 
            False otherwise.
        """
        sentiment_result = self.sentiment_api.generate_response(lyrics)
        if not sentiment_result:
            self._add_to_blacklist(basename)
            self._remove_temp_file(temp_path)
            logger.info(f"No sentiment result for {basename}")
            return False

        if sentiment_result.get('is_safe_for_radio', False):
            return self._move_song_to_audio_folder(basename, temp_path)
        else:
            logger.info(f"Song {basename} rejected. Reason: {sentiment_result.get('explanation', 'Unknown')}")
            self._add_to_blacklist(basename)
            self._remove_temp_file(temp_path)
            return False

    def _move_song_to_audio_folder(self, basename, temp_path):
        """
        Moves a song to the audio folder and adds it to the playlist.

        Parameters
        ----------
        basename : str
            The name of the song file.
        temp_path : str
            The path to the temporary song file.

        Returns
        -------
        bool
            True if the song was successfully moved and added to the playlist, 
            False otherwise.
        """
        final_path = os.path.join(AUDIO_FOLDER_PATH, basename)
        try:
            shutil.move(temp_path, final_path)
            self.aimp_controller.add_song_to_playlist(final_path)
            self.add_to_played_songs(basename)
            logger.info(f"Successfully processed and added song: {basename}")
            return True
        except Exception as e:
            logger.error(f"Error moving files for {basename}: {e}")
            self._remove_temp_file(temp_path)
            return False

    def _remove_temp_file(self, temp_path, is_cached=False):
        """
        Removes a temporary song file from the filesystem.

        Parameters
        ----------
        temp_path : str
            The path to the temporary song file.
        is_cached : bool, optional
            Whether the song is cached (default is False).
        """
        if os.path.exists(temp_path) and not is_cached:
            os.remove(temp_path)

    def _add_to_blacklist(self, basename: str):
        """
        Adds a song to the blacklist.

        Parameters
        ----------
        basename : str
            The name of the song file.
        """
        try:
            blacklisted_songs = self._get_blacklisted_songs()
            
            if basename not in blacklisted_songs:
                with open(BLACKLISTED_SONGS, 'a', encoding='utf-8') as f:
                    f.write(f"{basename}\n")
                logger.info(f"Added {basename} to blacklist")
            else:
                logger.debug(f"Song {basename} already in blacklist - skipping")
        except Exception as e:
            logger.error(f"Error adding to blacklist: {e}")
            
    def _get_blacklisted_songs(self) -> List[str]:
        """
        Retrieves the list of blacklisted songs.

        Returns
        -------
        List[str]
            A list of blacklisted song filenames.
        """
        try:
            if not os.path.exists(BLACKLISTED_SONGS):
                with open(BLACKLISTED_SONGS, 'w', encoding='utf-8') as f:
                    f.write('')
                return []
                
            with open(BLACKLISTED_SONGS, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.error(f"Error reading blacklisted songs: {e}")
            return []

    @log_errors
    def update_playlist_local(self):
        """
        Updates the local playlist with random songs until the total duration 
        exceeds 50 minutes.

        This method selects random songs from the local folder and adds them 
        to the playlist until the total duration reaches the target.
        """
        self.aimp_controller.prepare_for_update()
        total_duration = timedelta()
        
        while total_duration < timedelta(minutes=50):
            song_path = self._get_random_local_song()
            if not song_path:
                break
                
            duration = self._get_song_duration(song_path)
            if duration:
                total_duration += duration
                self.aimp_controller.add_song_to_playlist(song_path)
                
        logger.info(f"Local playlist updated, total duration: {total_duration}")

    def _time_calc(self, time1_obj: timedelta) -> timedelta:
        """
        Calculates the sum of a given time and the duration of a random song.

        Parameters
        ----------
        time1_obj : timedelta
            The initial time object to add the duration to.

        Returns
        -------
        timedelta
            The updated time object after adding the random song duration.
        """
        time2_obj = self._get_song_duration(self._get_random_local_song())
        return time1_obj + time2_obj if time2_obj else time1_obj
        
    @log_errors
    def _get_random_local_song(self) -> Optional[str]:
        """
        Selects a random song from the local audio folder that has not been played yet.

        Returns
        -------
        Optional[str]
            The full path to the selected song, or None if no unplayed songs 
            are available.
        """
        files_list = os.listdir(AUDIO_FOLDER_PATH)
        logger.debug(f"Found {len(files_list)} files in audio folder")
        
        while files_list:
            random_song = choice(files_list)
            logger.debug(f"Selected random song: {random_song}")
            played_songs = self.get_played_songs()
            
            if random_song not in played_songs:
                self.add_to_played_songs(random_song)
                full_path = os.path.join(AUDIO_FOLDER_PATH, random_song)
                self.aimp_controller.add_song_to_playlist(full_path)
                return full_path
                
        logger.warning("No unplayed songs available.")
        return None
        
    @log_errors
    def _get_song_duration(self, song_path: str) -> Optional[timedelta]:
        """
        Calculates the duration of a song.

        Parameters
        ----------
        song_path : str
            The path to the song file.

        Returns
        -------
        Optional[timedelta]
            The duration of the song as a timedelta object, or None if the 
            duration could not be determined.
        """
        if not song_path:
            logger.warning("No song path provided for duration calculation")
            return None
        
        try:
            logger.debug(f"Calculating duration for {os.path.basename(song_path)}")
            audio = AudioFileClip(song_path)
            duration = timedelta(seconds=audio.duration)
            audio.close()
            logger.debug(f"Duration calculated: {duration}")
            return duration
        except Exception as e:
            logger.error(f"Error calculating duration for {os.path.basename(song_path)}: {e}")
            return None

    @staticmethod
    def _parse_duration(duration_str: str) -> int:
        """
        Parses a duration string in the format "HH:MM:SS" and converts it to 
        the number of seconds.

        Parameters
        ----------
        duration_str : str
            The duration string to parse.

        Returns
        -------
        int
            The duration in seconds.
        """
        try:
            duration_obj = datetime.strptime(duration_str, "%H:%M:%S") - datetime.strptime("00:00:00", "%H:%M:%S")
            return int(duration_obj.total_seconds())
        except ValueError as e:
            logger.error(f"Invalid duration format: {e}")
            return 0

    @handle_exceptions
    def add_to_played_songs(self, basename: str) -> None:
        """
        Adds a song to the list of played songs.

        Parameters
        ----------
        basename : str
            The name of the song file.
        """
        try:
            with open(PLAYED_SONGS_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{basename}\n")
            logger.debug(f"Added {basename} to played songs")
        except Exception as e:
            logger.error(f"Error adding to played songs: {e}")

    @handle_exceptions
    def get_played_songs(self) -> List[str]:
        """
        Reads the list of played songs from a file.

        If the file does not exist, an empty file is created, and the method 
        returns an empty list. If an error occurs while reading, the method 
        returns an empty list and logs the error message.

        Returns
        -------
        List[str]
            A list of played song names (file paths), or an empty list if no 
            songs have been played or if an error occurred.
        """
        try:
            if not os.path.exists(PLAYED_SONGS_FILE):
                with open(PLAYED_SONGS_FILE, 'w', encoding='utf-8') as f:
                    f.write('')
                return []
                
            with open(PLAYED_SONGS_FILE, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.error(f"Error reading played songs: {e}")
            return []

    def create_directory_playlist(self, directory: str) -> str:
        """
        Creates a playlist name based on the directory.

        If the specified directory does not exist, raises a ValueError.

        Parameters
        ----------
        directory : str
            The directory path from which to create the playlist name.

        Returns
        -------
        str
            The name of the playlist, which is a string prefixed with 'priority_' 
            and suffixed with the directory name.

        Raises
        ------
        ValueError
            If the specified directory does not exist.
        """
        full_path = os.path.join(BASE_DIR, directory)
        if not os.path.exists(full_path):
            raise ValueError(f"Katalog {directory} nie istnieje")
            
        return f"priority_{os.path.basename(directory)}"

    def load_directory_playlist(self, directory: str, playlist_name: str) -> None:
        """
        Loads an audio playlist from the specified directory.

        This method scans the directory for audio files with the extensions 
        '.mp3', '.wav', '.m4a', or '.webm'. If no audio files are found, 
        raises a ValueError. The method then prepares the AIMP controller 
        and adds the audio files to the playlist.

        Parameters
        ----------
        directory : str
            The directory path to load the audio files from.
        playlist_name : str
            The name of the playlist to be loaded.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the specified directory does not exist or if no audio files 
            are found in the directory.
        """
        try:
            full_path = os.path.join(BASE_DIR, directory)
            if not os.path.exists(full_path):
                raise ValueError(f"Katalog {directory} nie istnieje")
                
            audio_files = []
            for file in os.listdir(full_path):
                if file.endswith(('.mp3', '.wav', '.m4a', '.webm')):
                    audio_files.append(os.path.join(full_path, file))
            
            if not audio_files:
                raise ValueError(f"Brak plików audio w katalogu {directory}")
            
            self.aimp_controller.prepare_for_update()
            for audio_file in audio_files:
                self.aimp_controller.add_song_to_playlist(audio_file)
            
            logger.info(f"Załadowano playlistę priorytetową: {playlist_name} ({len(audio_files)} plików)")
            
        except Exception as e:
            logger.error(f"Błąd podczas ładowania playlisty z katalogu: {e}")
            raise