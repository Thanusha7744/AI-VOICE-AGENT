# 🎙️ AI Voice Agent - 30 Days Challenge (Day 1 to Day 13)

---

## 📌 About the Project
This repository documents my journey through the **30 Days of AI Voice Agents Challenge**, where I built a complete **voice-based conversational AI** from scratch using **Python, FastAPI, Murf AI, AssemblyAI, and Google Gemini**.

The AI Voice Agent can:
- Listen to the user's **voice**
- Convert it into text using **Speech-to-Text (STT)**
- Process it with a **Large Language Model (LLM)**
- Reply back in a **natural AI-generated voice**
- Maintain **context across the conversation**
- Handle **errors gracefully** with fallback responses
- Offer a clean, responsive **web interface**

---

## 🎯 Features Implemented (Days 1–13)
- **🎤 Voice Recording** — Record user audio from the browser
- **🗣 Text-to-Speech (TTS)** using Murf AI
- **📝 Speech-to-Text (STT)** using AssemblyAI
- **🧠 AI Responses** using Google Gemini API
- **🔄 Full Voice-to-Voice Pipeline**
- **💬 Conversation Memory** (chat history)
- **⚠ Error Handling** with fallback voice responses
- **🎨 UI Improvements** with interactive record button
- **📚 Documentation** explaining every step

---

## 🛠 Tech Stack

### **Backend**
- **Python 3.x**
- **FastAPI** — REST API framework
- **Murf AI API** — Text-to-Speech
- **AssemblyAI API** — Speech-to-Text
- **Google Gemini API** — LLM

### **Frontend**
- **HTML5** — Structure
- **CSS3** — Styling
- **JavaScript (ES6)** — API calls and logic
- **MediaRecorder API** — Voice recording
- **HTML `<audio>` element** — Audio playback

### **Tools**
- **Postman / FastAPI Docs** — API testing
- **.env** — API key security
- **Git & GitHub** — Version control

---

## 📂 Folder Structure

voice-agent/
│
├── backend/
│ ├── main.py # FastAPI backend with endpoints
│ ├── requirements.txt # Python dependencies
│ ├── .env # API keys (ignored in GitHub)
│ ├── uploads/ # Temporary audio storage
│ └── utils/
│ ├── tts_service.py # Murf API TTS logic
│ ├── stt_service.py # AssemblyAI STT logic
│ ├── llm_service.py # Gemini API logic
│ └── chat_history.py # Conversation memory logic
│
├── frontend/
│ ├── index.html # Main UI
│ ├── script.js # Recording & API interaction
│ ├── styles.css # UI styling
│
├── README.md # Documentation
└── .gitignore # Ignore sensitive files



---

## 📅 Day-by-Day Development Journey

### **Day 1: Project Setup**
- Set up **FastAPI** backend.
- Created `index.html` and `script.js`.
- Served HTML from backend.
- Verified server runs locally.

---

### **Day 2: Your First REST TTS Call**
- Created `/generate` endpoint.
- Integrated **Murf AI API** for Text-to-Speech.
- Returned generated audio URL.
- Tested with FastAPI docs & Postman.

---

### **Day 3: Playing Back TTS Audio**
- Added text input + submit button.
- On submit → sent text to `/generate`.
- Played audio from returned URL in `<audio>`.

---

### **Day 4: Echo Bot v1**
- Implemented **MediaRecorder API**.
- Added "Start" and "Stop" recording buttons.
- Played back recorded audio locally.

---

### **Day 5: Send Audio to the Server**
- Built `/upload` endpoint.
- Uploaded audio file from frontend to backend.
- Saved files temporarily in `/uploads`.
- Returned metadata (name, type, size).

---

### **Day 6: Server-Side Transcription**
- Integrated **AssemblyAI** STT API.
- Created `/transcribe/file` endpoint.
- Sent audio directly for transcription.
- Displayed transcription in UI.

---

### **Day 7: Echo Bot v2**
- Created `/tts/echo` endpoint.
- Flow: Audio → STT → Murf TTS → Play AI voice.
- First time replacing recorded audio with AI voice.

---

### **Day 8: Integrating an LLM**
- Added `/llm/query` endpoint.
- Sent text to **Google Gemini API**.
- Returned AI-generated text.

---

### **Day 9: Full Non-Streaming Pipeline**
- Updated `/llm/query` to accept **audio input**.
- Flow: Audio → STT → LLM → TTS → Play.
- Achieved **voice-to-voice AI conversation**.

---

### **Day 10: Chat History**
- Created `/agent/chat/{session_id}` endpoint.
- Stored messages in a session-based dictionary.
- Allowed multi-turn conversations with context.
- Session ID stored in frontend URL.

---

### **Day 11: Error Handling**
- Added backend try-except for all API calls.
- Added frontend error handling for API failures.
- Fallback voice: *"I'm having trouble connecting right now."*

---

### **Day 12: UI Revamp**
- Removed old Echo Bot and TTS demo sections.
- Kept only conversational bot interface.
- Combined start/stop into one button with animations.
- Improved styling for better UX.

---

### **Day 13: Documentation**
- Created **README.md** with:
  - Project overview
  - Features
  - Tech stack
  - Folder structure
  - Detailed day-by-day progress
  - Setup instructions

---

## ⚙ How to Run Locally

### 1️⃣ - Clone the Repository

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>

2️⃣ - Install Backend Dependencies

cd backend
pip install -r requirements.txt

3️⃣ - Create .env File

MURF_API_KEY=your_murf_api_key
ASSEMBLYAI_API_KEY=your_assemblyai_api_key
GEMINI_API_KEY=your_gemini_api_key

4️⃣ - Start Backend Server
uvicorn main:app --reload

5️⃣ - Open Frontend
Open frontend/index.html in browser.
Or serve it via FastAPI static file serving.

 ARCHITECTURE FLOW: 
 
User Speaks (Voice)
      ↓
[Frontend] MediaRecorder API
      ↓
Send Audio to Backend
      ↓
[Backend - FastAPI]
  → AssemblyAI (Speech-to-Text)
  → Google Gemini (LLM)
  → Murf AI (Text-to-Speech)
      ↓
Return Audio URL
      ↓
[Frontend] Play AI Voice in <audio>