// --- STATE ---
var isRecording = false;
var isProcessing = false;
var isResultState = false; 
var isRetryState = false;  
var isPlayingAudio = false;
var roundAborted = false;

var mediaRecorder = null;
var audioChunks = [];
var audioContext = null;
var analyser = null;
var micStream = null;

// Silence Detector Variables
var silenceCheckInterval = null;
var lastVoiceTimestamp = 0;
var hasUserStartedSpeaking = false;
var recordStartTime = 0;
var currentAudioObj = null;

var NO_SPEECH_TIMEOUT = 5000; 
var SILENCE_AFTER_SPEECH = 2000; 
var NOISE_LEVEL = 15; 

var gameStarted = false;

window.onload = async () => {
    if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert(UI.audio_not_supported);
    }
};

// HTMX Hook: When a new card is loaded
if (window.handleHtmxAfterLoad) document.body.removeEventListener('htmx:afterOnLoad', window.handleHtmxAfterLoad);
window.handleHtmxAfterLoad = function(evt) {
    if(evt.detail.target.id === 'speaking-card-container') {
        startCurrentRound();
    }
};
document.body.addEventListener('htmx:afterOnLoad', window.handleHtmxAfterLoad);

// Cleanup on navigation (HTMX)
if (window.handleHtmxBeforeSwap) document.body.removeEventListener('htmx:beforeSwap', window.handleHtmxBeforeSwap);
window.handleHtmxBeforeSwap = function(evt) {
    // Ignore partial swaps (like the speaking card itself) to preserve state between rounds
    if (evt.detail.target.id === 'speaking-card-container') return;

    stopRecording(false); // Always try to stop recording/streams
    if (silenceCheckInterval) clearInterval(silenceCheckInterval);
    
    // Stop audio playback if any
    if (currentAudioObj) {
        currentAudioObj.pause();
        currentAudioObj = null;
    }
    isPlayingAudio = false;

    // Reset game state so next visit starts fresh
    gameStarted = false;
    isResultState = false;
    isRetryState = false;
    roundAborted = false;
};
document.body.addEventListener('htmx:beforeSwap', window.handleHtmxBeforeSwap);

async function handleMainClick() {
    if (audioContext && audioContext.state === 'suspended') {
        await audioContext.resume();
    }

    // 1. Interruption Logic: Stop playback if clicked during initial reading
    if (isPlayingAudio) {
        if (currentAudioObj) {
            currentAudioObj.pause();
            currentAudioObj = null;
        }
        isPlayingAudio = false;
        roundAborted = true;
        return;
    }

    if (isRetryState) {
        startCurrentRound(); 
        return;
    }

    if (isResultState) {
        nextRound();
        return;
    }
    
    if (isProcessing) return;

    if (isRecording) {
        if (!hasUserStartedSpeaking) {
            stopRecording(false); // upload = false
        } else {
            stopRecording(true);  // upload = true
        }
        return;
    }
    
    if (!gameStarted) {
        gameStarted = true;
        startCurrentRound();
    } else {
        nextRound();
    }
}

function nextRound() {
    isResultState = false;
    isRetryState = false;
    // Trigger HTMX to load next sentence
    htmx.trigger('#speaking-card-container', 'nextSentence');
}

async function startCurrentRound() {
    const taskEl = document.getElementById('task-display');
    if (!taskEl) return;
    
    isResultState = false;
    isRetryState = false;
    roundAborted = false;

    document.getElementById('transcript-display').innerText = '';
    document.getElementById('correction-display').style.display = 'none';
    updateUIState('idle');

    // If game hasn't started (initial load or level switch), just show text and wait
    if (!gameStarted) return;

    // Play source audio
    const audioSrc = taskEl.getAttribute('data-audio-src');
    if (audioSrc) {
        isPlayingAudio = true;
        await playAudioFile(audioSrc);
        isPlayingAudio = false;
    }

    // Check if aborted
    if (roundAborted) {
        isRetryState = true;
        updateUIState('idle');
        const icon = document.getElementById('btn-icon');
        icon.innerText = 'play_arrow';
        icon.classList.add('icon-play');
        return;
    }
    
    playBeep();
    startRecording();
}

