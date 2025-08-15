from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import requests
import shutil
import os
import time

app = FastAPI()

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ASSEMBLYAI_API_KEY = "1cd829cc230f428a849024ced476a0c5"
MURF_API_KEY = "ap2_a40dfb61-2d11-4881-8a1e-b11ef0722b4b"

ASSEMBLYAI_HEADERS = {
    "authorization": ASSEMBLYAI_API_KEY,
    "content-type": "application/json"
}

MURF_HEADERS = {
    "accept": "application/json",
    "Content-Type": "application/json",
    "api-key": MURF_API_KEY
}

@app.post("/tts/echo/")
async def echo_bot(file: UploadFile = File(...)):
    try:
        # Save uploaded audio temporarily
        temp_filename = f"temp_{int(time.time())}.webm"
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Upload audio to AssemblyAI
        with open(temp_filename, "rb") as f:
            upload_resp = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers={"authorization": ASSEMBLYAI_API_KEY},
                data=f
            )
        if upload_resp.status_code != 200:
            os.remove(temp_filename)
            return JSONResponse(status_code=500, content={"error": "Upload failed", "details": upload_resp.text})

        upload_url = upload_resp.json().get("upload_url")
        if not upload_url:
            os.remove(temp_filename)
            return JSONResponse(status_code=500, content={"error": "Upload URL missing in response"})

        # Start transcription request
        transcript_resp = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            headers=ASSEMBLYAI_HEADERS,
            json={"audio_url": upload_url}
        )
        if transcript_resp.status_code != 200:
            os.remove(temp_filename)
            return JSONResponse(status_code=500, content={"error": "Transcription start failed", "details": transcript_resp.text})

        transcript_id = transcript_resp.json().get("id")
        if not transcript_id:
            os.remove(temp_filename)
            return JSONResponse(status_code=500, content={"error": "Transcript ID missing in response"})

        poll_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"

        # Poll transcription status
        transcript_text = None
        for _ in range(20):
            poll_resp = requests.get(poll_url, headers=ASSEMBLYAI_HEADERS)
            poll_json = poll_resp.json()
            status = poll_json.get("status")
            if status == "completed":
                transcript_text = poll_json.get("text", "")
                break
            elif status == "error":
                os.remove(temp_filename)
                return JSONResponse(status_code=500, content={"error": poll_json.get("error")})
            time.sleep(3)

        os.remove(temp_filename)

        if not transcript_text:
            return JSONResponse(status_code=504, content={"error": "Transcription timed out."})

        # Call Murf TTS API with transcript text
        murf_payload = {
            "voiceId": "en-US-male",
            "text": transcript_text,
            "format": "MP3"
        }

        murf_response = requests.post(
            "https://api.murf.ai/v1/speech/generate",
            headers=MURF_HEADERS,
            json=murf_payload
        )

        if murf_response.status_code != 200:
            return JSONResponse(status_code=500, content={"error": "Murf API failed", "details": murf_response.text})

        murf_json = murf_response.json()
        audio_url = murf_json.get("audioFile")
        if not audio_url:
            return JSONResponse(status_code=500, content={"error": "No audio file returned from Murf"})

        # Download Murf audio file
        mp3_path = "murf_output.mp3"
        audio_data = requests.get(audio_url)
        with open(mp3_path, "wb") as f:
            f.write(audio_data.content)

        # Return URL to play audio
        return {"audio_file": "/play-audio", "transcript": transcript_text}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Unexpected error", "details": str(e)})

@app.get("/play-audio")
async def play_audio():
    mp3_path = "murf_output.mp3"
    if os.path.exists(mp3_path):
        return FileResponse(mp3_path, media_type="audio/mpeg")
    return JSONResponse(status_code=404, content={"error": "Audio file not found"})

@app.get("/index.html", response_class=HTMLResponse)
async def get_index():
    file_path = "index.html"
    if not os.path.exists(file_path):
        return HTMLResponse(content="<h1>index.html not found</h1>", status_code=404)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error reading index.html</h1><pre>{e}</pre>", status_code=500)

@app.get("/", response_class=HTMLResponse)
async def root():
    file_path = "index.html"
    if not os.path.exists(file_path):
        return HTMLResponse(content="<h1>index.html not found</h1>", status_code=404)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error reading index.html</h1><pre>{e}</pre>", status_code=500)