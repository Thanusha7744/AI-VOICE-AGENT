// script.js
// -------------------- Section switching (UI) --------------------
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    btn.classList.add('active');
    const sec = document.getElementById(btn.dataset.section);
    if (sec) sec.classList.add('active');
  });
});

// -------------------- Session ID (unchanged from Day10) --------------------
const urlParams = new URLSearchParams(window.location.search);
let sessionId = urlParams.get("session_id");
if (!sessionId) {
  sessionId = Date.now().toString();
  urlParams.set("session_id", sessionId);
  const newUrl = `${location.pathname}?${urlParams.toString()}`;
  window.history.replaceState({}, "", newUrl);
}

// -------------------- Elements --------------------
// Voice Assistant
const textInput = document.getElementById("textInput");
const generateBtn = document.getElementById("generateBtn");
const statusText = document.getElementById("statusText");
const audioPlayer = document.getElementById("audioPlayer");

// EchoBot
const startRecordBtn = document.getElementById("startRecordBtn");
const stopRecordBtn = document.getElementById("stopRecordBtn");
const transcriptionText = document.getElementById("transcriptionText");
const murfAudio = document.getElementById("murfAudio");

// Gemini Voice
const geminiStart = document.getElementById("gemini-start");
const geminiStop = document.getElementById("gemini-stop");
const geminiTranscriptDiv = document.getElementById("gemini-transcript");
const geminiReplyDiv = document.getElementById("gemini-reply");
const geminiAudio = document.getElementById("geminiAudio");

// Ensure initial button states
if (stopRecordBtn) stopRecordBtn.disabled = true;
if (geminiStop) geminiStop.disabled = true;

// -------------------- Helper functions --------------------

// Speak aloud a message using Web Speech API
function speakText(message) {
  try {
    const utterance = new SpeechSynthesisUtterance(message);
    utterance.lang = "en-US";
    speechSynthesis.speak(utterance);
  } catch (e) {
    console.warn("Speech synthesis failed:", e);
  }
}

// Fallback audio helper
function playFallbackAudio(targetAudioElement = audioPlayer) {
  try {
    // Use provided audio element or default audioPlayer
    if (targetAudioElement) {
      targetAudioElement.src = "/static/fallback.mp3";
      targetAudioElement.style.display = "block";
      targetAudioElement.play().catch(e => console.warn("Fallback playback error:", e));
    } else {
      const fb = new Audio("/static/fallback.mp3");
      fb.play().catch(e => console.warn("Fallback playback error:", e));
    }
  } catch (e) {
    console.warn("playFallbackAudio failed:", e);
  }
}

// -------------------- Voice Assistant: Text -> Murf TTS (ECHO exact text) --------------------
generateBtn.addEventListener('click', async () => {
  const text = textInput.value.trim();
  if (!text) {
    alert("Please enter some text.");
    return;
  }
  statusText.textContent = "Generating voice, please wait...";
  audioPlayer.style.display = "none";
  audioPlayer.src = "";

  try {
    const res = await fetch("/voice/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    if (!res.ok) {
      const errorMessage = "There is some problem in LLM, please try again after some time.";
      statusText.textContent = errorMessage;
      speakText(errorMessage);
      playFallbackAudio(audioPlayer);
      return;
    }

    statusText.textContent = "Voice generated successfully!";
    if (data.reply) {
      console.log("Voice Assistant echoed:", data.reply);
    }

    if (data.audio_file) {
      audioPlayer.src = data.audio_file + "?t=" + Date.now(); // cache buster
      audioPlayer.style.display = "block";
      try { await audioPlayer.play(); } catch (e) {
        console.warn("Playback error:", e);
        const errorMessage = "There is some problem in LLM, please try again after some time.";
        speakText(errorMessage);
        playFallbackAudio(audioPlayer);
      }
    } else {
      const errorMessage = "There is some problem in LLM, please try again after some time.";
      statusText.textContent = errorMessage;
      speakText(errorMessage);
      playFallbackAudio(audioPlayer);
    }
  } catch (err) {
    const errorMessage = "There is some problem in LLM, please try again after some time.";
    statusText.textContent = errorMessage + " (" + err.message + ")";
    speakText(errorMessage);
    playFallbackAudio(audioPlayer);
  }
});

// -------------------- EchoBot (Voice -> STT -> Murf TTS echo) --------------------
let mediaRecorder;
let audioChunks = [];

