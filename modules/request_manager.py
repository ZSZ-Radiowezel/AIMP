import logging
import requests
import threading
import os

from threading import Thread
from typing import Callable
from flask import Flask, request, jsonify
from typing import Optional, Dict, Any, List
from datetime import datetime

from .decorators import log_errors
from .exceptions import APIConnectionError
from .utils import sanitize_name
from config import SPECIAL_PLAYLISTS_PATH
logger = logging.getLogger(__name__)

class RequestManager:
    def __init__(self, backend_url: str, admin_url: str):
        """
    Manages HTTP requests for retrieving and updating song information from the backend.

    Parameters
    ----------
    backend_url : str
        The URL of the backend server providing song data.
    admin_url : str
        The URL of the admin server for administrative operations.

    Attributes
    ----------
    backend_url : str
        URL endpoint for song-related requests.
    admin_url : str
        URL endpoint for administrative tasks.
    """
        self.backend_url = backend_url
        self.admin_url = admin_url

    @log_errors
    def fetch_songs_from_backend(self) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch a list of songs to be played from the backend server.

        Attempts to retrieve the song list up to three times in case of errors.

        Returns
        -------
        list of dict or None
            A list of dictionaries containing song data, or `None` if all attempts fail.

        Notes
        -----
        Each dictionary in the returned list contains metadata such as song title and artist.
        """
        for attempt in range(3):
            try:
                response = requests.get(f"{self.backend_url}/voting/songs-to-play")
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
        return None

    @log_errors
    def post_playing_song(self, track_info: Dict[str, str]) -> bool:
        """
        Notify the backend that a song is currently playing.

        Parameters
        ----------
        track_info : dict of str
            Dictionary containing the song title and duration. Example:
            {'title': 'Song Title', 'duration': '3:45'}

        Returns
        -------
        bool
            `True` if the notification was successful, `False` otherwise.

        Raises
        ------
        Exception
            If a network or server error occurs.
        """
        data = {
            "SongId": track_info['title'],
            "Duration": track_info['duration']
        }
        headers = {'Content-Type': 'application/json'}
        
        for attempt in range(3):
            try:
                response = requests.post(
                    f"{self.backend_url}/voting/playing-song",
                    json=data,
                    headers=headers
                )
                if response.status_code == 200:
                    return True
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
        return False

    def start(self):
        thread = threading.Thread(
            target=lambda: self.app.run(host='0.0.0.0', port=self.port),
            daemon=True,
            name=f"CommandServer-{self.port}"
        )
        thread.start()
        logger.info(f"Command server started on port {self.port}")


class CommandServer:
    def __init__(self, port: int = 5050):
        """
    Implements a Flask-based command server to handle AIMP player commands and playlist scheduling.

    Parameters
    ----------
    port : int, optional
        The port on which the Flask server runs (default is 5050).

    Attributes
    ----------
    app : Flask
        The Flask application instance.
    port : int
        The port number for the server.
    playlist_manager : object or None
        Manages the playlist if set.
    schedule_manager : object or None
        Manages scheduled playlists if set.
    aimp_controller : AimpController or None
        Controls the AIMP player.
    block_manager : BlockManager or None
        Manages playback blocks.
    command_handler : list of str
        List of supported commands for the AIMP player.
    """
        self.app = Flask(__name__)
        self.port = port
        self.schedule_manager = None
        self.command_handler = None
        self.aimp_controller = None
        self.block_manager = None
        self.youtube_downloader = None
    
    def register_routes(self):
        """
        Register all the Flask routes for handling various API endpoints.
        """
        self.app.route('/command', methods=['POST'])(self.handle_command)

        self.app.route('/special/play', methods=['POST'])(self.schedule_priority_playlist)
        self.app.route('/special/get_tasks', methods=['GET'])(self.get_priority_tasks)
        self.app.route('/special/download', methods=['POST'])(self.download_playlist_from_youtube)
        self.app.route('/special/get_playlists', methods=['GET'])(self.get_special_playlists)
        self.app.route('/special/get_songs', methods=['GET'])(self.get_playlist_files)

        self.app.route('/block/add', methods=['POST'])(self.add_block)
        self.app.route('/block/remove', methods=['POST'])(self.remove_block)
        self.app.route('/block/list', methods=['GET'])(self.list_blocks)

        self.app.route('/volume/set', methods=['POST'])(self.set_volume)
        self.app.route('/volume/get', methods=['GET'])(self.get_volume)
    
    def set_context(self,schedule_manager, aimp_controller, block_manager, youtube_downloader):
        self.schedule_manager = schedule_manager
        self.aimp_controller = aimp_controller
        self.block_manager = block_manager
        self.youtube_downloader = youtube_downloader
        self.command_handler = ["play", "pause", "next"]

    def handle_command(self):
        """
        Handle AIMP player commands such as play, pause, and skip.

        Returns
        -------
        Response
            JSON response indicating success or error.
        """
        try:
            data = request.get_json()
            command = data.get('ToDO')
            if command and self.command_handler:
                self._handle_command(command)
                return jsonify({'status': 'success'})
            return jsonify({'status': 'error', 'message': 'Invalid command'}), 400
        except Exception as e:
            logger.error(f"Error handling command: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    def schedule_priority_playlist(self):
        """
        Schedule a playlist to be played at a specific date and time.

        Expects the following JSON payload:
        - 'directory': str, directory path containing the playlist. (relative from BASE_DIR)
        - 'play_date': str, date in 'YYYY-MM-DD' format.
        - 'play_time': str, time in 'HH:MM' format.

        Returns
        -------
        Response
            JSON response indicating success with a `task_id` or an error message.

        Raises
        ------
        ValueError
            If the provided data is invalid.
        """
        try:
            data = request.get_json()
            required_fields = ['directory', 'play_date', 'play_time']
                
            if not all(field in data for field in required_fields):
                return jsonify({
                        'error':'Required fields (directory, play_date, play_time) missing.'
                    }), 400
                
            task_id = self.schedule_manager.add_priority_playlist(
                    directory=os.path.join(SPECIAL_PLAYLISTS_PATH, data['directory']),
                    play_date=data['play_date'],
                    play_time=data['play_time']
                )
                
            return jsonify({
                    'status': 'success',
                    'task_id': task_id,
                    'message': 'Priority playlist planned'
                }), 200
                
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Error when scheduling a playlist: {e}")
            return jsonify({'error': str(e)}), 500

    def get_priority_tasks(self):
        """
        Retrieve the list of scheduled priority playlists.

        Returns
        -------
        Response
            JSON response containing the list of scheduled tasks, or an error message.
        """
        try:
            tasks = self.schedule_manager.get_priority_tasks()
            return jsonify(tasks), 200
        except Exception as e:
            logger.error(f"Error when downloading tasks: {e}")
            return jsonify({'error': str(e)}), 500

    def _handle_command(self, command: str):
        """
        Internal method to handle AIMP commands.

        Parameters
        ----------
        command : str
            The command to be executed, e.g., 'play', 'pause', or 'next'.

        Raises
        ------
        Exception
            If the command execution fails.
        """
        if not self.aimp_controller:
            logger.error("Error while downloading tasks")
            return

        logger.info(f"Received command: {command}")
        try:
            if command == 'play':
                self.aimp_controller.play_song()
            elif command == 'pause':
                self.aimp_controller.pause_song()
            elif command == 'next':
                self.aimp_controller.skip_song()
            else:
                logger.warning(f"Unknown command: {command}")
        except Exception as e:
            logger.error(f"Error executing command {command}: {e}")

    def add_block(self):
        """
        Add a block period to restrict playback during a specified time.

        Expects the following JSON payload:
        - 'date': str, date in 'YYYY-MM-DD' format.
        - 'start_time': str, start time in 'HH:MM' format.
        - 'end_time': str, end time in 'HH:MM' format.

        Returns
        -------
        Response
            JSON response indicating success or an error message.
        """
        try:
            data = request.get_json()
            success = self.block_manager.add_block(
                    data['date'].replace("T00:00:00.000",""),
                    data['start_time'],
                    data['end_time']
                )
            if success:
                return jsonify({'status': 'success'})
            return jsonify({'status': 'error'}), 400
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400

    def remove_block(self):
        """
        Remove a previously set block period.

        Expects the following JSON payload:
        - 'date': str, date in 'YYYY-MM-DD' format.
        - 'start_time': str, start time in 'HH:MM' format.
        - 'end_time': str, end time in 'HH:MM' format.

        Returns
        -------
        Response
            JSON response indicating success or an error message.
        """
        try:
            data = request.get_json()
            success = self.block_manager.remove_block(
                    data['date'].replace("T00:00:00.000",""),
                    data['start_time'],
                    data['end_time']
                )
            if success:
                return jsonify({'status': 'success'})
            return jsonify({'status': 'error'}), 400
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400

    def list_blocks(self):
        """
        List all active block periods.

        Returns
        -------
        Response
            JSON response containing a list of blocks, or an error message.
        """
        try:
            blocks = self.block_manager.get_blocks()
            if blocks:
                return jsonify(blocks)
            return jsonify({'status': 'error'}), 400
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
        
    def get_volume(self):
        try:
            volume = self.aimp_controller.get_volume()
            return jsonify({'volume': volume})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    def set_volume(self):
        try:
            data = request.get_json()
            success = self.aimp_controller.set_volume(data['volume'])
            
            if success:
                return jsonify({'status': 'success'})
            return jsonify({'status': 'error'}), 400
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
        
    def download_playlist_from_youtube(self):
        """
        Downloads a YouTube playlist, validates input data, and handles cases where the playlist already exists.
        
        Returns:
            Flask response: JSON response indicating success or failure.
        """
        try:
            data = request.get_json()

            if not data or 'name' not in data or 'playlist_url' not in data:
                return jsonify({'status': 'error', 'reason': 'Missing required fields: name and playlist_url'}), 400

            standarized_name = sanitize_name(data['name'])
            if standarized_name[0]:
                append = bool(int(data.get('append', 0)))

                if standarized_name[1] in os.listdir(SPECIAL_PLAYLISTS_PATH) and not append:
                    return jsonify({'status': 'error', 'reason': 'Playlist already exists', 'playlist_files': os.listdir(os.path.join(SPECIAL_PLAYLISTS_PATH,standarized_name[0]))}), 400
                
                success = self.youtube_downloader.download_playlist(
                    url=data['playlist_url'],
                    path=os.path.join(SPECIAL_PLAYLISTS_PATH, standarized_name[1])
                )
                
                if success:
                    return jsonify({'status': 'success'})
            
            return jsonify({'status': 'error', 'reason': standarized_name[1]}), 400

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            return jsonify({'status': 'error', 'reason': 'Internal server error'}), 500

    def get_special_playlists(self):
        return jsonify(os.listdir(SPECIAL_PLAYLISTS_PATH))
    
    def get_playlist_files(self):
        name = request.args.get('name')
        files = os.listdir(os.path.join(SPECIAL_PLAYLISTS_PATH, name))
        return jsonify(files)

    def start(self):
        """
        Start the command server in a separate thread.

        Notes
        -----
        The server runs in daemon mode, which allows it to be stopped with the main application.
        """
        thread = threading.Thread(
            target=lambda: self.app.run(host='0.0.0.0', port=self.port),
            daemon=True,
            name=f"CommandServer-{self.port}"
        )
        thread.start()
        logger.info(f"Command server started on port {self.port}")

