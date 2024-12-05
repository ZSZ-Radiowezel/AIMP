import keyboard
import logging
from .decorators import log_errors

from config import MAIN_AUDIO_DEVICE_NAME

logger = logging.getLogger(__name__)

class HotkeyManager:
    def __init__(self, playlist_manager, aimp_controller):
        """
        A class that manages hotkeys for controlling the AIMP audio player and playlist updates.

        Parameters
        ----------
        playlist_manager : PlaylistManager
            An instance of the PlaylistManager used for updating playlists.
        aimp_controller : AimpController
            An instance of the AimpController used for controlling the AIMP audio player.
        """
        self.playlist_manager = playlist_manager
        self.aimp_controller = aimp_controller
        self._setup_hotkeys()

    def _setup_hotkeys(self):
        """
        Sets up the hotkey mappings for controlling the AIMP audio player and managing playlists.

        The hotkeys are mapped as follows:
        - 'p': Stop audio device
        - 's': Start audio device
        - 'u': Update playlist
        - 'l': Update playlist locally (from disk)
        - 'z': Play song
        """
        self.hotkey_mappings = {
            'p': self.aimp_controller.stop_audio_device(MAIN_AUDIO_DEVICE_NAME),
            's': self.aimp_controller.start_audio_device,
            'u': self.playlist_manager.update_playlist,
            'l': self.playlist_manager.update_playlist_local,
            'z': self.aimp_controller.play_song
        }

    @log_errors
    def start_hotkey_listener(self):

        """
        Starts listening for hotkey presses and executes the corresponding actions.

        The following commands are available:
        - 'u': Update playlist
        - 'l': Update playlist locally (from disk)
        - 'p': Mute sound device
        - 's': Unmute sound device
        - 'z': Play song

        The method blocks until the user exits the program (Ctrl + C).
        
        Logs any errors that occur during execution.

        Raises
        ------
        KeyboardInterrupt
            If the user presses Ctrl + C to exit the program.
        """
        for key, callback in self.hotkey_mappings.items():
            keyboard.add_hotkey(key, callback)
        
        # Print available commands
        print("\nAvailable commands:")
        print("Press u to update playlist")
        print("Press l to update playlist locally (from disk)")
        print("Press p to mute sound device")
        print("Press s to unmute sound device")
        print("Press z to play song")
        print("Press Ctrl + C to exit\n")

        keyboard.wait()