async function startRecording() {
  transcriptionText.textContent = "Recording...";
  audioChunks = [];
  try {
    let stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.start();

    mediaRecorder.ondataavailable = e => {
      audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
      const formData = new FormData();
      formData.append("file", audioBlob, "recorded.webm");

      transcriptionText.textContent = "Uploading audio and waiting for response...";

      try {
        const response = await fetch(`/echobot/voice/${sessionId}`, {
          method: "POST",
          body: formData,
        });

        const data = await response.json();
        if (!response.ok) {
          const errorMessage = "There is some problem in LLM, please try again after some time.";
          transcriptionText.textContent = errorMessage;
          speakText(errorMessage);
          playFallbackAudio(murfAudio);
          return;
        }

        if (data.transcript) {
          transcriptionText.textContent = `Transcription: ${data.transcript}`;
        } else {
          transcriptionText.textContent = "No transcription returned.";
        }

        if (data.audio_file) {
          murfAudio.src = data.audio_file + "?t=" + Date.now();
          murfAudio.style.display = "block";

          murfAudio.onended = () => {
            transcriptionText.textContent = "Bot finished speaking. You can record again.";
          };

          try {
            await murfAudio.play();
          } catch (e) {
            console.warn("Playback error:", e);
            const errorMessage = "There is some problem in LLM, please try again after some time.";
            speakText(errorMessage);
            playFallbackAudio(murfAudio);
          }
        } else {
          const errorMessage = "There is some problem in LLM, please try again after some time.";
          speakText(errorMessage);
          playFallbackAudio(murfAudio);
        }
      } catch (err) {
        const errorMessage = "There is some problem in LLM, please try again after some time.";
        transcriptionText.textContent = errorMessage + " (" + err.message + ")";
        speakText(errorMessage);
        playFallbackAudio(murfAudio);
      }
    };

    stopRecordBtn.disabled = false;
    startRecordBtn.disabled = true;
  } catch (err) {
    const errorMessage = "There is some problem in LLM, please try again after some time.";
    transcriptionText.textContent = errorMessage + " (" + err.message + ")";
    speakText(errorMessage);
    playFallbackAudio(murfAudio);
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
    transcriptionText.textContent = "Stopped recording, processing...";
  }
  if (stopRecordBtn) stopRecordBtn.disabled = true;
  if (startRecordBtn) startRecordBtn.disabled = false;
}

if (startRecordBtn) startRecordBtn.onclick = startRecording;
if (stopRecordBtn) stopRecordBtn.onclick = stopRecording;

// -------------------- Gemini Voice (Voice -> STT -> Gemini -> Murf TTS) WITH history --------------------
let geminiRecorder;
let geminiChunks = [];

if (geminiStart) {
  geminiStart.addEventListener('click', async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      geminiRecorder = new MediaRecorder(stream);
      geminiChunks = [];
      geminiRecorder.ondataavailable = e => geminiChunks.push(e.data);
      geminiRecorder.onstop = async () => {
        const audioBlob = new Blob(geminiChunks, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("file", audioBlob, "recorded.webm");

        geminiTranscriptDiv.textContent = "Uploading audio, waiting for Gemini...";
        geminiReplyDiv.textContent = "";

        try {
          const res = await fetch(`/gemini/voice/${sessionId}`, {
            method: "POST",
            body: formData
          });

          const data = await res.json();
          if (!res.ok) {
            const errorMessage = "There is some problem in LLM, please try again after some time.";
            geminiTranscriptDiv.textContent = errorMessage;
            speakText(errorMessage);
            playFallbackAudio(geminiAudio);
            return;
          }

          geminiTranscriptDiv.textContent = data.transcript ? `Transcription: ${data.transcript}` : "";
          geminiReplyDiv.textContent = data.reply ? `Answer: ${data.reply}` : "";

          if (data.audio_file) {
            geminiAudio.src = data.audio_file + "?t=" + Date.now();
            geminiAudio.style.display = "block";
            try { await geminiAudio.play(); } catch (e) {
              console.warn("Playback error:", e);
              const errorMessage = "There is some problem in LLM, please try again after some time.";
              speakText(errorMessage);
              playFallbackAudio(geminiAudio);
            }
          } else {
            const errorMessage = "There is some problem in LLM, please try again after some time.";
            speakText(errorMessage);
            playFallbackAudio(geminiAudio);
          }
        } catch (err) {
          const errorMessage = "There is some problem in LLM, please try again after some time.";
          geminiTranscriptDiv.textContent = errorMessage + " (" + err.message + ")";
          speakText(errorMessage);
          playFallbackAudio(geminiAudio);
        } finally {
          geminiStart.disabled = false;
          geminiStop.disabled = true;
        }
      };

      geminiRecorder.start();
      geminiStart.disabled = true;
      geminiStop.disabled = false;
      geminiTranscriptDiv.textContent = "Recording...";
      geminiReplyDiv.textContent = "";
    } catch (err) {
      const errorMessage = "There is some problem in LLM, please try again after some time.";
      geminiTranscriptDiv.textContent = errorMessage + " (" + err.message + ")";
      speakText(errorMessage);
      playFallbackAudio(geminiAudio);
    }
  });

  geminiStop.addEventListener('click', () => {
    if (geminiRecorder && geminiRecorder.state !== "inactive") {
      geminiRecorder.stop();
      geminiTranscriptDiv.textContent = "Stopped recording, processing...";
    }
    geminiStop.disabled = true;
    geminiStart.disabled = false;
  });
}