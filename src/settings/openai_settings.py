

from pydantic_settings import BaseSettings
from pydantic import Field 

class OpenAISettings(BaseSettings):
    api_key:str=Field(validation_alias='OPENAI_API_KEY')
    tts_model_name:str=Field(default='tts-1', validation_alias='TTS_MODEL_NAME')
    completion_model_name:str=Field(default='gpt-4o', validation_alias='COMPLETION_MODEL_NAME')
    speech_to_text_model_name:str=Field(default='whisper-1', validation_alias='SPEECH_TO_TEXT_MODEL_NAME')