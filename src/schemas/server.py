
from pydantic import BaseModel

class Transcription(BaseModel):
    text:str 
    voice:str='alloy'
    chunk_size:int=65536