import aiofiles
from fastapi import UploadFile 
import uuid
from pydub import AudioSegment
import os

async def save_file(file:UploadFile):
    filename = str(uuid.uuid4())+file.filename
    async with aiofiles.open(f"static/{filename}", 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)  
    return f"static/{filename}"

def concatenate_audios(audio_files, output_file):
    silence = AudioSegment.silent(duration=1000)
    combined = AudioSegment.empty()
    for audio_file in audio_files:
        audio = AudioSegment.from_file(audio_file)
        combined += audio + silence
    combined.export(output_file, format="mp3")

def delete_files(file_paths):
    for file_path in file_paths:
        try:
            os.remove(file_path)
            print(f"Deleted file: {file_path}")
        except FileNotFoundError:
            print(f"File not found: {file_path}")
        except PermissionError:
            print(f"Permission denied: {file_path}")
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")