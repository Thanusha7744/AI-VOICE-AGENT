import logging
import os
import shutil
import time
import requests
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from google import genai  # google-genai client

# -----------------------
# Configuration / setup
# -----------------------
load_dotenv()

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
MURF_API_KEY = os.getenv("MURF_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or "YOUR_GEMINI_API_KEY_HERE"  # replace with your key if not using .env

if not ASSEMBLYAI_API_KEY:
    raise ValueError("❌ ASSEMBLYAI_API_KEY not found in .env")
if not MURF_API_KEY:
    raise ValueError("❌ MURF_API_KEY not found in .env")
if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
    logging.getLogger("uvicorn").warning("GEMINI_API_KEY is not set. LLM calls will fail until you set it.")

ASSEMBLYAI_HEADERS = {"authorization": ASSEMBLYAI_API_KEY, "content-type": "application/json"}
MURF_HEADERS = {"accept": "application/json", "Content-Type": "application/json", "api-key": MURF_API_KEY}

# Init Gemini client if key available
if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    client = None

# Fallback audio (pre-recorded) served from static folder
FALLBACK_AUDIO_URL = "/static/fallback.mp3"

# -----------------------
# App setup
# -----------------------
app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn")

# Ensure these directories exist in your project
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------
# Helper functions (unchanged)
# -----------------------
def upload_to_assemblyai(file_path: str) -> str:
    with open(file_path, "rb") as f:
        resp = requests.post("https://api.assemblyai.com/v2/upload", headers={"authorization": ASSEMBLYAI_API_KEY}, data=f)
    if resp.status_code not in (200, 201):
        raise Exception(f"AssemblyAI upload failed: {resp.status_code} {resp.text}")
    return resp.json().get("upload_url")

def start_transcription(upload_url: str) -> str:
    resp = requests.post("https://api.assemblyai.com/v2/transcript", headers=ASSEMBLYAI_HEADERS, json={"audio_url": upload_url})
    if resp.status_code not in (200, 201):
        raise Exception(f"AssemblyAI start transcription failed: {resp.status_code} {resp.text}")
    return resp.json().get("id")

def poll_transcription(transcript_id: str, max_tries: int = 60, interval: int = 3) -> str:
    poll_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
    for _ in range(max_tries):
        r = requests.get(poll_url, headers=ASSEMBLYAI_HEADERS)
        if r.status_code != 200:
            raise Exception(f"AssemblyAI poll failed: {r.status_code} {r.text}")
        j = r.json()
        status = j.get("status")
        if status == "completed":
            return j.get("text", "")
        if status == "error":
            raise Exception(f"AssemblyAI transcription error: {j.get('error')}")
        time.sleep(interval)
    raise Exception("Transcription timed out")

def gemini_generate(prompt: str) -> str:
    if client is None:
        raise Exception("Gemini client not initialized (GEMINI_API_KEY missing)")
    resp = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt])
    return resp.text if hasattr(resp, "text") else str(resp)

def get_murf_voice_id() -> str:
    r = requests.get("https://api.murf.ai/v1/speech/voices", headers=MURF_HEADERS)
    if r.status_code != 200:
        raise Exception(f"Failed to fetch Murf voices: {r.status_code} {r.text}")
    voices = r.json()
    if not voices or not isinstance(voices, list):
        raise Exception("Unexpected voices format from Murf")
    return voices[0].get("voiceId")

def generate_murf_audio_and_save(text: str, out_path: str = "murf_output.mp3") -> str:
    # Murf accepts up to 3000 characters per request; truncate to safe limit
    if len(text) > 3000:
        logger.info("LLM response > 3000 chars, truncating for Murf (3000 chars max).")
        text = text[:3000]

    voice_id = get_murf_voice_id()
    payload = {"voiceId": voice_id, "text": text, "format": "MP3"}
    r = requests.post("https://api.murf.ai/v1/speech/generate", headers=MURF_HEADERS, json=payload)
    if r.status_code not in (200, 201):
        raise Exception(f"Murf TTS failed: {r.status_code} {r.text}")
    audio_url = r.json().get("audioFile")
    if not audio_url:
        raise Exception("Murf returned no audioFile URL")
    audio_data = requests.get(audio_url)
    if audio_data.status_code != 200:
        raise Exception(f"Failed to download Murf audio: {audio_data.status_code}")
    with open(out_path, "wb") as f:
        f.write(audio_data.content)
    return out_path

# -----------------------
# Chat history store (Day 10) — ONLY for Gemini
# -----------------------
# Structure: { session_id: [ {"role":"user","content":...}, {"role":"assistant","content":...}, ... ] }
chat_store = {}

# -----------------------
# Routes (keep Day 8 endpoints + Day 9 additions)
# -----------------------
@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/gemini")
async def gemini_get_test():
    return {"message": "GET on /gemini works! Use POST to send prompts."}

