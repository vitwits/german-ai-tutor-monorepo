<script>
/* eslint-disable */
  import { onMount, onDestroy } from "svelte";
  import { tweened } from "svelte/motion";
  import { cubicOut } from "svelte/easing";
  import { fade } from "svelte/transition";
  import api from "../lib/api";
  import { addToast } from "../stores/toast";
  import { user } from "../stores/auth";
  import { getUI } from "../lib/ui";

  // --- STATE ---
  let loading = true;
  let sentence = null;
  
  // Interaction Phase: 'idle' -> 'playing' -> 'recording' -> 'processing' -> 'splash' -> 'feedback'
  let phase = 'idle';
  
  // Recording State
  let result = null; // { average_score, pronunciation_score, ... }
  let transcript = "";
  let correction = "";
  
  // Audio Logic
  let mediaRecorder = null;
  let audioChunks = [];
  let audioContext = null;
  let analyser = null;
  let micStream = null;
  let silenceInterval = null;
  let visualizerScale = 1;
  let animationFrameId = null;
  let currentAudioObj = null;
  let lastStopType = 'unknown'; // Track how recording was stopped

  // Silence Detection & Config
  const NOISE_LEVEL = 15;
  const SILENCE_AFTER_SPEECH = 2000; // 2s after speech
  const INITIAL_SILENCE_TIMEOUT = 5000; // 5s to start speaking
  let lastVoiceTime = 0;
  let hasSpoken = false;
  let startTime = 0;
  let noSpeechTimeoutId = null;

  // Result Splash State
  let showSplash = false;
  let splashTimer = null;
  
  // Scores (Tweened for animation)
  const scoreAvg = tweened(0, { duration: 1500, easing: cubicOut });
  const scorePron = tweened(0, { duration: 1000, easing: cubicOut });
  const scoreCont = tweened(0, { duration: 1000, easing: cubicOut });
  const scoreGram = tweened(0, { duration: 1000, easing: cubicOut });

  // UI Strings
  $: ui = getUI($user?.interface_language || 'ukr');

  // Computed Props for Source Language (Task)
  $: userLang = $user?.interface_language || 'ukr';
  $: sourceText = sentence ? (userLang === 'ukr' ? (sentence.text_uk || sentence.text_en) : sentence.text_en) : '';
  $: sourceAudio = sentence ? (userLang === 'ukr' ? (sentence.audio_uk || sentence.audio_en) : sentence.audio_en) : '';

  async function loadNext() {
    loading = true;
    showSplash = false;
    result = null;
    transcript = "";
    correction = "";
    phase = 'idle';
    
    if (currentAudioObj) {
        currentAudioObj.pause();
        currentAudioObj = null;
    }
    
    // Reset scores immediately
    scoreAvg.set(0, { duration: 0 });
    scorePron.set(0, { duration: 0 });
    scoreCont.set(0, { duration: 0 });
    scoreGram.set(0, { duration: 0 });

    try {
      const res = await api.get("/speaking/next");
      if (res.data.error) {
        addToast(res.data.error, "error");
        return;
      }
      sentence = res.data.sentence;
    } catch (e) {
      console.error(e);
      addToast("Failed to load sentence", "error");
    } finally {
      loading = false;
    }
  }

  function playAudio(path) {
    if (!path) return;
    const url = (path.startsWith("http") || path.startsWith("/")) ? path : `/static/audio/sentences/${path}`;
    if (currentAudioObj) currentAudioObj.pause();
    currentAudioObj = new Audio(url);
    currentAudioObj.play().catch(e => console.log("Audio play error", e));
    return currentAudioObj;
  }

  // --- MAIN INTERACTION HANDLER ---
  async function handleMainClick() {
    if (phase === 'idle') {
        // 1. Play Prompt (Native Language)
        phase = 'playing';
        const audio = playAudio(sourceAudio);
        if (audio) {
            audio.onended = () => {
                startRecording();
            };
        } else {
            // Fallback if no audio
            startRecording();
        }
    } else if (phase === 'playing') {
        // Skip audio
        if (currentAudioObj) currentAudioObj.pause();
        startRecording();
    } else if (phase === 'recording') {
        // 3. Stop Recording (Manual - user pressed button)
        lastStopType = 'manual';
        stopRecording();
        hasSpoken = true;
    } else if (phase === 'feedback') {
        await loadNext();
        if (sentence) handleMainClick();
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
          await processAudio(blob, lastStopType);
        } else {
          phase = 'idle'; // Reset if failed
          if (!hasSpoken && phase !== 'idle') addToast(ui.speaking_silence || "Silence detected", "info");
        }
      };

      mediaRecorder.start();
      phase = 'recording';
      hasSpoken = false;
      startTime = Date.now();
      lastVoiceTime = Date.now();

      setupVisualizer(micStream);
      startSilenceDetection();
      
      // 5s timeout for initial silence
      if (noSpeechTimeoutId) clearTimeout(noSpeechTimeoutId);
      noSpeechTimeoutId = setTimeout(() => {
          if (!hasSpoken && phase === 'recording') {
              stopRecording(); // Just stop, don't submit
              phase = 'idle';
              addToast(ui.speaking_silence || "Silence detected", "info");
          }
      }, INITIAL_SILENCE_TIMEOUT);

    } catch (e) {
      console.error(e);
      addToast("Microphone access denied", "error");
      phase = 'idle';
    }
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    if (silenceInterval) clearInterval(silenceInterval);
    if (noSpeechTimeoutId) clearTimeout(noSpeechTimeoutId);
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    visualizerScale = 1;
  }
  
  function stopAndSubmit() {
      lastStopType = 'auto'; // Auto-stopped by silence detection
      stopRecording();
      hasSpoken = true; 
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
    if (phase !== 'recording') return;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteFrequencyData(dataArray);
    
    let sum = 0;
    for(let i = 0; i < bufferLength; i++) sum += dataArray[i];
    let average = sum / bufferLength;
    
    // Scale factor: 1 + (0 to 0.6) based on volume
    visualizerScale = 1 + (average / 255) * 0.6; 
    animationFrameId = requestAnimationFrame(drawVisualizer);
  }

  function startSilenceDetection() {
    if (silenceInterval) clearInterval(silenceInterval);
    silenceInterval = setInterval(() => {
      if (phase !== 'recording' || !analyser) return;

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      analyser.getByteFrequencyData(dataArray);
      
      let sum = 0;
      for(let i = 0; i < bufferLength; i++) sum += dataArray[i];
      let average = sum / bufferLength;

      if (average > NOISE_LEVEL) {
        if (!hasSpoken) {
            hasSpoken = true;
            if (noSpeechTimeoutId) clearTimeout(noSpeechTimeoutId);
        }
        lastVoiceTime = Date.now();
      } else {
        const now = Date.now();
        if (hasSpoken && (now - lastVoiceTime > SILENCE_AFTER_SPEECH)) {
          stopAndSubmit();
        }
      }
    }, 100);
  }

  async function processAudio(blob, stopType = 'unknown') {
    phase = 'processing';
    const formData = new FormData();
    formData.append('audio', blob);
    formData.append('original_text', sentence.text_de);
    formData.append('stop_type', stopType);

    try {
      const res = await api.post('/evaluate_audio', formData);
      result = res.data;
      transcript = result.transcribed_text;
      correction = sentence.text_de; // Correct German text
      phase = 'splash';
      
      // Update energy if returned
      if (result.energy) {
        user.update(u => ({
          ...u,
          billing: {
            ...u.billing,
            energy_left: result.energy.energy_left,
            daily_spending: result.energy.daily_spending
          }
        }));
      }
      
      // Show Splash
      showSplash = true;
      
      // Animate Scores
      scoreAvg.set(result.average_score);
      scorePron.set(result.pronunciation_score);
      scoreCont.set(result.context_score);
      scoreGram.set(result.grammar_score);

      // Play Feedback Audio
      if (result.feedback_audio_url) {
        playAudio(result.feedback_audio_url);
      }

      // Auto close splash after 5s
      if (splashTimer) clearTimeout(splashTimer);
      splashTimer = setTimeout(() => {
          closeSplash();
      }, 5000);
      
      // Confetti if perfect
      if (result.average_score >= 100) {
          launchConfetti();
      }
    } catch (e) {
      console.error(e);
      addToast("Evaluation failed", "error");
      phase = 'idle';
    }
  }
  
  async function reportSentence() {
      if (!sentence) return;
      if (!confirm(ui.report_sentence + "?")) return;
      try {
          await api.post('/api/report_sentence', { id: sentence.id });
          addToast(ui.sentence_reported || "Reported", "success");
          loadNext();
      } catch(e) { console.error(e); }
  }

  function launchConfetti() {
      const colors = ['#FFC107', '#2196F3', '#4CAF50', '#F44336', '#9C27B0'];
      const container = document.getElementById('splash-screen');
      if (!container) return;
      
      for (let i = 0; i < 50; i++) {
          const el = document.createElement('div');
          el.classList.add('confetti');
          el.style.left = Math.random() * 100 + '%';
          el.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
          el.style.animation = `fall ${Math.random() * 3 + 2}s linear forwards`;
          container.appendChild(el);
      }
  }
  
  function closeSplash() {
      showSplash = false;
      phase = 'feedback';
      // Auto play correct German audio
      if (sentence && sentence.audio_de) {
          playAudio(sentence.audio_de);
      }
  }

  function repeatRound() {
      if (currentAudioObj) currentAudioObj.pause();
      phase = 'idle';
      result = null;
      transcript = "";
      correction = "";
      handleMainClick();
  }

  onMount(loadNext);
  onDestroy(() => {
    stopRecording();
    stopStream();
    if (splashTimer) clearTimeout(splashTimer);
    if (audioContext) audioContext.close();
  });
