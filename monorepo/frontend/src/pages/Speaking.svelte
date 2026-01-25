<script>
  import { onMount, onDestroy } from "svelte";
  import api from "../lib/api";
  import { addToast } from "../stores/toast";

  let sentence = null;
  let isFav = false;
  let loading = true;
  
  // State
  let isRecording = false;
  let isProcessing = false;
  let result = null; // { average_score, pronunciation_score, ... }
  
  // Audio Logic
  let mediaRecorder = null;
  let audioChunks = [];
  let audioContext = null;
  let analyser = null;
  let micStream = null;
  let silenceInterval = null;
  let visualizerScale = 1;
  let animationFrameId = null;

  // Silence Detection Config
  const NOISE_LEVEL = 15;
  const SILENCE_AFTER_SPEECH = 2000;
  const MAX_RECORD_TIME = 8000;
  let lastVoiceTime = 0;
  let hasSpoken = false;
  let startTime = 0;

  async function loadNext() {
    loading = true;
    result = null;
    try {
      const res = await api.get("/speaking/next");
      if (res.data.error) {
        addToast(res.data.error, "error");
        return;
      }
      sentence = res.data.sentence;
      isFav = res.data.is_fav;
      
      // Play audio automatically
      if (sentence.audio_de) {
        setTimeout(() => playAudio(sentence.audio_de), 500);
      }
    } catch (e) {
      console.error(e);
      addToast("Failed to load sentence", "error");
    } finally {
      loading = false;
    }
  }

  function playAudio(path) {
    if (!path) return;
    const url = path.startsWith("http") ? path : `/static/audio/sentences/${path}`;
    new Audio(url).play().catch(e => console.log("Audio play error", e));
  }

  async function toggleRecording() {
    if (isRecording) {
      stopRecording();
    } else {
      await startRecording();
    }
  }

  async function startRecording() {
    try {
      if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
      if (audioContext.state === 'suspended') await audioContext.resume();

      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      mediaRecorder = new MediaRecorder(micStream);
      audioChunks = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stopStream();
        if (audioChunks.length > 0 && hasSpoken) {
          const blob = new Blob(audioChunks, { type: 'audio/webm' });
          await processAudio(blob);
        } else {
          isRecording = false;
          addToast("No speech detected", "info");
        }
      };

      mediaRecorder.start();
      isRecording = true;
      hasSpoken = false;
      startTime = Date.now();
      lastVoiceTime = Date.now();

      setupVisualizer(micStream);
      startSilenceDetection();

    } catch (e) {
      console.error(e);
      addToast("Microphone access denied", "error");
    }
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    isRecording = false;
    if (silenceInterval) clearInterval(silenceInterval);
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    visualizerScale = 1;
  }

  function stopStream() {
    if (micStream) {
      micStream.getTracks().forEach(track => track.stop());
      micStream = null;
    }
  }

  function setupVisualizer(stream) {
    analyser = audioContext.createAnalyser();
    const src = audioContext.createMediaStreamSource(stream);
    src.connect(analyser);
    analyser.fftSize = 256;
    drawVisualizer();
  }

  function drawVisualizer() {
    if (!isRecording) return;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteFrequencyData(dataArray);
    
    let sum = 0;
    for(let i = 0; i < bufferLength; i++) sum += dataArray[i];
    let average = sum / bufferLength;
    
    visualizerScale = 1 + (average / 100); // Scale factor
    animationFrameId = requestAnimationFrame(drawVisualizer);
  }

  function startSilenceDetection() {
    if (silenceInterval) clearInterval(silenceInterval);
    silenceInterval = setInterval(() => {
      if (!isRecording || !analyser) return;

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      analyser.getByteFrequencyData(dataArray);
      
      let sum = 0;
      for(let i = 0; i < bufferLength; i++) sum += dataArray[i];
      let average = sum / bufferLength;

      if (average > NOISE_LEVEL) {
        if (!hasSpoken) hasSpoken = true;
        lastVoiceTime = Date.now();
      } else {
        const now = Date.now();
        if (hasSpoken && (now - lastVoiceTime > SILENCE_AFTER_SPEECH)) {
          stopRecording();
        } else if (!hasSpoken && (now - startTime > MAX_RECORD_TIME)) {
          stopRecording();
        }
      }
    }, 100);
  }

  async function processAudio(blob) {
    isProcessing = true;
    const formData = new FormData();
    formData.append('audio', blob);
    formData.append('original_text', sentence.text_de);

    try {
      const res = await api.post('/evaluate_audio', formData);
      result = res.data;
      if (result.feedback_audio_url) {
        playAudio(result.feedback_audio_url);
      }
    } catch (e) {
      console.error(e);
      addToast("Evaluation failed", "error");
    } finally {
      isProcessing = false;
    }
  }

  async function toggleFav() {
    if (!sentence) return;
    try {
      const res = await api.post('/toggle_sentence_fav', { id: sentence.id });
      isFav = res.data.is_fav;
    } catch (e) { console.error(e); }
  }

  onMount(loadNext);
  onDestroy(() => {
    stopRecording();
    stopStream();
    if (audioContext) audioContext.close();
  });