@app.post("/gemini")
async def gemini_chat(payload: dict):
    # Keep text-only Gemini endpoint for compatibility (unchanged)
    prompt = payload.get("prompt") or payload.get("text") or ""
    if not prompt:
        return JSONResponse(status_code=400, content={"error": "Prompt or text field is required"})
    try:
        text = gemini_generate(prompt)
        return {"response": text}
    except Exception as e:
        logger.exception("Failed to generate Gemini response")
        # Return error + fallback audio URL so frontend can play fallback
        return JSONResponse(status_code=500, content={"error": "Failed to generate response", "details": str(e), "audio_file": FALLBACK_AUDIO_URL})

# KEEP your existing echo endpoint (backup) - unchanged flow but improved error responses
@app.post("/tts/echo/")
async def echo_bot(file: UploadFile = File(...)):
    try:
        temp_filename = f"temp_{int(time.time())}.webm"
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # upload
        with open(temp_filename, "rb") as f:
            upload_resp = requests.post("https://api.assemblyai.com/v2/upload", headers={"authorization": ASSEMBLYAI_API_KEY}, data=f)
        if upload_resp.status_code not in (200,201):
            os.remove(temp_filename)
            return JSONResponse(status_code=500, content={"error": "Upload failed", "details": upload_resp.text, "audio_file": FALLBACK_AUDIO_URL})

        upload_url = upload_resp.json().get("upload_url")
        if not upload_url:
            os.remove(temp_filename)
            return JSONResponse(status_code=500, content={"error": "Upload URL missing", "audio_file": FALLBACK_AUDIO_URL})

        transcript_resp = requests.post("https://api.assemblyai.com/v2/transcript", headers=ASSEMBLYAI_HEADERS, json={"audio_url": upload_url})
        if transcript_resp.status_code not in (200,201):
            os.remove(temp_filename)
            return JSONResponse(status_code=500, content={"error": "Transcription start failed", "details": transcript_resp.text, "audio_file": FALLBACK_AUDIO_URL})

        transcript_id = transcript_resp.json().get("id")
        if not transcript_id:
            os.remove(temp_filename)
            return JSONResponse(status_code=500, content={"error": "Transcript ID missing", "audio_file": FALLBACK_AUDIO_URL})

        poll_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        transcript_text = None
        for _ in range(20):
            poll_resp = requests.get(poll_url, headers=ASSEMBLYAI_HEADERS)
            poll_json = poll_resp.json()
            if poll_json.get("status") == "completed":
                transcript_text = poll_json.get("text", "")
                break
            elif poll_json.get("status") == "error":
                os.remove(temp_filename)
                return JSONResponse(status_code=500, content={"error": poll_json.get("error"), "audio_file": FALLBACK_AUDIO_URL})
            time.sleep(3)

        os.remove(temp_filename)
        if not transcript_text:
            return JSONResponse(status_code=504, content={"error": "Transcription timed out.", "audio_file": FALLBACK_AUDIO_URL})

        # Murf
        try:
            voices_resp = requests.get("https://api.murf.ai/v1/speech/voices", headers=MURF_HEADERS)
            if voices_resp.status_code != 200:
                return JSONResponse(status_code=500, content={"error": "Failed to fetch voices", "details": voices_resp.text, "audio_file": FALLBACK_AUDIO_URL})
            voices = voices_resp.json()
            voice_id = voices[0].get("voiceId")
            murf_payload = {"voiceId": voice_id, "text": transcript_text, "format": "MP3"}
            murf_response = requests.post("https://api.murf.ai/v1/speech/generate", headers=MURF_HEADERS, json=murf_payload)
            if murf_response.status_code not in (200,201):
                return JSONResponse(status_code=500, content={"error": "Murf API failed", "details": murf_response.text, "audio_file": FALLBACK_AUDIO_URL})
            murf_json = murf_response.json()
            audio_url = murf_json.get("audioFile")
            if not audio_url:
                return JSONResponse(status_code=500, content={"error": "No audio file returned", "audio_file": FALLBACK_AUDIO_URL})
            mp3_path = "murf_output.mp3"
            audio_data = requests.get(audio_url)
            with open(mp3_path, "wb") as f:
                f.write(audio_data.content)
        except Exception as e:
            logger.exception("Murf TTS error in /tts/echo/")
            return JSONResponse(status_code=500, content={"error": "Murf TTS error", "details": str(e), "audio_file": FALLBACK_AUDIO_URL})

        return {"audio_file": "/play-audio", "transcript": transcript_text}
    except Exception as e:
        logger.exception("Unexpected error in /tts/echo/")
        return JSONResponse(status_code=500, content={"error": "Unexpected error", "details": str(e), "audio_file": FALLBACK_AUDIO_URL})

