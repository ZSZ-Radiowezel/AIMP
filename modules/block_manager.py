import os
import json
import logging

from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

class BlockManager:
    def __init__(self, base_dir: str, schedule_manager):
        """
        Manages blocks that define time intervals during which certain actions are restricted.

        Parameters
        ----------
        base_dir : str
            The directory where the block file is stored.
        schedule_manager : object
            An object that manages scheduling.

        Attributes
        ----------
        blocks_file : str
            The file path for storing block data in JSON format.
        schedule_manager : object
            An object that manages scheduling, expected to have `add_block_immediately()` method.

        Methods
        -------
        add_block(date: str, start_time: str, end_time: str) -> bool
            Adds a new block for the specified date and time interval.
        remove_block(date: str, start_time: str, end_time: str) -> bool
            Removes a block for the specified date and time interval.
        get_blocks() -> List[Dict[str, str]]
            Returns all blocks stored.
        is_blocked() -> bool
            Checks if the current date and time fall within any block.
        """
        self.blocks_file = os.path.join(base_dir, "blocks.json")
        self._ensure_blocks_file()
        self.schedule_manager = schedule_manager

    def _ensure_blocks_file(self) -> None:
        """
        Ensures the block file exists by creating an empty JSON file if not present.
        """
        if not os.path.exists(self.blocks_file):
            with open(self.blocks_file, 'w', encoding='utf-8') as f:
                json.dump({"blocks": []}, f)

    def add_block(self, date: str, start_time: str, end_time: str) -> bool:
        """
        Adds a new block for a given date and time interval.

        Parameters
        ----------
        date : str
            The date for the block in 'YYYY-MM-DD' format.
        start_time : str
            The starting time of the block in 'HH:MM' format.
        end_time : str
            The ending time of the block in 'HH:MM' format.

        Returns
        -------
        bool
            True if the block was added successfully, False if it already exists or invalid.
        """
        try:
            datetime.strptime(date, "%Y-%m-%d")
            datetime.strptime(start_time, "%H:%M")
            datetime.strptime(end_time, "%H:%M")
            
            blocks = self._read_blocks()
            new_block = {
                "date": date,
                "start_time": start_time,
                "end_time": end_time
            }
            
            if new_block in blocks["blocks"]:
                return False
            
            self.schedule_manager.add_block_immediately(new_block)
                
            blocks["blocks"].append(new_block)
            self._write_blocks(blocks)
            return True
            
        except ValueError as e:
            logger.error(f"Invalid date/time format: {e}")
            return False

    def remove_block(self, date: str, start_time: str, end_time: str) -> bool:
        """
        Removes an existing block for the given date and time interval.

        Parameters
        ----------
        date : str
            The date of the block to remove in 'YYYY-MM-DD' format.
        start_time : str
            The starting time of the block in 'HH:MM' format.
        end_time : str
            The ending time of the block in 'HH:MM' format.

        Returns
        -------
        bool
            True if the block was removed successfully, False otherwise.
        """
        try:
            blocks = self._read_blocks()
            block_to_remove = {
                "date": date,
                "start_time": start_time,
                "end_time": end_time
            }
            
            if block_to_remove in blocks["blocks"]:
                blocks["blocks"].remove(block_to_remove)
                self._write_blocks(blocks)
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error removing blockade: {e}")
            return False

    def get_blocks(self) -> List[Dict[str, str]]:
        """
        Retrieves all stored blocks.

        Returns
        -------
        List[Dict[str, str]]
            A list of blocks with each block represented as a dictionary.
        """
        return self._read_blocks()["blocks"]

    def is_blocked(self) -> bool:
        """
        Checks if the current date and time fall within any defined block.

        Returns
        -------
        bool
            True if the current time is within a block, False otherwise.
        """
        try:
            now = datetime.now()
            current_date = now.strftime("%Y-%m-%d")
            current_time = now.strftime("%H:%M")
            
            for block in self.get_blocks():
                if block["date"] == current_date:
                    if block["start_time"] <= current_time <= block["end_time"]:
                        return True
            return False
            
        except Exception as e:
            logger.error(f"Error checking blockade status: {e}")
            return False

    def _read_blocks(self) -> Dict:
        """
        Reads the blocks from the block file.

        Returns
        -------
        Dict
            A dictionary containing the list of blocks.
        """
        try:
            with open(self.blocks_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading blockades: {e}")
            return {"blocks": []}

    def _write_blocks(self, blocks: Dict) -> None:
        """
        Writes the given blocks to the block file.

        Parameters
        ----------
        blocks : Dict
            A dictionary containing the list of blocks to write.
        """
        try:
            with open(self.blocks_file, 'w', encoding='utf-8') as f:
                json.dump(blocks, f, indent=2)
        except Exception as e:
            logger.error(f"Error writing blockades: {e}") 