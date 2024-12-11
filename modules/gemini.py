from flask import Flask, jsonify, request
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import base64
import asyncio
import re
import json
import logging

logger = logging.getLogger(__name__)

class GeminiApi:
    """
    A class to interact with the Gemini generative AI model for various use cases like transcription and sentiment analysis.

    Parameters
    ----------
    api_key : str
        The API key for authenticating requests to the Gemini API.
    model : str, optional
        The model name to be used by the Gemini API (default is "gemini-1.5-flash").
    prompt : str, optional
        A system instruction to be passed to the model upon initialization (default is an empty string).
    """
    def __init__(self, api_key, model: str = "gemini-1.5-flash", prompt="") -> None:
        self.api_key = api_key
        self.model = model
        self.PROMPT = prompt
        self.model_instance = None
        self._init_model()

    def _init_model(self) -> None:
        """
        Initializes the generative model instance using the provided API key and system instruction.

        This method attempts to configure the API and initializes the generative model for subsequent usage.
        
        Raises
        ------
        Exception
            If the generative model cannot be initialized.
        """
        try:
            genai.configure(api_key=self.api_key)
            self.model_instance = genai.GenerativeModel(self.model, system_instruction=self.PROMPT)
            logger.info(f"Initialized GenerativeModel with model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize GenerativeModel: {e}")

    @staticmethod
    def audio_to_base64(file_path):

        """
        Converts an audio file to a base64 encoded string.

        Parameters
        ----------
        file_path : str
            The file path to the audio file.

        Returns
        -------
        str
            The base64 encoded representation of the audio file, or None if the file cannot be read.

        Raises
        ------
        FileNotFoundError
            If the specified audio file is not found.
        """
        try:
            with open(file_path, "rb") as audio_file:
                audio_bytes = audio_file.read()
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                logger.info(f"Converted audio file '{file_path}' to base64")
                return audio_base64
        except FileNotFoundError:
            logger.error(f"Audio file '{file_path}' not found")
        except Exception as e:
            logger.error(f"Error converting audio to base64: {e}")

class TranscriptAPI(GeminiApi):
    """
    A subclass of GeminiApi that handles the generation of transcriptions from audio files.

    Parameters
    ----------
    api_key : str
        The API key for authenticating requests to the Gemini API.
    model : str, optional
        The model name to be used by the Gemini API (default is "gemini-1.5-flash").
    prompt : str, optional
        A system instruction to be passed to the model upon initialization (default is an empty string).
    """
    def generate_response(self, song):
        """
        Generates a transcription response for the provided audio file.

        Parameters
        ----------
        song : str
            The file path to the audio file to be transcribed.

        Returns
        -------
        str
            The transcribed text from the audio file, or None if the transcription fails.

        Notes
        -----
        The method converts the provided audio file to base64 before passing it to the generative model for transcription.
        """
        try:
            logger.debug("Starting generate_response method.")
            if not self.model_instance:
                logger.warning("Model instance is not initialized.")
                return None

            logger.debug(f"Converting song '{song}' to base64.")
            base64_audio = self.audio_to_base64(song)
            if not base64_audio:
                logger.error(f"Failed to convert '{song}' to base64.")
                return None

            mime_type = "audio/mp3" if song.endswith(".mp3") else "audio/webm"
            logger.info(f"Generating response for song: {song} with mime_type: {mime_type}")

            logger.debug("Calling model_instance.generate_content.")
            response = self.model_instance.generate_content(
                [
                    {"text": "."},
                    {"mime_type": mime_type, "data": base64_audio}
                ],
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
                }
            )
            logger.debug("Model response received.")

            if response:
                logger.info("Response generated successfully.")
                return response.text
            else:
                logger.warning("No response generated.")
                return None
        except Exception as e:
            logger.error(f"Error generating response for song '{song}': {e}")
            return None

class SentimentAPI(GeminiApi):
    """
    A subclass of GeminiApi that handles the sentiment analysis of text data.

    Parameters
    ----------
    api_key : str
        The API key for authenticating requests to the Gemini API.
    model : str, optional
        The model name to be used by the Gemini API (default is "gemini-1.5-flash").
    prompt : str, optional
        A system instruction to be passed to the model upon initialization (default is an empty string).
    """
    def generate_response(self, lyrics):

        """
        Generates a sentiment analysis response for the provided song lyrics.

        Parameters
        ----------
        lyrics : str
            The text of the song lyrics to be analyzed.

        Returns
        -------
        dict
            A dictionary containing the sentiment analysis result, or None if the analysis fails.

        Notes
        -----
        The method processes the raw response from the model, extracts the relevant JSON content, 
        and returns it in a structured format.
        """
        try:
            if not self.model_instance:
                logger.warning("Model instance is not initialized.")
                return None

            logger.info("Generating sentiment response for lyrics.")
            response = self.model_instance.generate_content(
                lyrics,
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
                }
            )
            if response and response.candidates:
                json_content = response.candidates[0].content.parts[0].text
                logger.debug(f"Raw JSON content: {json_content}")

                json_content = re.sub(r'```json\s*|\s*```', '', json_content)
                match = re.search(r'\{.*?\}', json_content, re.DOTALL)
                if match:
                    json_content = match.group(0)

                result = json.loads(json_content)
                return result
            else:
                logger.warning("No valid response generated.\n response: {response[:50]}")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON content: {e}")
            return None
        except Exception as e:
            logger.error(f"Error generating sentiment response: {e}")
            return None
