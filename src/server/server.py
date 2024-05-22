import asyncio
import signal 
import json 
from openai import AsyncOpenAI
from io import BytesIO
from ..settings.openai_settings import OpenAISettings
from typing_extensions import Self 

from ..log import logger 
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from typing import List 

from aiofiles import open as aio_open 
from ..schemas.server import Transcription

import Levenshtein

class APIServer:
    def __init__(self, host:str, port:int, openai_settings:OpenAISettings):
        self.openai_settings = openai_settings
        self.host = host 
        self.port = port 
        self.api = FastAPI(
            title='api-server',
            description='this server expose the next endpoints: speechtotext, texttospeech, compare_text',
            version='0.0.1',
            lifespan=self.lifespan_builder()
        )

        self.api.add_api_route('/compare_texts', endpoint=self.compare_texts(), methods=['POST'])
        self.api.add_api_route('/transcription', endpoint=self.transcription(), methods=['POST'])
        self.api.add_api_route('/tts', endpoint=self.tts(), methods=['POST'])
    
    def compare_texts(self):
        async def inner_handler(source:str, target:str):
            distance = Levenshtein.distance(source, target)
            length_ = max(len(source), len(target))
            score = 1 - (distance / length_)
            return JSONResponse(
                status_code=200,
                content={
                    'score': score 
                }
            )
        return inner_handler
        
    def transcription(self):
        async def inner_handler(upload_file:UploadFile):
            _, extension = upload_file.filename.split('.')
            if extension not in ['mp3', 'wav']:
                raise HTTPException(
                    status_code=500,
                    detail=f'file extension must be one of [mp3n wav]'
                )
            
            bytestream = await upload_file.read()
            transcription_res = await self.llm.audio.transcriptions.create(
                file=(upload_file.filename, bytestream),
                model=self.openai_settings.speech_to_text_model_name
            )
            return transcription_res.text
        return inner_handler
    
    def tts(self):
        async def inner_handler(incoming_req:Transcription):
            tts_res = await self.llm.audio.speech.create(
                input=incoming_req.text,
                model=self.openai_settings.tts_model_name,
                voice=incoming_req.voice  
            )
            buffer = BytesIO()
            async_chunk_iterator = await tts_res.aiter_bytes(chunk_size=incoming_req.chunk_size)
            async for bytes_chunk in async_chunk_iterator:
                buffer.write(bytes_chunk)
            buffer.seek(0)
            async with aio_open('audio.wav', mode='wb') as fp:
                await fp.write(buffer.read())
            return FileResponse('audio.wav')

        return inner_handler
    
    def lifespan_builder(self):
        async def lifespan(app:FastAPI):
            yield 
        return lifespan

    async def listen(self):
        self.config = uvicorn.Config(app=self.api, host=self.host, port=self.port)
        self.server = uvicorn.Server(config=self.config)
        await self.server.serve()

    async def __aenter__(self):
        self.llm = AsyncOpenAI(api_key=self.openai_settings.api_key)
        self.mutex = asyncio.Lock()
        return self 
    
    async def __aexit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            logger.error(exc_value)
            logger.exception(traceback)
        