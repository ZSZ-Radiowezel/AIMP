import threading
import time
import schedule
import logging

from logging_config import setup_logging

from modules.block_manager import BlockManager
from modules.text_analysis import TextAnalyzer
from modules.hotkey_manager import HotkeyManager
from modules.aimp_controller import AimpController
from modules.playlist_manager import PlaylistManager
from modules.schedule_manager import ScheduleManager
from modules.gemini import TranscriptAPI, SentimentAPI
from modules.youtube_downloader import YoutubeDownloader
from modules.utils import load_prompts, ensure_directories_exist
from modules.request_manager import RequestManager, CommandServer

from config import (
    GEMINI_API_KEY, 
    GEMINI_MODEL,
    URL_BACKEND,
    URL_ADMINPAGE,
    BASE_DIR
)


setup_logging()
logger = logging.getLogger(__name__)

def initialize_components():
    """
    Initializes all components of the application, setting up necessary modules, 
    and establishing connections between them.

    The function creates instances of various modules such as `TextAnalyzer`, `TranscriptAPI`, 
    `SentimentAPI`, `AimpController`, `YoutubeDownloader`, `RequestManager`, `PlaylistManager`, 
    `ScheduleManager`, and `BlockManager`. It also configures the `CommandServer` and starts 
    necessary services like AIMP and hotkey management.

    Returns
    -------
    tuple
        A tuple containing instances of the initialized components: 
        `aimp_controller`, `request_manager`, `hotkey_manager`, and `schedule_manager`.

    Raises
    ------
    Exception
        If any error occurs during the initialization of components.
    """
    try:
        ensure_directories_exist()
        
        prompt_sentiment, prompt_transcript = load_prompts()
        text_analyzer = TextAnalyzer()
        text_analyzer.initialize()
        
        transcript_api = TranscriptAPI(
            api_key=GEMINI_API_KEY, 
            model=GEMINI_MODEL, 
            prompt=prompt_transcript
        )
        sentiment_api = SentimentAPI(
            api_key=GEMINI_API_KEY, 
            model=GEMINI_MODEL, 
            prompt=prompt_sentiment
        )
        
        aimp_controller = AimpController()
        youtube_downloader = YoutubeDownloader()
        
        request_manager = RequestManager(URL_BACKEND, URL_ADMINPAGE) 
        
        playlist_manager = PlaylistManager(
            aimp_controller=aimp_controller,
            youtube_downloader=youtube_downloader,
            text_analyzer=text_analyzer,
            transcript_api=transcript_api,
            sentiment_api=sentiment_api,
            request_manager=request_manager
        )
        
        schedule_manager = ScheduleManager(
            playlist_manager=playlist_manager, 
            aimp_controller=aimp_controller,
            block_manager=None  
        )
        
        block_manager = BlockManager(BASE_DIR, schedule_manager)

        schedule_manager.block_manager = block_manager
        
        aimp_controller.clear_played_songs()

        command_server = CommandServer(port=5050)
        command_server.set_context(
            schedule_manager=schedule_manager,
            aimp_controller=aimp_controller,
            block_manager=block_manager,
            youtube_downloader=youtube_downloader)
        
        command_server.register_routes()
        command_server.start()
        
        hotkey_manager = HotkeyManager(playlist_manager, aimp_controller)
        
        logger.info("All components initialized successfully")
        return (
            aimp_controller, 
            request_manager, 
            hotkey_manager,
            schedule_manager
        )
    except Exception as e:
        logger.error(f"Error during initialization: {e}")
        raise

def run_schedule():
    """
    Runs the scheduled tasks in a loop, checking and executing tasks pending according 
    to the schedule. This function is designed to run in a separate thread to handle 
    the scheduling of tasks asynchronously.

    Continuously checks for pending scheduled tasks and executes them every 5 seconds.

    Raises
    ------
    Exception
        If any error occurs while running the scheduled tasks.
    """
    while True:
        try:
            schedule.run_pending()
            time.sleep(5)
        except Exception as e:
            logger.error(f"Error in schedule loop: {e}")

def run_priority_scheduler():
    """
    Runs the priority-based scheduler tasks in a loop, checking and executing high-priority 
    tasks pending according to the schedule. This function is designed to run in a separate 
    thread for handling priority tasks asynchronously.

    Continuously checks for priority scheduled tasks and executes them every 1 second.

    Raises
    ------
    Exception
        If any error occurs while running the priority scheduler.
    """
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error in priority_scheduler thread: {e}")

def main():
    """
    The main entry point of the application. Initializes all components, sets up schedules, 
    starts AIMP, and listens for hotkeys. Also runs the main loop that tracks and posts 
    the currently playing song to the backend.

    This function starts all necessary threads for hotkey listening, scheduling, and 
    priority scheduling. It also continuously monitors the current track from AIMP and 
    posts the information about the playing song to the backend every time the song changes.

    Returns
    -------
    None

    Raises
    ------
    KeyboardInterrupt
        If the user interrupts the application with a keyboard signal (e.g., Ctrl+C).
    Exception
        If any fatal error occurs during the execution of the main application.
    """
    try:
        (
            aimp_controller, 
            request_manager, 
            hotkey_manager,
            schedule_manager
        ) = initialize_components()
        
        schedule_manager.setup_schedules()
        
        aimp_controller.start_aimp()
        
        hotkey_thread = threading.Thread(
            target=hotkey_manager.start_hotkey_listener, 
            daemon=True,
            name="HotkeyThread"
        )
        schedule_thread = threading.Thread(
            target=run_schedule,
            daemon=True,
            name="ScheduleThread"
        )
        
        hotkey_thread.start()
        schedule_thread.start()
        
        priority_thread = threading.Thread(
            target=run_priority_scheduler,
            daemon=True,
            name="PrioritySchedulerThread"
        )
        priority_thread.start()
        
        logger.info("Application started successfully")
        
        # Main loop
        previous_title = None
        while True:
            time.sleep(3)
            try:
                current_track = aimp_controller.get_current_track_info()
                if current_track and current_track['title'] != previous_title:
                    previous_title = current_track['title']
                    request_manager.post_playing_song(current_track)
                    
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        print("\nShutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        pass

if __name__ == "__main__":
    main()
