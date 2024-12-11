import logging
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Callable
import os
import time

from .decorators import log_errors

from config import (
    PLAYLIST_UPDATE_TIMES,
    DEVICE_START_TIMES,
    DEVICE_STOP_TIMES,
    AUDIO_DEVICE_NAME,
    BASE_DIR
)

logger = logging.getLogger(__name__)

class ScheduleManager:

    def __init__(self, playlist_manager, aimp_controller, block_manager):
        """
        A class to manage schedules for playlist updates, audio device control, 
        and block periods, including managing priority playlists.

        Attributes
        ----------
        playlist_manager : PlaylistManager
            The playlist manager responsible for handling playlists.
        aimp_controller : AIMPController
            The controller for the AIMP audio player.
        block_manager : BlockManager
            The manager that handles blocking periods.
        priority_tasks : Dict[str, dict]
            A dictionary holding scheduled priority tasks.
        is_priority_playing : bool
            A flag indicating if a priority playlist is currently playing.
        current_priority_task : str
            The ID of the currently playing priority task.
        priority_end_time : datetime
            The end time of the currently playing priority playlist.
        """
        self.playlist_manager = playlist_manager
        self.aimp_controller = aimp_controller
        self.block_manager = block_manager
        self.priority_tasks: Dict[str, dict] = {}
        self.is_priority_playing = False
        self.current_priority_task = None
        self.priority_end_time = None
        self.is_loaded  =False
        
    def _run_if_not_blocked(self, task: Callable) -> Callable:
        """
        Wraps the given task to ensure it only runs when there is no active block period.

        Parameters
        ----------
        task : Callable
            The task to be wrapped and executed.

        Returns
        -------
        Callable
            A wrapped function that will execute the task if the block is not active.
        """
        def wrapper(*args, **kwargs):
            
            if self.is_priority_playing:
                logger.info(f"Task {task.__name__} skipped - priority playlist is playing")
                return
                
            if not self.block_manager.is_blocked():
                logger.debug(f"Executing task: {task.__name__}")
                if datetime.today().weekday() < 5:  
                    return task(*args, **kwargs)
                else:
                    logger.info("Today is a weekend, skipping the task.")
            else:
                logger.info("Task is blocked, skipping.")
                return
            
            logger.info(f"Task {task.__name__} skipped - blockade period active")
            
        return wrapper

    @log_errors
    def setup_schedules(self):
        """
        Sets up the schedules for playlist updates, device control, and block periods.

        Schedules tasks such as updating the playlist, starting and stopping devices, 
        and managing block periods. This method is called to initialize the schedule.
        """
        schedule.every().day.at("00:01").do(self._schedule_daily_blocks)

        for time_str in PLAYLIST_UPDATE_TIMES:
            schedule.every().day.at(f"{time_str}:00").do(
                self._run_if_not_blocked(self.playlist_manager.update_playlist)
            )

        for stop_time in DEVICE_STOP_TIMES:
            schedule.every().day.at(f"{stop_time}:00").do(
                self._run_if_not_blocked(
                    lambda: self.aimp_controller.stop_audio_device(device=AUDIO_DEVICE_NAME)
                )
            )

        for start_time in DEVICE_START_TIMES:
            schedule.every().day.at(f"{start_time}:00").do(
                self._run_if_not_blocked(self.aimp_controller.start_audio_device)
            )
            schedule.every().day.at(f"{start_time}:00").do(
                self._run_if_not_blocked(self.aimp_controller.play_song)
            )

        schedule.every().day.at("07:44:00").do(
            self.aimp_controller.clear_played_songs
        )

        self._schedule_daily_blocks()
        
        logger.info("All schedules have been configured")

    def _schedule_daily_blocks(self):
        """
        Schedules the daily block periods based on the current day's blocks.

        The method checks the block manager for block periods and schedules them 
        accordingly for the current day.
        """
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            blocks = self.block_manager.get_blocks()
            
            schedule.clear("block")
            
            for block in blocks:
                if block["date"] == today:
                    self._add_block_to_schedule(block)
                    
            logger.info(f"Updated blockade schedule as of: {today}")
            
        except Exception as e:
            logger.error(f"Exception when planning daily blockades: {e}")

    def _add_block_to_schedule(self, block):
        """
        Adds a specific block period to the schedule.

        The block is added if its start and end times are in the future. The method 
        also ensures the block is scheduled correctly.

        Parameters
        ----------
        block : dict
            A dictionary containing block information, including the date, 
            start time, and end time.
        """
        try:
            block_date = datetime.strptime(block["date"], "%Y-%m-%d")
            start_time = datetime.strptime(block["start_time"], "%H:%M").time()
            end_time = datetime.strptime(block["end_time"], "%H:%M").time()

            start_datetime = datetime.combine(block_date.date(), start_time)
            end_datetime = datetime.combine(block_date.date(), end_time)
            
            current_time = datetime.now()
            
            if start_datetime > current_time:
                schedule.every().day.at(block["start_time"]).do(
                    self._start_block_period
                ).tag("block").until(start_datetime + timedelta(minutes=1))
            
            if end_datetime > current_time:
                schedule.every().day.at(block["end_time"]).do(
                    self._end_block_period
                ).tag("block").until(end_datetime + timedelta(minutes=1))
            
            logger.info(f"A blockade has been planned for: {block['date']}: {block['start_time']} - {block['end_time']}")
            
        except Exception as e:
            logger.error(f"Exception when adding a blockade to the schedule: {e}")

    def add_block_immediately(self, block):
        """
        Adds a block period to the schedule immediately if the block is for the current day.

        Parameters
        ----------
        block : dict
            A dictionary containing block information, including the date, 
            start time, and end time.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        if block["date"] == today:
            self._add_block_to_schedule(block)
            logger.info(f"Immediately added a blockade to the schedule: {block['start_time']} - {block['end_time']}")
        else:
            logger.info(f"Blockade is not for today, not added to schedule: {block['date']}")

    def _start_block_period(self):
        """
        Pauses the music playback when a block period starts.

        This method is called to pause the audio playback at the beginning of 
        a block period.
        """
        try:
            if self.aimp_controller.is_playing():
                logger.info("Starting the blockade - pausing the music")
                self.aimp_controller.pause_song()
        except Exception as e:
            logger.error(f"Error during start of blockade: {e}")

    def _end_block_period(self):
        """
        Resumes music playback after the block period ends.

        This method resumes the audio playback at the end of a block period, 
        provided no priority playlist is currently playing.
        """
        try:
            if not self.is_priority_playing:
                logger.info("End of blockade - resume playback")
                self.aimp_controller.play_song()
        except Exception as e:
            logger.error(f"Error during end of blockade: {e}")

    def add_priority_playlist(self, directory: str, play_date: str, play_time: str) -> str:
        """
        Schedules a priority playlist to be played at a specific date and time.

        This method schedules a playlist to play based on a specified directory, 
        date, and time. It also calculates the total duration of the playlist.

        Parameters
        ----------
        directory : str
            The directory containing the audio files for the playlist.
        play_date : str
            The date when the playlist should start, in 'YYYY-MM-DD' format.
        play_time : str
            The time when the playlist should start, in 'HH:MM' format.

        Returns
        -------
        str
            A unique task ID for the scheduled priority playlist.

        Raises
        ------
        ValueError
            If the specified play date and time are in the past or if a task 
            with the same ID already exists.
        """
        try:
            play_datetime = datetime.strptime(f"{play_date} {play_time}", '%Y-%m-%d %H:%M')
            if play_datetime < datetime.now():
                raise ValueError("Date and time must be in the future")
            
            task_id = f"priority_{directory}_{play_date}_{play_time}"
            
            if task_id in self.priority_tasks:
                raise ValueError(f"A task with ID {task_id} already exists")
            
            playlist_name = self.playlist_manager.create_directory_playlist(directory)
            
            full_path = os.path.join(BASE_DIR, directory)
            total_duration = timedelta()
            audio_files = [f for f in os.listdir(full_path) 
                          if f.endswith(('.mp3', '.wav', '.m4a', '.webm'))]
            
            for file in audio_files:
                file_path = os.path.join(full_path, file)
                duration = self.playlist_manager._get_song_duration(file_path)
                if duration:
                    total_duration += duration
            
            def play_priority_playlist():
                current_datetime = datetime.now()
                if current_datetime.date() == play_datetime.date():
                    if not self.is_loaded:
                        logger.info(f"Starting priority playlist: {playlist_name}")
                        self.is_loaded=True
                        self.is_priority_playing = True
                        self.current_priority_task = task_id
                        self.priority_end_time = datetime.now() + total_duration
                        
                        self.playlist_manager.load_directory_playlist(directory, playlist_name)
                        time.sleep(1)
                        self.aimp_controller.play_song()
                        self.aimp_controller.start_audio_device()
                        
                        self._schedule_playlist_check(task_id)
            
            job = schedule.every().day.at(play_time).do(
                play_priority_playlist
            )
            
            self.priority_tasks[task_id] = {
                'job': job,
                'playlist_name': playlist_name,
                'play_datetime': play_datetime,
                'directory': directory,
                'duration': total_duration
            }
            
            logger.info(f"Scheduled priority playlist: {task_id} for {play_date} {play_time}")
            return task_id
            
        except Exception as e:
            logger.error(f"Error scheduling priority playlist: {e}")
            raise

    def _schedule_playlist_check(self, task_id: str):
        """
        Schedules a periodic check to monitor the status of a priority playlist.

        The check ensures that the playlist is playing and stops once the expected 
        end time has been reached.

        Parameters
        ----------
        task_id : str
            The unique task ID of the priority playlist being checked.
        """
        def check_playlist_status():
            if not self.is_priority_playing or task_id != self.current_priority_task:
                return schedule.CancelJob

            try:
                current_time = datetime.now()
                
                if current_time >= self.priority_end_time:
                    logger.info("Priority playlist finished - reached expected end time")
                    self._cleanup_priority_task(task_id)
                    self.is_loaded=False
                    return schedule.CancelJob
                
                time_left = self.priority_end_time - current_time
                logger.debug(f"Priority playlist time remaining: {time_left}")
                
            except Exception as e:
                logger.error(f"Error checking playlist status: {e}")
                
        schedule.every(30).seconds.do(check_playlist_status)

    def _cleanup_priority_task(self, task_id: str) -> None:
        """
        Cleans up after the completion of a priority playlist.

        Cancels the scheduled task and restores the normal playlist once the 
        priority playlist has finished playing.

        Parameters
        ----------
        task_id : str
            The unique task ID of the completed priority playlist.
        """
        if task_id in self.priority_tasks:
            task = self.priority_tasks[task_id]
            schedule.cancel_job(task['job'])
            del self.priority_tasks[task_id]
            
            self.is_priority_playing = False
            self.current_priority_task = None
            self.priority_end_time = None
            
            self.playlist_manager.update_playlist()
            self.aimp_controller.play_song()
            logger.info(f"Cleaned up priority task: {task_id} and restored normal playlist")

    def get_priority_tasks(self) -> List[Dict]:
        """
        Retrieves the list of currently scheduled priority tasks.

        Returns
        -------
        List[Dict]
            A list of dictionaries containing details about the scheduled 
            priority tasks, including task ID, directory, play date, and playlist name.
        """
        return [{
            'task_id': task_id,
            'directory': task['directory'],
            'play_datetime': task['play_datetime'].strftime('%Y-%m-%d %H:%M'),
            'playlist_name': task['playlist_name']
        } for task_id, task in self.priority_tasks.items()]