# -----------------------
# ECHOBOT endpoint (Voice -> STT -> Murf TTS echo) — NO history
# This replaces previous agent/chat behavior for EchoBot to prevent cross-talk
# -----------------------
@app.post("/echobot/voice/{session_id}")
async def echobot_voice(session_id: str, file: UploadFile = File(...)):
    """
    Receive audio -> STT with AssemblyAI -> TTS with Murf to speak the transcription back.
    Returns: {"transcript": "...", "audio_file": "/play-audio"}
    """
    try:
        temp_filename = f"temp_{int(time.time())}.webm"
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # STT
        try:
            upload_url = upload_to_assemblyai(temp_filename)
            transcript_id = start_transcription(upload_url)
            transcript_text = poll_transcription(transcript_id, max_tries=60, interval=3)
        except Exception as e:
            logger.exception("STT error in /echobot/voice/:")
            try:
                os.remove(temp_filename)
            except Exception:
                pass
            return JSONResponse(status_code=500, content={"error": "STT failed", "details": str(e), "audio_file": FALLBACK_AUDIO_URL})

        # TTS: Murf speaks exactly the transcript_text (echo)
        try:
            mp3_path = "murf_output.mp3"
            generate_murf_audio_and_save(transcript_text, out_path=mp3_path)
        except Exception as e:
            logger.exception("TTS error in /echobot/voice/:")
            try:
                os.remove(temp_filename)
            except Exception:
                pass
            return JSONResponse(status_code=500, content={"error": "TTS failed", "details": str(e), "audio_file": FALLBACK_AUDIO_URL})

        # cleanup
        try:
            os.remove(temp_filename)
        except Exception:
            pass

        return {"transcript": transcript_text, "audio_file": "/play-audio"}

    except Exception as e:
        logger.exception("Error in /echobot/voice/")
        return JSONResponse(status_code=500, content={"error": str(e), "audio_file": FALLBACK_AUDIO_URL})