async function startRecording() {
    try {
        if (!document.getElementById('visualizer')) return;

        micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        // Check if user navigated away during permission prompt
        if (!document.getElementById('visualizer')) {
            micStream.getTracks().forEach(track => track.stop());
            return;
        }

        const options = MediaRecorder.isTypeSupported('audio/webm') ? { mimeType: 'audio/webm' } : {};
        mediaRecorder = new MediaRecorder(micStream, options);
        audioChunks = [];

        mediaRecorder.ondataavailable = event => {
            if (event.data.size > 0) audioChunks.push(event.data);
        };
        
        mediaRecorder.shouldUpload = false;

        mediaRecorder.onstop = async () => {
            if (micStream) {
                micStream.getTracks().forEach(track => track.stop());
                micStream = null;
            }
            
            if (mediaRecorder.shouldUpload) {
                const mimeType = mediaRecorder.mimeType || 'audio/webm';
                const audioBlob = new Blob(audioChunks, { type: mimeType });
                processAudioBlob(audioBlob);
            } else {
                console.log("Recording cancelled (manual or silence).");

                // Check if UI elements exist before updating
                const transDisplay = document.getElementById('transcript-display');
                const icon = document.getElementById('btn-icon');

                if (transDisplay && icon) {
                    updateUIState('idle');
                    transDisplay.innerText = UI.cancelled;
                    isRetryState = true; 
                    icon.innerText = 'refresh';
                    icon.classList.remove('icon-play');
                }
            }
        };

        mediaRecorder.start();
        isRecording = true;
        updateUIState('listening');
        initAudioAndSilenceDetector(micStream);

    } catch (e) {
        console.error(e);
        window.toast.show(UI.mic_denied, "error");
        updateUIState('idle');
    }
}

function stopRecording(upload = true) {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.shouldUpload = upload;
        mediaRecorder.stop();
    } else {
        // Force stop stream if recorder wasn't active
        if (micStream) {
            micStream.getTracks().forEach(track => track.stop());
            micStream = null;
        }
    }
    if (silenceCheckInterval) clearInterval(silenceCheckInterval);
    isRecording = false;
    
    if (upload) {
        isProcessing = true;
        updateUIState('processing');
    }
}

async function initAudioAndSilenceDetector(stream) {
    try {
        if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
        if (audioContext.state === 'suspended') await audioContext.resume();
        
        if (!isRecording) return;
        
        analyser = audioContext.createAnalyser();
        const src = audioContext.createMediaStreamSource(stream);
        src.connect(analyser);
        analyser.fftSize = 256;
        
        drawVisualizer();
        
        hasUserStartedSpeaking = false;
        lastVoiceTimestamp = Date.now();
        recordStartTime = Date.now();
        
        if (silenceCheckInterval) clearInterval(silenceCheckInterval);
        
        silenceCheckInterval = setInterval(() => {
            if (!isRecording) return;
            
            const bufferLength = analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);
            analyser.getByteFrequencyData(dataArray);
            
            let sum = 0;
            for(let i = 0; i < bufferLength; i++) sum += dataArray[i];
            let average = sum / bufferLength;
            
            if (average > NOISE_LEVEL) {
                if (!hasUserStartedSpeaking) hasUserStartedSpeaking = true;
                lastVoiceTimestamp = Date.now();
            } else {
                const now = Date.now();
                if (hasUserStartedSpeaking) {
                    if (now - lastVoiceTimestamp > SILENCE_AFTER_SPEECH) {
                        stopRecording(true); 
                    }
                } else {
                    if (now - recordStartTime > NO_SPEECH_TIMEOUT) {
                        stopRecording(false); 
                    }
                }
            }
        }, 100); 
    } catch (e) { console.error(e); }
}

async function processAudioBlob(blob) {
    const formData = new FormData();
    formData.append('audio', blob);
    
    const taskEl = document.getElementById('task-display');
    const originalText = taskEl ? taskEl.getAttribute('data-original-text') : '';
    formData.append('original_text', originalText);

    try {
        const res = await fetch('/api/evaluate_audio', { method: 'POST', body: formData });
        const rawData = await res.json();
        let result = Array.isArray(rawData) ? (rawData.length > 0 ? rawData[0] : null) : rawData;

        if (!result) throw new Error("Empty response");
        showFeedback(result);
    } catch (e) {
        console.error(e);
        showFeedback({ average_score: 0, feedback: UI.error_prefix + e.message, transcribed_text: "" });
    }
}

