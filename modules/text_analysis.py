import re
import logging

from typing import Dict, Set, Optional
from langdetect import detect
from ahocorasick import Automaton

from .decorators import handle_exceptions
from .exceptions import TextAnalysisError

logger = logging.getLogger(__name__)

class TextAnalyzer:
    def __init__(self):
        """
        A class for analyzing text to detect profanity and remove emojis.

        Attributes
        ----------
        profanity_pl_automaton : Automaton
            The Aho-Corasick automaton for detecting profanity words in Polish.
        profanity_en_automaton : Automaton
            The Aho-Corasick automaton for detecting profanity words in English.
        emoji_unicode_ranges : Set[int]
            A set of Unicode code points representing emoji characters.
        initialized : bool
            A flag indicating whether the TextAnalyzer has been initialized.
        """
        self.profanity_pl_automaton = Automaton()
        self.profanity_en_automaton = Automaton()
        self.emoji_unicode_ranges = self._create_emoji_unicode_ranges()
        self.initialized = False
        
    def initialize(self) -> None:
        """
        Initializes the profanity detection automatons by loading words from files.
        
        Loads profanity words into the Polish and English automata, and sets the
        `initialized` flag to True upon successful initialization.

        Raises
        ------
        TextAnalysisError
            If initialization fails due to an error loading the profanity files.
        """
        try:
            self._load_words_into_automaton("wulgaryzmy_pl.txt", self.profanity_pl_automaton)
            self._load_words_into_automaton("wulgaryzmy_en.txt", self.profanity_en_automaton)
            self.initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize TextAnalyzer: {e}")
            raise TextAnalysisError("Initialization failed")

    @handle_exceptions
    def analyze_text(self, text: str) -> Dict:
        """
        Analyzes the input text for profanity and removes emojis.
        
        Parameters
        ----------
        text : str
            The text to be analyzed.
        
        Returns
        -------
        Dict
            A dictionary containing:
            - 'text_clean': The text with emojis removed.
            - 'profanity_result': A string indicating the level of profanity.
            - 'is_acceptable': A boolean indicating whether the text is acceptable.
        
        Raises
        ------
        TextAnalysisError
            If the TextAnalyzer is not initialized.
        """
        if not self.initialized:
            raise TextAnalysisError("TextAnalyzer not initialized")
            
        text = self.del_emoji(text)
        profanity_result = self.analyze_profanity(text)
        
        return {
            'text_clean': text,
            'profanity_result': profanity_result,
            'is_acceptable': self._is_text_acceptable(profanity_result)
        }

    def _is_text_acceptable(self, profanity_result: str) -> bool:
        """
        Determines if the text is acceptable based on the profanity result.

        Parameters
        ----------
        profanity_result : str
            The result of the profanity analysis.
        
        Returns
        -------
        bool
            True if the text is acceptable, False otherwise.
        """
        return profanity_result in [
            "6 swear words or less",
            "Lyrics go to NLP model"
        ]

    @staticmethod
    def _create_emoji_unicode_ranges() -> Set[int]:
        """
        Creates a set of Unicode ranges representing emoji characters.

        Returns
        -------
        Set[int]
            A set of Unicode code points that correspond to various emojis.
        """
        ranges = [
            (0x1F600, 0x1F64F),  # emoticons
            (0x1F300, 0x1F5FF),  # symbols & pictographs
            (0x1F680, 0x1F6FF),  # transport & map symbols
            (0x1F1E0, 0x1F1FF),  # flags (iOS)
            (0x2702, 0x27B0),
            (0x24C2, 0x1F251),
            (0x1F926, 0x1F937),
            (0x10000, 0x10FFFF),
            (0x2640, 0x2642),
            (0x2600, 0x2B55),
            (0x200d, 0x200d),
            (0x23cf, 0x23cf),
            (0x23e9, 0x23e9),
            (0x231a, 0x231a),
            (0xfe0f, 0xfe0f),
            (0x3030, 0x3030)
        ]
        return {code_point for start, end in ranges for code_point in range(start, end + 1)}

    def del_emoji(self, text: str) -> str:
        """
        Removes emojis from the given text.

        Parameters
        ----------
        text : str
            The text from which emojis should be removed.
        
        Returns
        -------
        str
            The input text with all emojis removed.
        """
        return ''.join(char for char in text if ord(char) not in self.emoji_unicode_ranges)

    @handle_exceptions
    def analyze_profanity(self, text: str) -> str:
        """
        Analyzes the text for profanity and returns a description of the result.

        Parameters
        ----------
        text : str
            The text to be analyzed for profanity.
        
        Returns
        -------
        str
            A string indicating the level of profanity, such as:
            - 'Lyrics go to NLP model'
            - '6 swear words or less'
            - 'Too many swear words'
        """
        text_lower = text.lower()
        
        profanity_pl = self._count_occurrences(text_lower, self.profanity_pl_automaton)
        profanity_en = self._count_occurrences(text_lower, self.profanity_en_automaton)
        
        total_count = sum(profanity_pl.values()) + sum(profanity_en.values())
        
        if total_count == 0:
            return "Lyrics go to NLP model"
        elif total_count <= 6 and not profanity_pl:
            return "6 swear words or less"
        else:
            return "Too many swear words"

    def _count_occurrences(self, text: str, automaton: Automaton) -> Dict[str, int]:
        """
        Counts occurrences of words from an Aho-Corasick automaton in the text.

        Parameters
        ----------
        text : str
            The text in which profanity words will be counted.
        automaton : Automaton
            The Aho-Corasick automaton to be used for matching words.

        Returns
        -------
        Dict[str, int]
            A dictionary with profanity words as keys and their counts as values.
        """
        counts = {}
        for end_index, word in automaton.iter(text):
            start_index = end_index - len(word) + 1
            if self._is_whole_word(text, start_index, end_index):
                counts[word] = counts.get(word, 0) + 1
        return counts

    @staticmethod
    def _is_whole_word(text: str, start: int, end: int) -> bool:
        """
        Checks if a matched word is a whole word in the text.

        Parameters
        ----------
        text : str
            The text in which to check for whole words.
        start : int
            The start index of the matched word.
        end : int
            The end index of the matched word.

        Returns
        -------
        bool
            True if the match is a whole word, False otherwise.
        """
        before = text[start - 1] if start > 0 else ' '
        after = text[end + 1] if end < len(text) - 1 else ' '
        return not (before.isalnum() or after.isalnum())

    def _load_words_into_automaton(self, filename: str, automaton: Automaton) -> None:
        """
        Loads profanity words from a file into an Aho-Corasick automaton.

        Parameters
        ----------
        filename : str
            The path to the file containing profanity words.
        automaton : Automaton
            The Aho-Corasick automaton into which words will be loaded.

        Raises
        ------
        TextAnalysisError
            If there is an error loading the file or the words into the automaton.
        """
        try:
            with open(filename, "r", encoding='utf-8') as file:
                for line in file:
                    word = line.strip().lower()
                    automaton.add_word(word, word)
            automaton.make_automaton()
        except Exception as e:
            logger.error(f"Error loading profanity file {filename}: {e}")
            raise