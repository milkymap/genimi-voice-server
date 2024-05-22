# API Server Project

This project provides an API server with endpoints for speech-to-text transcription, text-to-speech conversion, and text comparison using Levenshtein distance. The server is built using FastAPI and integrates with OpenAI's services.

## Prerequisites

- Docker
- Python 3.9+
- Pip

## Setup Instructions

### Using Docker

1. **Build Docker Image**

   ```bash
    docker build -t genimi:0.0 -f Dockerfile .
    docker run --rm --name genimi -it -e OPENAI_API_KEY=sk-XXX -p 8000:8000 genimi:0.0 --host '0.0.0.0' --port 8000
    ```