</script>

<!-- SPLASH SCREEN OVERLAY -->
{#if showSplash && result && phase === 'splash'}
<div id="splash-screen" transition:fade={{ duration: 300 }}>
    <div class="score-circle">
        <svg viewBox="0 0 140 140">
            <circle class="score-circle-bg" cx="70" cy="70" r="60"></circle>
            <circle class="score-circle-fg" cx="70" cy="70" r="60" 
                    style="stroke-dashoffset: {377 - ($scoreAvg / 100) * 377}; stroke: {$scoreAvg >= 80 ? '#4CAF50' : $scoreAvg >= 50 ? '#FFC107' : '#F44336'};">
            </circle>
        </svg>
        <span style="position: relative; z-index: 1;">{$scoreAvg.toFixed(0)}</span>
    </div>
    
    <div class="transcript">"{transcript}"</div>
    
    <div class="stats-container">
        <div class="stat-row">
            <div class="stat-label"><span>{ui.score_pronunciation}</span> <b>{$scorePron.toFixed(0)}</b></div>
            <div class="progress-bg"><div class="progress-fill" style="width: {$scorePron}%; background: #42A5F5;"></div></div>
        </div>
        <div class="stat-row">
            <div class="stat-label"><span>{ui.score_context}</span> <b>{$scoreCont.toFixed(0)}</b></div>
            <div class="progress-bg"><div class="progress-fill" style="width: {$scoreCont}%; background: #66BB6A;"></div></div>
        </div>
        <div class="stat-row">
            <div class="stat-label"><span>{ui.score_grammar}</span> <b>{$scoreGram.toFixed(0)}</b></div>
            <div class="progress-bg"><div class="progress-fill" style="width: {$scoreGram}%; background: #FFA726;"></div></div>
        </div>
    </div>
</div>
{/if}

<div class="speak-container">
  <!-- Report Button -->
  <button class="report-btn" title={ui.report_sentence} on:click={reportSentence}>
      <span class="material-symbols-outlined">flag</span>
  </button>

  <!-- Task Text Container -->
  <div id="speaking-card-container">
  {#if loading}
    <div class="loading">{ui.speaking_loading}</div>
  {:else if sentence}
    <div class="task-text">
      {sourceText}
    </div>
  {/if}
  </div>

  <div class="controls-container">
    <!-- Repeat Button -->
    <button class="side-btn {phase === 'feedback' ? 'visible' : ''}" on:click={repeatRound}>
      <span class="material-symbols-outlined">replay</span>
    </button>

    <!-- Main Mic -->
    <div class="mic-wrapper">
      <div class="mic-ring" style="transform: translate(-50%, -50%) scale({visualizerScale}); display: {phase === 'recording' ? 'block' : 'none'}"></div>
      
      <button class="mic-btn {phase === 'recording' ? 'recording' : ''} {phase === 'processing' ? 'processing' : ''}" 
              on:click={handleMainClick} disabled={phase === 'processing' || loading}>
        {#if phase === 'processing'}
          <span class="material-symbols-outlined rotating">sync</span>
        {:else if phase === 'recording'}
          <span class="material-symbols-outlined">stop</span>
        {:else if phase === 'playing'}
          <span class="material-symbols-outlined icon-play">mic</span>
        {:else}
          <span class="material-symbols-outlined icon-play">play_arrow</span>
        {/if}
      </button>
    </div>

    <!-- Feedback Area -->
    <div class="feedback-area">
        {#if phase === 'feedback'}
          <div class="user-transcript" transition:fade>{transcript}</div>
          <div class="correction-box" transition:fade>{correction}</div>
        {/if}
    </div>
  </div>
</div><style>
  .speak-container {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    min-height: 70vh; text-align: center; position: relative;
  }
  .task-text {
    font-size: 1.5rem; font-weight: 500; margin-bottom: 40px; min-height: 4rem;
    color: var(--on-surface); transition: opacity 0.3s; padding: 0 10px; display: flex; align-items: center; justify-content: center;
  }
  #speaking-card-container {
    min-height: 160px; /* Reserve space to keep button centered */
    display: flex; align-items: center; justify-content: center;
    width: 100%;
  }
  .controls-container {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 20px;
    margin-bottom: 40px;
    position: relative;
  }
  .mic-wrapper {
    position: relative; width: 168px; height: 168px; /* +20% from 140px */
    display: flex; align-items: center; justify-content: center;
  }
  .mic-btn {
    width: 120px; height: 120px; /* +20% from 100px */
    border-radius: 50%; border: none; background: var(--primary);
    color: var(--on-primary); font-size: 1.2rem; font-weight: 700; cursor: pointer;
    box-shadow: 0 8px 20px rgba(25, 118, 210, 0.3); z-index: 2; transition: transform 0.2s, background-color 0.3s;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
  }
  .mic-btn:active { transform: scale(0.95); }
  .mic-btn.recording { background-color: #d32f2f; }
  .mic-btn.processing { background-color: #9E9E9E; cursor: default; }
  
  .mic-ring {
    position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
    width: 120px; height: 120px; border-radius: 50%; background: var(--primary); opacity: 0.3;
    z-index: 1; transition: width 0.1s, height 0.1s;
  }

  .side-btn {
    width: 50px; height: 50px; border-radius: 50%; border: 1px solid var(--border);
    background: var(--surface); color: var(--on-surface);
    display: flex; align-items: center; justify-content: center; cursor: pointer;
    box-shadow: var(--shadow); transition: all 0.2s; opacity: 0; pointer-events: none;
  }
  .side-btn.visible { opacity: 1; pointer-events: auto; }
  .side-btn:active { transform: scale(0.95); }
  .filled { font-variation-settings: 'FILL' 1; }
  
  .feedback-area { width: 100%; max-width: 400px; min-height: 100px; }
  .user-transcript { font-style: italic; color: var(--on-surface); opacity: 0.8; margin-bottom: 12px; font-size: 1.2rem; }
  .correction-box {
    background: rgba(76, 175, 80, 0.1); border: 1px solid #4CAF50; color: #2E7D32;
    padding: 12px; border-radius: var(--radius); font-weight: 500; font-size: 1.2rem;
  }

  /* Unified Icon Styles */
  .icon-play {
      font-size: 48px;
      font-variation-settings: 'wght' 600;
  }
  /* Larger play icon */
  .mic-btn .icon-play {
      font-size: 72px; 
  }
  /* Standard mic/stop icon size */
  .mic-btn .material-symbols-outlined:not(.icon-play) {
      font-size: 48px;
  }

  /* Splash Screen Styles */
  #splash-screen {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(8px);
    z-index: 10000; display: flex; flex-direction: column;
    align-items: center; justify-content: center; color: white;
  }

  .score-circle {
    width: 140px; height: 140px;
    display: flex; align-items: center; justify-content: center;
    font-size: 3rem; font-weight: 700; margin-bottom: 30px;
    position: relative;
  }
  .score-circle svg {
    position: absolute; top: 0; left: 0; width: 100%; height: 100%; transform: rotate(-90deg);
  }
  .score-circle circle {
    fill: none; stroke-width: 18; stroke-linecap: round;
  }
  .score-circle-bg { stroke: #333; }
  .score-circle-fg {
    stroke-dasharray: 377; /* 2 * PI * 60 */
    transition: stroke-dashoffset 0.1s linear; /* Handled by tweened store */
  }

  .transcript { font-style: italic; opacity: 0.8; margin-bottom: 30px; font-size: 1.2rem; max-width: 80%; }
  
  .stats-container { width: 80%; max-width: 300px; margin-bottom: 40px; }
  .stat-row { margin-bottom: 16px; }
  .stat-label { display: flex; justify-content: space-between; font-size: 0.9rem; margin-bottom: 6px; opacity: 0.9; }
  .progress-bg { height: 10px; background: rgba(255,255,255,0.1); border-radius: 5px; overflow: hidden; }
  .progress-fill { height: 100%; border-radius: 5px; transition: width 0.1s linear; }

  .rotating { animation: rotate 1.5s linear infinite; }
  @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

  .report-btn {
    position: absolute; top: 0; right: 0;
    background: none; border: none; color: #d32f2f; opacity: 0.5;
    cursor: pointer; transition: opacity 0.2s; padding: 10px;
  }
  .report-btn:hover { opacity: 1; }
  
  /* Confetti */
  :global(.confetti) {
    position: absolute; width: 10px; height: 10px; top: -20px; z-index: 10001; pointer-events: none;
  }
</style>