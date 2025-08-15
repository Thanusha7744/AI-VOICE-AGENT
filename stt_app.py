from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import requests
import os

app = FastAPI()

# Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to ["http://127.0.0.1:5500"] for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load API keys from environment variables (secure method)
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "your_assemblyai_api_key_here")
MURF_API_KEY = os.getenv("MURF_API_KEY", "your_murf_api_key_here")

# ------------------- ROOT ROUTE -------------------
@app.get("/", response_class=HTMLResponse)
async def read_root():
    return "<h2>Speech-to-Text (STT) Service Running</h2><p>Use POST /stt to process audio.</p>"

# ------------------- SPEECH TO TEXT -------------------
@app.post("/stt")
async def speech_to_text(file: UploadFile = File(...)):
    try:
        # Save the uploaded file
        file_location = f"temp_{file.filename}"
        with open(file_location, "wb") as f:
            f.write(await file.read())

        # Upload to AssemblyAI
        upload_url = "https://api.assemblyai.com/v2/upload"
        headers = {"authorization": ASSEMBLYAI_API_KEY}
        with open(file_location, "rb") as f:
            upload_response = requests.post(upload_url, headers=headers, data=f)
        upload_url = upload_response.json()["upload_url"]

        # Request transcription
        transcript_url = "https://api.assemblyai.com/v2/transcript"
        transcript_request = {"audio_url": upload_url}
        transcript_response = requests.post(transcript_url, json=transcript_request, headers=headers)
        transcript_id = transcript_response.json()["id"]

        # Wait for transcription result
        while True:
            poll_response = requests.get(f"{transcript_url}/{transcript_id}", headers=headers).json()
            if poll_response["status"] == "completed":
                os.remove(file_location)  # cleanup temp file
                return {"text": poll_response["text"]}
            elif poll_response["status"] == "error":
                os.remove(file_location)
                return JSONResponse({"error": poll_response["error"]}, status_code=500)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ------------------- MURF AI TEXT TO SPEECH -------------------
@app.post("/tts")
async def text_to_speech(payload: dict):
    try:
        text = payload.get("text", "")
        if not text:
            return JSONResponse({"error": "Text is required"}, status_code=400)

        murf_url = "https://api.murf.ai/v1/speech/generate"
        headers = {
            "Authorization": f"Bearer {MURF_API_KEY}",
            "Content-Type": "application/json"
        }
        body = {
            "voiceId": "en-US-male",  # Example voice ID
            "text": text,
            "format": "mp3"
        }

        response = requests.post(murf_url, headers=headers, json=body)
        if response.status_code != 200:
            return JSONResponse({"error": response.text}, status_code=response.status_code)

        audio_data = response.content
        output_file = "murf_output.mp3"
        with open(output_file, "wb") as f:
            f.write(audio_data)

        return FileResponse(output_file, media_type="audio/mpeg", filename="murf_output.mp3")

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)