async function showFeedback(result) {
    isProcessing = false;
    isResultState = true; 

    const transDisplay = document.getElementById('transcript-display');
    if (transDisplay) {
        if (result.transcribed_text) {
            if (result.transcribed_text.includes('[NOISE]')) {
                transDisplay.innerText = UI.noise;
            } else {
                transDisplay.innerText = `${UI.you}: "${result.transcribed_text}"`;
            }
        } else {
            transDisplay.innerText = UI.silence;
        }
    }

    updateUIState('next');

    // --- SPLASH SCREEN LOGIC ---
    const splash = document.getElementById('splash-screen');
    const circlePath = document.getElementById('splash-circle-path');
    
    if (!splash || !circlePath) return;
    
    // Scores
    const avg = result.average_score || 0;
    const p = result.pronunciation_score || 0;
    const c = result.context_score || 0;
    const g = result.grammar_score || 0;

    // Color logic
    let color = '#f44336'; // Red
    if (avg >= 80) color = '#4CAF50'; // Green
    else if (avg >= 50) color = '#FFC107'; // Orange
    
    if (circlePath) circlePath.style.stroke = color;

    // Confetti if score >= 90
    if (avg >= 90) {
        launchConfetti();
    }

    // Show Splash
    splash.style.display = 'flex';
    // Force reflow
    void splash.offsetWidth;
    splash.style.opacity = '1';

    // Animate Circle
    const circumference = 377;
    const offset = circumference - (avg / 100) * circumference;
    setTimeout(() => {
        if (circlePath) circlePath.style.strokeDashoffset = offset;
    }, 100);

    // Animate Counter
    animateValue("splash-total", 0, avg, 1500);
    animateValue("val-pron", 0, p, 1500);
    animateValue("val-cont", 0, c, 1500);
    animateValue("val-gram", 0, g, 1500);

    // Animate Bars
    setTimeout(() => {
        const bp = document.getElementById('bar-pron');
        const bc = document.getElementById('bar-cont');
        const bg = document.getElementById('bar-gram');
        if(bp) bp.style.width = p + '%';
        if(bc) bc.style.width = c + '%';
        if(bg) bg.style.width = g + '%';
    }, 100);

    // Play Feedback Audio
    if (result.feedback_audio_url) {
        const audio = new Audio(result.feedback_audio_url);
        audio.play();
    }

    // Correction logic (shown after splash)
    const taskEl = document.getElementById('task-display');
    const corrBox = document.getElementById('correction-display');
    if (taskEl && corrBox) {
        corrBox.innerText = taskEl.getAttribute('data-original-text');
        corrBox.style.display = 'block';
    }

    // Hide Splash after 5s
    setTimeout(() => {
        splash.style.opacity = '0';
        setTimeout(() => {
            splash.style.display = 'none';
            // Reset animations for next time
            if(circlePath) circlePath.style.strokeDashoffset = 377;
            
            const bp = document.getElementById('bar-pron');
            const bc = document.getElementById('bar-cont');
            const bg = document.getElementById('bar-gram');
            if(bp) bp.style.width = '0%';
            if(bc) bc.style.width = '0%';
            if(bg) bg.style.width = '0%';
            
            // Reset button state
            const btn = document.getElementById('main-btn');
            const icon = document.getElementById('btn-icon');
            btn.style.backgroundColor = 'var(--primary)';
            icon.style.display = 'block';
            icon.innerText = 'play_arrow';
            icon.classList.add('icon-play');

            // Clear confetti
            const confettis = document.querySelectorAll('.confetti');
            confettis.forEach(c => c.remove());
            
            // Play correct German audio
            const audioSrc = taskEl.getAttribute('data-audio-de');
            if(audioSrc) playAudioFile(audioSrc);
        }, 500);
    }, 4000);
}

function launchConfetti() {
    const colors = ['#FFC107', '#2196F3', '#4CAF50', '#F44336', '#9C27B0'];
    const container = document.getElementById('splash-screen');
    
    for (let i = 0; i < 50; i++) {
        const el = document.createElement('div');
        el.classList.add('confetti');
        el.style.left = Math.random() * 100 + '%';
        el.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
        el.style.animation = `fall ${Math.random() * 3 + 2}s linear forwards`;
        container.appendChild(el);
    }
}

