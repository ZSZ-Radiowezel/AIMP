import os
import time
import pyaimp
import logging
import subprocess
import threading
import logging

from time import sleep
from typing import Optional, Dict

from .decorators import ensure_connected, handle_exceptions

from config import (
    MAIN_AUDIO_DEVICE_NAME, 
    AIMP_VOLUME_INCREMENT, 
    AIMP_MAX_VOLUME, 
    PLAYED_SONGS_FILE,
    AIMP_PLAYLIST_PATH
)

logger = logging.getLogger(__name__)

class AimpController:
    def __init__(self):
        """
        Controller for managing AIMP audio player using the `pyaimp` library.

        Attributes
        ----------
        command : str
            Command to launch AIMP.
        client : pyaimp.Client, optional
            Client instance for interacting with AIMP.
        current_volume : int
            Current volume level of AIMP.
        """
        self.command = "aimp"
        self.client = None
        self.current_volume = AIMP_MAX_VOLUME
        
    @handle_exceptions
    def get_current_track_info(self) -> Optional[Dict[str, str]]:

        """
        Retrieve information about the currently playing track.

        Returns
        -------
        dict or None
            A dictionary containing the track title and duration, or None if an error occurs.
        """
        if not self.client:
            return None
            
        try:
            info = self.client.get_current_track_info()
            return {
                'title': info.get('title', ''),
                'duration': info.get('duration', '00:00:00')
            }
        except Exception as e:
            logger.error(f"Error getting track info: {e}")
            return None
    
    @handle_exceptions
    def start_aimp(self) -> None:
        """
        Start the AIMP application in a separate thread and connect to the client.
        """
        thread = threading.Thread(target=self.run_aimp)
        thread.start()
        time.sleep(3)  # Wait for AIMP to initialize
        self.connect_to_aimp()
    
    def run_aimp(self) -> None:
        """Launch AIMP using a subprocess."""
        subprocess.run(self.command)
    
    @handle_exceptions
    def connect_to_aimp(self) -> None:
        """
        Connect to the AIMP client.
        """
        self.client = pyaimp.Client()
        self.client.stop()  
    
    @handle_exceptions
    def aimp_quit(self) -> None:
        """
        Quit the AIMP application and reset the client.
        """
        if self.client:
            self.client.quit()
            self.client = None
    
    @ensure_connected
    def add_song_to_playlist(self, song_path: str) -> None:
        """
        Add a song to the active AIMP playlist.

        Parameters
        ----------
        song_path : str
            The file path of the song to add.
        """
        self.client.add_to_active_playlist(song_path)
    
    @ensure_connected
    def play_song(self) -> None:
        """Start playback of the current track."""
        try:
            self.client.play()
            logger.info("Playback started successfully")
        except Exception as e:
            logger.error(f"Error when starting playback: {e}", exc_info=True)
    
    @ensure_connected
    def pause_song(self) -> None:
        """Pause the current playback."""
        try:
            self.client.pause()
            logger.info("Track paused successfully")
        except Exception as e:
            logger.error(f"Error when pausing a song: {e}", exc_info=True)
    
    @ensure_connected
    def skip_song(self) -> None:
        """Skip the current track."""
        self.client.next()
    
    @handle_exceptions
    def stop_audio_device(self, device: str) -> None:
        """
        Gradually reduce the volume of the specified audio device to zero.

        Parameters
        ----------
        device : str
            Name of the audio device.
        """
        volume = self.current_volume
        while volume > 0:
            volume = max(0, volume - AIMP_VOLUME_INCREMENT)
            subprocess.run(f'nircmd setsysvolume {volume} "{device}"')
        self.current_volume = 0
    
    @handle_exceptions
    def start_audio_device(self) -> None:
        """Restore the audio device volume to the maximum level."""
        subprocess.run(f'nircmd setsysvolume 0 "{MAIN_AUDIO_DEVICE_NAME}"')
        volume = 0
        while volume < AIMP_MAX_VOLUME:
            volume = min(AIMP_MAX_VOLUME, volume + AIMP_VOLUME_INCREMENT)
            subprocess.run(f'nircmd setsysvolume {volume} "{MAIN_AUDIO_DEVICE_NAME}"')
        self.current_volume = AIMP_MAX_VOLUME
    
    @handle_exceptions
    def clear_played_songs(self) -> None:
        """Clear the contents of the played songs file."""
        with open(PLAYED_SONGS_FILE, 'w', encoding='utf-8') as f:
            f.write('')

    @handle_exceptions
    def prepare_for_update(self) -> None:
        """Prepare AIMP for updates by stopping audio and clearing playlists."""
        try:
            self.connect_to_aimp()
            self.stop_audio_device(MAIN_AUDIO_DEVICE_NAME)
            self.aimp_quit()
            sleep(2)
            
            if os.path.exists(AIMP_PLAYLIST_PATH):
                for file in os.listdir(AIMP_PLAYLIST_PATH):
                    if file.endswith('.aimppl4'):  
                        try:
                            os.remove(os.path.join(AIMP_PLAYLIST_PATH, file))
                            logger.debug(f"Removed playlist file: {file}")
                        except Exception as e:
                            logger.error(f"Error removing playlist file {file}: {e}")
            
           
            self.start_aimp()
            sleep(1)
            self.connect_to_aimp()
            
            logger.info("AIMP prepared for update")
        except Exception as e:
            logger.error(f"Error preparing AIMP for update: {e}")
            raise

    @handle_exceptions
    def clear_playlist_files(self) -> None:
        """Remove all playlist files in the AIMP playlist directory."""
        if os.path.exists(AIMP_PLAYLIST_PATH):
            for file in os.listdir(AIMP_PLAYLIST_PATH):
                try:
                    os.remove(os.path.join(AIMP_PLAYLIST_PATH, file))
                    logger.debug(f"Removed playlist file: {file}")
                except Exception as e:
                    logger.error(f"Error removing playlist file {file}: {e}")
    
    @ensure_connected
    def is_playing(self) -> bool:

        """
        Check if AIMP is currently playing a track.

        Returns
        -------
        bool
            True if AIMP is playing, False otherwise.
        """
        try:
            state = self.client.get_playback_state()
            logger.debug(f"AIMP playback status: {state}")
            
            is_playing = (state == pyaimp.PlayBackState.Playing)
            logger.debug(f"Is music playing?: {is_playing}")
            
            return is_playing
            
        except Exception as e:
            logger.error(f"Error when checking playback status: {e}", exc_info=True)
            return False
    
    @ensure_connected
    def get_volume(self) -> int:
        """
        Retrieve the current volume level.

        Returns
        -------
        int
            Current volume level as a percentage.
        """
        return self.client.get_volume()
    
    @ensure_connected
    def set_volume(self, number) -> int:
        """
        Set the volume to a specified level.

        Parameters
        ----------
        number : int
            Desired volume level as a percentage.

        Returns
        -------
        bool
            True if the operation is successful, False otherwise.
        """
        try:
            self.client.set_volume(number)
            return True
        except:
            return False
    