# -----------------------
# /llm/query (Day 9) - keep unchanged for compatibility
# -----------------------
@app.post("/llm/query")
async def llm_query(request: Request, file: UploadFile = File(None)):
    """
    - If called with JSON { "text": "..."} -> generate LLM response (Day 8)
    - If called as multipart/form-data with a 'file' -> full pipeline (Day 9)
    """
    try:
        content_type = request.headers.get("content-type", "")
        # AUDIO path (multipart with file)
        if file is not None or "multipart/form-data" in content_type:
            if file is None:
                return JSONResponse(status_code=400, content={"error": "No audio file provided", "audio_file": FALLBACK_AUDIO_URL})
            # save temp file
            temp_filename = f"temp_{int(time.time())}.webm"
            with open(temp_filename, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # upload -> transcribe
            try:
                upload_url = upload_to_assemblyai(temp_filename)
                transcript_id = start_transcription(upload_url)
                transcript_text = poll_transcription(transcript_id, max_tries=60, interval=3)
            except Exception as e:
                logger.exception("STT error in /llm/query audio path")
                try:
                    os.remove(temp_filename)
                except Exception:
                    pass
                return JSONResponse(status_code=500, content={"error": "STT failed", "details": str(e), "audio_file": FALLBACK_AUDIO_URL})

            # generate LLM reply
            try:
                llm_reply = gemini_generate(transcript_text).strip()
            except Exception as e:
                logger.exception("LLM error in /llm/query audio path")
                try:
                    os.remove(temp_filename)
                except Exception:
                    pass
                return JSONResponse(status_code=500, content={"error": "LLM failed", "details": str(e), "audio_file": FALLBACK_AUDIO_URL})

            # generate Murf audio
            try:
                mp3_path = "murf_output.mp3"  # kept fixed for frontend simplicity
                generate_murf_audio_and_save(llm_reply, out_path=mp3_path)
            except Exception as e:
                logger.exception("TTS error in /llm/query audio path")
                try:
                    os.remove(temp_filename)
                except Exception:
                    pass
                return JSONResponse(status_code=500, content={"error": "TTS failed", "details": str(e), "audio_file": FALLBACK_AUDIO_URL})

            # cleanup temp
            try:
                os.remove(temp_filename)
            except Exception:
                pass

            return {"transcript": transcript_text, "llm_response": llm_reply, "audio_file": "/play-audio"}

        # TEXT path (JSON)
        data = await request.json()
        prompt = data.get("text") or data.get("prompt") or ""
        if not prompt:
            return JSONResponse(status_code=400, content={"error": "Text or prompt field is required", "audio_file": FALLBACK_AUDIO_URL})
        try:
            text = gemini_generate(prompt)
            return {"response": text}
        except Exception as e:
            logger.exception("Error in /llm/query")
            return JSONResponse(status_code=500, content={"error": str(e), "audio_file": FALLBACK_AUDIO_URL})

    except Exception as e:
        logger.exception("Error in /llm/query (outer)")
        return JSONResponse(status_code=500, content={"error": str(e), "audio_file": FALLBACK_AUDIO_URL})

# -----------------------
# Voice Assistant text endpoint (Text -> Murf TTS echo) — NO Gemini
# -----------------------
@app.post("/voice/text")
async def voice_text(payload: dict):
    """
    Accepts JSON: { "text": "..." }
    Returns: { "reply": exact_text, "audio_file": "/play-audio" }
    """
    try:
        text = payload.get("text") or payload.get("prompt") or ""
        if not text:
            return JSONResponse(status_code=400, content={"error": "Text is required", "audio_file": FALLBACK_AUDIO_URL})
        # TTS: speak exactly what was typed
        mp3_path = "murf_output.mp3"
        try:
            generate_murf_audio_and_save(text, out_path=mp3_path)
            return {"reply": text, "audio_file": "/play-audio"}
        except Exception as e:
            logger.exception("TTS error in /voice/text")
            return JSONResponse(status_code=500, content={"error": "TTS failed", "details": str(e), "audio_file": FALLBACK_AUDIO_URL})
    except Exception as e:
        logger.exception("Error in /voice/text")
        return JSONResponse(status_code=500, content={"error": str(e), "audio_file": FALLBACK_AUDIO_URL})

# -----------------------
# Gemini voice endpoint (Voice -> STT -> Gemini -> Murf TTS) — WITH history
# Stores conversation history per session_id in chat_store
# -----------------------
@app.post("/gemini/voice/{session_id}")
async def gemini_voice(session_id: str, file: UploadFile = File(...)):
    """
    Flow:
    1. Receive audio -> STT (AssemblyAI)
    2. Append user message to chat_store[session_id]
    3. Send conversation history to Gemini (joined prompt)
    4. Append assistant message to history
    5. TTS (Murf) for Gemini reply
    6. Return transcript, reply, audio_file
    """
    try:
        temp_filename = f"temp_{int(time.time())}.webm"
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # STT
        try:
            upload_url = upload_to_assemblyai(temp_filename)
            transcript_id = start_transcription(upload_url)
            transcript_text = poll_transcription(transcript_id, max_tries=60, interval=3)
        except Exception as e:
            logger.exception("STT error in /gemini/voice/")
            try:
                os.remove(temp_filename)
            except Exception:
                pass
            return JSONResponse(status_code=500, content={"error": "STT failed", "details": str(e), "audio_file": FALLBACK_AUDIO_URL})

        # Save to Gemini chat history
        if session_id not in chat_store:
            chat_store[session_id] = []
        chat_store[session_id].append({"role": "user", "content": transcript_text})

        # Build prompt from history for Gemini
        history_text = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in chat_store[session_id]])
        full_prompt = "You are a helpful assistant. Continue the conversation based on the history below.\n\n" + history_text + "\nAssistant:"

        # LLM
        try:
            llm_reply = gemini_generate(full_prompt).strip()
        except Exception as e:
            logger.exception("LLM error in /gemini/voice/")
            # append a system error reply to history to reflect failure (optional)
            chat_store[session_id].append({"role": "assistant", "content": "I'm having trouble generating a response right now."})
            try:
                os.remove(temp_filename)
            except Exception:
                pass
            return JSONResponse(status_code=500, content={"error": "LLM failed", "details": str(e), "audio_file": FALLBACK_AUDIO_URL})

        # Append assistant reply to history
        chat_store[session_id].append({"role": "assistant", "content": llm_reply})

        # TTS
        try:
            mp3_path = "murf_output.mp3"
            generate_murf_audio_and_save(llm_reply, out_path=mp3_path)
        except Exception as e:
            logger.exception("TTS error in /gemini/voice/")
            try:
                os.remove(temp_filename)
            except Exception:
                pass
            return JSONResponse(status_code=500, content={"error": "TTS failed", "details": str(e), "audio_file": FALLBACK_AUDIO_URL})

        # cleanup
        try:
            os.remove(temp_filename)
        except Exception:
            pass

        return {"transcript": transcript_text, "reply": llm_reply, "audio_file": "/play-audio"}
    except Exception as e:
        logger.exception("Error in /gemini/voice/")
        return JSONResponse(status_code=500, content={"error": str(e), "audio_file": FALLBACK_AUDIO_URL})

# -----------------------
# Serve the latest Murf audio (unchanged)
# -----------------------
@app.get("/play-audio")
async def play_audio():
    mp3_path = "murf_output.mp3"
    if os.path.exists(mp3_path):
        return FileResponse(mp3_path, media_type="audio/mpeg")
    return JSONResponse(status_code=404, content={"error": "Audio file not found", "audio_file": FALLBACK_AUDIO_URL})