function animateValue(id, start, end, duration) {
    const obj = document.getElementById(id);
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.innerHTML = Math.floor(progress * (end - start) + start);
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

function updateUIState(state) {
    const btn = document.getElementById('main-btn');
    const ring = document.getElementById('visualizer');
    const icon = document.getElementById('btn-icon');
    
    if (!btn || !icon || !ring) return;
    
    icon.classList.remove('rotating');
    icon.classList.remove('icon-play');

    if (state === 'listening') {
        btn.style.backgroundColor = '#d32f2f'; 
        icon.style.display = 'block'; icon.innerText = 'stop';
        ring.style.display = 'block';
    } else if (state === 'processing') {
        btn.style.backgroundColor = '#9E9E9E'; 
        ring.style.display = 'none'; icon.style.display = 'block';
        icon.innerText = 'sync'; icon.classList.add('rotating');
    } else if (state === 'next') {
        ring.style.display = 'none'; icon.style.display = 'none';
    } else {
        // IDLE / RETRY
        btn.style.backgroundColor = 'var(--primary)';
        ring.style.display = 'none'; icon.style.display = 'block';
        
        if (!gameStarted) {
            icon.innerText = 'play_arrow';
            icon.classList.add('icon-play');
        } else {
            icon.innerText = isRetryState ? 'refresh' : 'mic'; 
        }
    }
}

async function playAudioFile(path) {
    if(!path) return;
    if (currentAudioObj) { currentAudioObj.pause(); currentAudioObj = null; }
    
    // Handle full path or filename
    const url = path.startsWith('/') ? path : '/static/audio/sentences/' + path;
    
    currentAudioObj = new Audio(url);
    return new Promise(resolve => {
        currentAudioObj.onended = resolve; currentAudioObj.onerror = resolve;
        currentAudioObj.onpause = resolve; // Handle interruption
        currentAudioObj.play().catch(e => resolve());
    });
}

function playBeep() {
    try {
        if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
        
        const osc = audioContext.createOscillator();
        const gain = audioContext.createGain();
        osc.connect(gain);
        gain.connect(audioContext.destination);
        osc.frequency.value = 600;
        gain.gain.value = 0.1;
        osc.start();
        setTimeout(() => osc.stop(), 150);
    } catch(e) { console.error("Beep error", e); }
}

function drawVisualizer() {
    if (!isRecording) return;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteFrequencyData(dataArray);
    let sum = 0;
    for(let i = 0; i < bufferLength; i++) sum += dataArray[i];
    let average = sum / bufferLength;
    const scale = 1 + (average / 150); 
    const ring = document.getElementById('visualizer');
    if (!ring) return;
    ring.style.transform = `translate(-50%, -50%) scale(${scale})`;
    requestAnimationFrame(drawVisualizer);
}

if (window.handleLevelUpdated) window.removeEventListener('level-updated', window.handleLevelUpdated);

var levelUpdateTimer = null;

window.handleLevelUpdated = async () => {
    // Debounce: якщо функція викликана повторно протягом 100мс, скасовуємо попередній виклик
    if (levelUpdateTimer) clearTimeout(levelUpdateTimer);

    levelUpdateTimer = setTimeout(() => {
        // 1. Hard stop recording if active
        if (isRecording && mediaRecorder) {
            mediaRecorder.onstop = null; 
            mediaRecorder.stop();
            if(micStream) micStream.getTracks().forEach(track => track.stop());
        }
        if (silenceCheckInterval) clearInterval(silenceCheckInterval);
        
        // 2. Reset State
        isRecording = false;
        isProcessing = false;
        isResultState = false;
        isRetryState = false;
        gameStarted = false;
        
        // 3. Reset UI
        updateUIState('idle');
        const transDisplay = document.getElementById('transcript-display');
        if (transDisplay) transDisplay.innerText = '';
        
        const corrDisplay = document.getElementById('correction-display');
        if (corrDisplay) corrDisplay.style.display = 'none';
        
        // 4. Trigger HTMX to load new content
        // Використовуємо htmx.ajax для прямого контролю
        htmx.ajax('GET', '/speaking/next', {target: '#speaking-card-container', swap: 'innerHTML'});
    }, 100);
};

window.addEventListener('level-updated', window.handleLevelUpdated);