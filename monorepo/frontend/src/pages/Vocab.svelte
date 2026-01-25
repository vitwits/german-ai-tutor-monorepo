<script>
  import { onMount } from "svelte";
  import api from "../lib/api";
  
  let words = [];
  let loading = false;
  let viewMode = 'list'; // 'list' or 'grid'
  
  // Flashcard Session State
  let showSession = false;
  let sessionCards = [];
  let currentCardIdx = 0;
  let isFlipped = false;
  let sessionMode = 'review'; // 'study' (auto) or 'review' (manual rating)

  async function loadVocab() {
    loading = true;
    try {
        const res = await api.get('/vocab');
        words = res.data.items;
    } catch (e) {
        console.error(e);
    } finally {
        loading = false;
    }
  }

  async function startSession() {
    loading = true;
    try {
        const res = await api.get('/vocab/session?limit=20');
        sessionCards = res.data;
        if (sessionCards.length > 0) {
            showSession = true;
            currentCardIdx = 0;
            isFlipped = false;
        } else {
            alert("No words to review!");
        }
    } catch (e) {
        console.error(e);
    } finally {
        loading = false;
    }
  }

  function flipCard() {
    isFlipped = !isFlipped;
  }

  async function rateCard(rating) {
    const card = sessionCards[currentCardIdx];
    try {
        await api.post('/vocab/update_progress', { id: card.id, rating });
        nextCard();
    } catch (e) {
        console.error(e);
    }
  }

  function nextCard() {
    isFlipped = false;
    if (currentCardIdx < sessionCards.length - 1) {
        currentCardIdx++;
    } else {
        alert("Session complete!");
        showSession = false;
        loadVocab(); // Refresh list
    }
  }

  function playAudio(url) {
      if(url) new Audio(url).play();
  }

  onMount(loadVocab);
</script>

{#if showSession}
    <!-- FLASHCARD OVERLAY -->
    <div class="session-overlay">
        <div class="session-header">
            <span>{currentCardIdx + 1} / {sessionCards.length}</span>
            <button class="btn-text" on:click={() => showSession = false}>Exit</button>
        </div>

        <div class="flashcard-container" 
             on:click={flipCard} 
             on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && flipCard()}
             role="button" 
             tabindex="0"
             aria-label="Flashcard, tap to flip">
            <div class="flashcard {isFlipped ? 'flipped' : ''}">
                <div class="front">
                    <div class="word">{sessionCards[currentCardIdx].display}</div>
                    <div class="hint">Tap to flip</div>
                    <button class="btn-audio" on:click|stopPropagation={() => playAudio(sessionCards[currentCardIdx].audio_de_url)}>
                        <span class="material-symbols-outlined">volume_up</span>
                    </button>
                </div>
                <div class="back">
                    <div class="trans">{sessionCards[currentCardIdx].trans}</div>
                    <div class="ctx">{sessionCards[currentCardIdx].ctx}</div>
                </div>
            </div>
        </div>

        <div class="controls">
            {#if isFlipped}
                <button class="btn-rate hard" on:click={() => rateCard('hard')}>Hard</button>
                <button class="btn-rate medium" on:click={() => rateCard('medium')}>Good</button>
                <button class="btn-rate easy" on:click={() => rateCard('easy')}>Easy</button>
            {:else}
                <button class="btn-contained" on:click={flipCard}>Show Answer</button>
            {/if}
        </div>
    </div>
{:else}
    <!-- VOCAB LIST -->
    <div class="vocab-header">
        <h2>My Vocabulary</h2>
        <button class="btn-contained" on:click={startSession}>
            <span class="material-symbols-outlined">school</span> Practice
        </button>
    </div>

    <div class="vocab-list">
        {#each words as w}
            <div class="vocab-item">
                <div class="v-main">
                    <div class="v-word">{w.display}</div>
                    <div class="v-trans">{w.ua || w.en}</div>
                </div>
                <div class="v-meta">
                    <span class="level-badge lvl-{w.level?.toLowerCase()}">{w.level || '?'}</span>
                </div>
            </div>
        {/each}
    </div>
{/if}

<style>
    .vocab-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .vocab-list { display: flex; flex-direction: column; gap: 8px; }
    .vocab-item { 
        background: var(--surface); padding: 12px 16px; border-radius: var(--radius);
        border: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;
    }
    .v-word { font-weight: 500; color: var(--primary); font-size: 1.1rem; }
    .v-trans { font-size: 0.9rem; opacity: 0.8; }

    /* Flashcard Styles */
    .session-overlay {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: var(--bg); z-index: 2000; display: flex; flex-direction: column;
    }
    .session-header { padding: 20px; display: flex; justify-content: space-between; }
    
    .flashcard-container {
        flex: 1; perspective: 1000px; display: flex; align-items: center; justify-content: center; padding: 20px;
    }
    .flashcard {
        width: 100%; max-width: 400px; height: 300px; position: relative;
        transform-style: preserve-3d; transition: transform 0.6s; cursor: pointer;
    }
    .flashcard.flipped { transform: rotateY(180deg); }
    
    .front, .back {
        position: absolute; width: 100%; height: 100%; backface-visibility: hidden;
        background: var(--surface); border: 1px solid var(--border); border-radius: 20px;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1); text-align: center; padding: 20px; box-sizing: border-box;
    }
    .back { transform: rotateY(180deg); }

    .word { font-size: 2.5rem; font-weight: 700; margin-bottom: 10px; }
    .hint { opacity: 0.5; font-size: 0.9rem; margin-top: 20px; }
    .trans { font-size: 2rem; color: var(--primary); margin-bottom: 20px; }
    .ctx { font-style: italic; opacity: 0.8; }

    .controls { padding: 40px; display: flex; justify-content: center; gap: 20px; }
    
    .btn-rate {
        padding: 12px 24px; border: none; border-radius: 8px; color: white; font-weight: 600; cursor: pointer;
    }
    .hard { background: #F44336; }
    .medium { background: #FFC107; color: black; }
    .easy { background: #4CAF50; }

    .btn-audio {
        background: none; border: 1px solid var(--border); border-radius: 50%; width: 40px; height: 40px;
        display: flex; align-items: center; justify-content: center; margin-top: 20px; cursor: pointer;
        color: var(--primary);
    }

    .level-badge { padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; color: white; }
    .lvl-a1 { background-color: #8BC34A; } .lvl-a2 { background-color: #4CAF50; }
    .lvl-b1 { background-color: #29B6F6; } .lvl-b2 { background-color: #1976D2; }
    .lvl-c1 { background-color: #D32F2F; } .lvl-c2 { background-color: #311B92; }
</style>