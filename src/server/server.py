import asyncio
import signal 
import json 
from openai import AsyncOpenAI
from io import BytesIO
from ..settings.openai_settings import OpenAISettings
from typing_extensions import Self 
import os 
import uuid
from concurrent.futures import ThreadPoolExecutor

from ..log import logger 
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File,status,BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from typing import List 
from fastapi.middleware.cors import CORSMiddleware
from aiofiles import open as aio_open 
from ..schemas.server import Transcription,available_lang,Payload
from ..server.utils import save_file,concatenate_audios,delete_files
import Levenshtein

class APIServer:
    def __init__(self, host:str, port:int, openai_settings:OpenAISettings):
        self.openai_settings = openai_settings
        self.host = host 
        self.port = port 
        self.api = FastAPI(
            title='api-server',
            description='this server expose the next endpoints: speechtotext, texttospeech, compare_text',
            version='0.0.2',
            lifespan=self.lifespan_builder()
        )

        self.api.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.executor = ThreadPoolExecutor()
        self.api.add_api_route('/compare_texts', endpoint=self.compare_texts(), methods=['POST'])
        self.api.add_api_route('/transcription', endpoint=self.transcription(), methods=['POST'])
        self.api.add_api_route('/tts', endpoint=self.tts(), methods=['POST','GET'])
        self.api.add_api_route('/transcription-evaluation',endpoint=self.transcription_and_evaluation(),methods=['POST']) 

    def compare_texts(self):
        async def inner_handler(source:str, target:str):
            distance = Levenshtein.distance(source, target)
            length_ = max(len(source), len(target))
            score = 1 - (distance / length_)
            completion_res = await self.llm.chat.completions.create(
                messages=[
                    {
                        'role': 'system',
                        'content': 'your role is to compute a score between two words or phrases. this score must check if the word was spelled correctly. the response is a JSON with two keys: score: float number between 0 and 1 and justification: string to justify the score. use french as main language!'
                    },
                    {
                        'role': 'user',
                        'content': f'is this "{source}" the same as "{target}"'
                    }
                ],
                model=self.openai_settings.completion_model_name,
                response_format={'type': 'json_object'}
            )
            llm_score = json.loads(completion_res.choices[0].message.content)
            return JSONResponse(
                status_code=200,
                content={
                    'score': score,
                    'llm_score': llm_score}
            )
        return inner_handler

    def transcription_and_evaluation(self):
        async def inner_handler(lang:str,target:List[str],background_task:BackgroundTasks,files: List[UploadFile] = File(...)):
            task = [save_file(file) for file in files]
            result = await asyncio.gather(*task)
            target_audio = "static/"+str(uuid.uuid4())+".mp3"
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.executor,concatenate_audios,result,target_audio)
            async with aio_open(target_audio,"rb") as fp:
                bin_audio = await fp.read()
            transcription_res = await self.llm.audio.transcriptions.create(
                file=("audio.mp3", bin_audio),
                model=self.openai_settings.speech_to_text_model_name,
                language=lang,
                prompt="cet audio représente un enfant s'entraînant à apprendre des mots en français"
            )
            target = " ".join(target)
            completion_res = await self.llm.chat.completions.create(
            messages=[
                    {
                        'role': 'system',
                        'content': """Tu es assistant ton role est d'aider un enfant à apprendre sa langue (langue code: fr) la variable Try que tu vas recevoir correspond à la transanscription des mots dit par l'enfant en utilisant whisper et la variable Target correspond au vrai resultat tu dois donnés un note à l'enfant entre 0 à 100 en fonction s'il a bien trouvé tu ne dois pas prendre en compte les majuscules,les virgules et autres car le Try viens d'un transcription audio
                                la réponse est un JSON avec deux clés : score : 0 à 100 et justification : justification du score en disant les mots qui correspond et d'autres non avec une felicitation ou encouragement """
                    },
                    {
                        'role': 'user',
                        'content': f'Try:"{transcription_res.text}"\n Target:"{target}"' 
                    }
                ],
                model=self.openai_settings.completion_model_name,
                response_format={'type': 'json_object'}
            )
            llm_score = json.loads(completion_res.choices[0].message.content)
            result.append(target_audio)
            background_task.add_task(delete_files,result)
            return JSONResponse(
                status_code=200,
                content={
                    'llm_score': llm_score}
            )
        return inner_handler

    def transcription(self):
        async def inner_handler(lang:str,upload_file:UploadFile):
            if lang not in available_lang:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"this key {lang} is not available these are the ones available {available_lang}"
                )
            _, extension = upload_file.filename.split('.') 
            if extension not in ['mp3', 'wav']:
                raise HTTPException(
                    status_code=500,
                    detail=f'file extension must be one of [mp3n wav or webm]'
                    )

            bytestream = await upload_file.read()
            transcription_res = await self.llm.audio.transcriptions.create(
                file=(upload_file.filename, bytestream),
                model=self.openai_settings.speech_to_text_model_name,
                language=lang,
                prompt="cet audio représente un enfant s'entraînant à apprendre des mots en français"
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
            # async with aio_open('static/audio.wav', mode='wb') as fp:
            #     await fp.write(buffer.read())
            return StreamingResponse(buffer,media_type="audio/wav")
        return inner_handler
    
    def lifespan_builder(self):
        async def lifespan(app:FastAPI):
            yield 
        return lifespan

    async def listen(self):
        if not os.path.exists("static"):
            os.makedirs("static")
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