</script>

<div class="speak-container">
  {#if loading}
    <div class="loading">Loading...</div>
  {:else if sentence}
    <div class="task-text">
      {sentence.text_de}
    </div>
    
    <div class="controls-container">
      <button class="side-btn" on:click={loadNext} disabled={isRecording}>
        <span class="material-symbols-outlined">skip_next</span>
      </button>

      <div class="mic-wrapper">
        <div class="mic-ring" style="transform: scale({visualizerScale}); display: {isRecording ? 'block' : 'none'}"></div>
        <button class="mic-btn {isRecording ? 'recording' : ''} {isProcessing ? 'processing' : ''}" on:click={toggleRecording} disabled={isProcessing}>
          {#if isProcessing}
            <span class="material-symbols-outlined rotating">sync</span>
          {:else if isRecording}
            <span class="material-symbols-outlined">stop</span>
          {:else}
            <span class="material-symbols-outlined icon-play">mic</span>
          {/if}
        </button>
      </div>

      <button class="side-btn" on:click={toggleFav} style="color: {isFav ? '#FFC107' : 'inherit'}">
        <span class="material-symbols-outlined {isFav ? 'filled' : ''}">star</span>
      </button>
    </div>

    {#if result}
      <div class="result-card">
        <div class="score-circle" style="border-color: {result.average_score >= 80 ? '#4CAF50' : result.average_score >= 50 ? '#FFC107' : '#F44336'}">
          {result.average_score}
        </div>
        <div class="transcript">
          "{result.transcribed_text}"
        </div>
        <div class="stats">
          <div class="stat"><span>Pronunciation</span> <b>{result.pronunciation_score}</b></div>
          <div class="stat"><span>Accuracy</span> <b>{result.context_score}</b></div>
          <div class="stat"><span>Grammar</span> <b>{result.grammar_score}</b></div>
        </div>
      </div>
    {/if}
  {/if}
</div>

<style>
  .speak-container {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    min-height: 60vh; text-align: center;
  }
  .task-text {
    font-size: 1.5rem; font-weight: 500; margin-bottom: 40px; min-height: 4rem;
    color: var(--on-surface); padding: 0 10px;
  }
  .controls-container {
    display: flex; align-items: center; justify-content: center; gap: 20px; margin-bottom: 40px;
  }
  .mic-wrapper {
    position: relative; width: 140px; height: 140px;
    display: flex; align-items: center; justify-content: center;
  }
  .mic-btn {
    width: 100px; height: 100px; border-radius: 50%; border: none; background: var(--primary);
    color: var(--on-primary); cursor: pointer; z-index: 2;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 8px 20px rgba(25, 118, 210, 0.3); transition: all 0.2s;
  }
  .mic-btn.recording { background-color: #d32f2f; }
  .mic-btn.processing { background-color: #9E9E9E; cursor: default; }
  .mic-btn .material-symbols-outlined { font-size: 48px; }
  
  .mic-ring {
    position: absolute; width: 100px; height: 100px; border-radius: 50%;
    background: var(--primary); opacity: 0.3; z-index: 1;
    transition: transform 0.05s linear;
  }

  .side-btn {
    width: 50px; height: 50px; border-radius: 50%; border: 1px solid var(--border);
    background: var(--surface); color: var(--on-surface);
    display: flex; align-items: center; justify-content: center; cursor: pointer;
    box-shadow: var(--shadow); transition: all 0.2s;
  }
  .side-btn:active { transform: scale(0.95); }
  .filled { font-variation-settings: 'FILL' 1; }

  .result-card {
    background: var(--surface); padding: 20px; border-radius: var(--radius);
    box-shadow: var(--shadow); width: 100%; max-width: 400px;
    animation: slideUp 0.3s ease-out;
  }
  .score-circle {
    width: 60px; height: 60px; border-radius: 50%; border: 4px solid #ccc;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.5rem; font-weight: bold; margin: 0 auto 10px auto;
  }
  .transcript { font-style: italic; opacity: 0.8; margin-bottom: 15px; }
  .stats { display: flex; justify-content: space-around; font-size: 0.9rem; }
  .stat { display: flex; flex-direction: column; gap: 4px; }

  .rotating { animation: rotate 1.5s linear infinite; }
  @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
  @keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
</style>