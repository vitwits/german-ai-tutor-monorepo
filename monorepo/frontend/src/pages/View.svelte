<script>
  import { onMount, onDestroy, tick } from "svelte";
  import api from "../lib/api";
  import { user } from "../stores/auth";
  import { router } from "tinro";
  import { addToast } from "../stores/toast";
  import { getUI } from "../lib/ui";

  export let id; 

  let text = null;
  let sentences = [];
  let vocab = [];
  let vocabMap = {};
  let quizData = [];
  let loading = true;
  
  // UI State
  let activeTab = 'vocab'; // 'vocab' or 'quiz'
  let showTrans = false;
  let isPlayingAll = false;
  let playingIndex = -1; // Index of sentence currently playing in Play All
  let currentAudio = null;
  
  // Quiz State
  let currentQIndex = 0;
  let quizScore = 0;
  let quizActive = false;
  let quizFinished = false;
  let selectedOptionIndex = null;
  let isChecked = false;
  let lastQuizResult = null;
  let scorePct = 0; // Для анімації

  // Popups
  let showPopup = false;
  let popupStyle = "";
  let selectedText = "";
  let selectionContext = "";
  let selectionSentenceIndex = -1;
  let selectionStartIndex = -1;

  let showLearnedPopup = false;
  let learnedPopupContent = "";
  let learnedPopupStyle = "";
  let hideTimeout;

  // Grammar Cache
  let grammarCache = {};

  // Reactive UI strings
  $: ui = getUI($user ? $user.interface_language : 'ukr');
  $: ui = getUI($user?.interface_language || 'ukr');

  async function loadText() {
    loading = true;
    try {
      const res = await api.get(`/texts/${id}`);
      text = res.data.text;
      vocab = res.data.vocab || [];
      
      // Build Vocab Map for quick lookup
      vocab.forEach(v => vocabMap[v.id] = v);

      // Parse Content
      const rawSentences = JSON.parse(text.content_json);
      
      // Parse Quiz
      if (text.quiz_json) {
        try { quizData = JSON.parse(text.quiz_json); } catch(e) {}
      }

      // Process sentences for highlighting
      sentences = rawSentences.map((s, idx) => {
        const originalText = s.de;
        const sentVocab = vocab.filter(v => v.sentence_index === idx);
        
        // Сортуємо у зворотному порядку (від кінця до початку), 
        // щоб вставка тегів не зсувала індекси для попередніх слів
        sentVocab.sort((a, b) => (b.start_index || 0) - (a.start_index || 0));
        
        let lastIdx = originalText.length;
        let html = "";
        
        sentVocab.forEach(v => {
            const start = v.start_index;
            const end = v.end_index;
            
            // Перевіряємо валідність індексів
            if (start !== null && start >= 0 && end <= originalText.length && start < end) {
                // Додаємо текст ПІСЛЯ слова
                html = originalText.substring(end, lastIdx) + html;
                // Додаємо саме слово в обгортці
                const wordVal = originalText.substring(start, end);
                html = `<span class="learned" data-wid="${v.id}">${wordVal}</span>` + html;
                lastIdx = start;
            }
        });
        
        // Додаємо початок речення
        html = originalText.substring(0, lastIdx) + html;

        // Determine translation based on user language
        // const userLang = $user ? $user.interface_language : 'ukr';
        const userLang = $user?.interface_language || 'ukr';
        // Fallback logic: try target lang, then english, then whatever is available
        let transText = s.uk;
        if (userLang !== 'ukr') transText = s.en || s.uk;
        if (!transText) transText = s.en || s.uk;

        return { ...s, de_html: html, index: idx, has_grammar: false, grammar_explanation: null, display_trans: transText };
      });

    } catch (e) {
      console.error(e);
      addToast("Error loading text", "error");
      router.goto('/library');
    } finally {
      loading = false;
    }
  }

  // --- AUDIO LOGIC ---

  async function playAudio(txt, idx = -1) {
      if (currentAudio) {
          currentAudio.pause();
          currentAudio = null;
      }
      
      // If triggered manually (not Play All), reset Play All state
      if (idx !== -1 && !isPlayingAll) {
          playingIndex = -1;
      }

      try {
          const res = await api.post('/tts', { text: txt });
          return new Promise((resolve) => {
              currentAudio = new Audio(res.data.url);
              currentAudio.onended = () => {
                  currentAudio = null;
                  resolve();
              };
              currentAudio.onerror = () => {
                  currentAudio = null;
                  resolve();
              };
              currentAudio.play().catch(e => resolve());
          });
      } catch (e) {
          console.error(e);
      }
  }

  async function playAll() {
      if (isPlayingAll) {
          isPlayingAll = false;
          if (currentAudio) currentAudio.pause();
          playingIndex = -1;
          return;
      }

      isPlayingAll = true;
      
      for (let i = 0; i < sentences.length; i++) {
          if (!isPlayingAll) break;
          playingIndex = i;
          
          // Scroll to sentence
          const el = document.getElementById(`sent-${i}`);
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });

          await playAudio(sentences[i].de);
          
          if (!isPlayingAll) break;
          await new Promise(r => setTimeout(r, 600));
      }
      
      isPlayingAll = false;
      playingIndex = -1;
  }

  async function playVocabPair(de, trans) {
      if (currentAudio) currentAudio.pause();
      
      try {
          const res = await api.post('/tts_pair', { de_text: de, trans_text: trans });
          const urls = res.data.urls;
          
          for (const url of urls) {
              await new Promise(resolve => {
                  currentAudio = new Audio(url);
                  currentAudio.onended = resolve;
                  currentAudio.play().catch(resolve);
              });
              await new Promise(r => setTimeout(r, 300));
          }
      } catch (e) { console.error(e); }
  }

  // --- TRANSLATION & SELECTION ---

  function getCharOffset(container, node, offset) {
    let charCount = 0;
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    let currentNode;
    while (currentNode = walker.nextNode()) {
        if (currentNode === node) return charCount + offset;
        charCount += currentNode.length;
    }
    return -1;
  }

  function handleMouseUp(event) {
    if (event.target.closest('button') || event.target.closest('#pop') || event.target.classList.contains('learned')) return;

    const selection = window.getSelection();
    let textStr = selection.toString().trim();

    // --- AUTO-EXPAND SELECTION LOGIC (From old project) ---
    if (!selection.isCollapsed && selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        // Separator characters (everything that is NOT part of a word)
        const isSeparator = (char) => /[\s\.,!?;:()\[\]"'«»]/.test(char);
        
        const container = range.commonAncestorContainer;
        const el = container.nodeType === 3 ? container.parentElement : container;
        
        // Work only inside lesson text
        if (el.closest && el.closest('.de-text')) {
            if (range.startContainer.nodeType === 3) {
                let start = range.startOffset;
                const txt = range.startContainer.textContent;
                while (start > 0 && !isSeparator(txt[start - 1])) start--;
                range.setStart(range.startContainer, start);
            }
            if (range.endContainer.nodeType === 3) {
                let end = range.endOffset;
                const txt = range.endContainer.textContent;
                while (end < txt.length && !isSeparator(txt[end])) end++;
                range.setEnd(range.endContainer, end);
            }
            selection.removeAllRanges();
            selection.addRange(range);
            textStr = selection.toString().trim(); // Update textStr after expansion
        }
    }

    // --- WORD COUNT LIMIT ---
    const wordCount = textStr.split(/\s+/).filter(w => w.length > 0).length;
    if (wordCount > 4) {
        addToast(ui.selection_limited_toast, "warning");
        showPopup = false;
        return;
    }

    // Stop if selection hits a learned word
    if (selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        const fragment = range.cloneContents();
        if (fragment.querySelector('.learned')) {
             // Reset if crossing learned word
             showPopup = false;
             return;
        }
    }

    if (!textStr || textStr.length > 50) {
        showPopup = false;
        return;
    }

    const sentenceEl = event.target.closest('.de-line');
    if (!sentenceEl) {
        showPopup = false;
        return;
    }

    const textSpan = sentenceEl.querySelector('.de-text');
    if (!textSpan || !textSpan.contains(selection.anchorNode)) return;

    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    
    // Calculate precise index
    selectionStartIndex = getCharOffset(textSpan, range.startContainer, range.startOffset);

    // Position Popup
    const scrollTop = window.scrollY;
    const scrollLeft = window.scrollX;
    
    if (window.innerWidth > 768) {
        popupStyle = `top: ${rect.top + scrollTop - 45}px; left: ${rect.left + scrollLeft + (rect.width / 2)}px; transform: translateX(-50%);`;
    } else {
        popupStyle = `position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%); width: auto; min-width: 200px; text-align: center;`;
    }

    selectedText = textStr;
    selectionContext = sentenceEl.dataset.text;
    selectionSentenceIndex = parseInt(sentenceEl.dataset.index);
    showPopup = true;
  }

  async function quickTranslate() {
    try {
        const res = await api.post('/quick_translate', {
            text: selectedText,
            ctx: selectionContext,
            tid: id,
            sent_idx: selectionSentenceIndex,
            start_char_index: selectionStartIndex
        });

        if (res.data.ok) {
            showPopup = false;
            window.getSelection().removeAllRanges();
            addToast(ui.word_added, "success");
            loadText(); // Reload to show highlight
        } else {
            addToast(ui[res.data.error_key] || ui.translation_failed_msg, "error");
        }
    } catch (e) {
        console.error(e);
        addToast(ui.error_generic, "error");
    }
  }

  // --- GRAMMAR ---

  async function explainGrammar(idx) {
      const s = sentences[idx];
      if (s.grammar_explanation) {
          s.grammar_explanation = null; // Toggle off
          sentences = [...sentences];
          return;
      }

      // Loading state
      s.grammar_loading = true;
      sentences = [...sentences];

      try {
          const res = await api.post('/explain_grammar', {
              sentence: s.de,
              text_id: id,
              sentence_index: idx
          });
          
          // Format HTML
          let formatted = res.data.explanation.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>');
          s.grammar_explanation = formatted;
      } catch (e) {
          addToast("Failed to explain grammar", "error");
      } finally {
          s.grammar_loading = false;
          sentences = [...sentences];
      }
  }

  // --- LEARNED WORD POPUP ---

  function handleLearnedClick(e) {
      const target = e.target;
      if (target.classList.contains('learned')) {
          const wid = target.dataset.wid;
          const word = vocabMap[wid];
          if (word) {
              const rect = target.getBoundingClientRect();
              const scrollTop = window.scrollY;
              const scrollLeft = window.scrollX;
              
              const trans = $user.interface_language === 'ukr' ? word.ua : word.en;
              learnedPopupContent = `<div style="font-weight:500; color:var(--primary);">${trans}</div>`;
              
              learnedPopupStyle = `top: ${rect.top + scrollTop - 8}px; left: ${rect.left + scrollLeft + (rect.width/2)}px; transform: translate(-50%, -100%); display: block;`;
              showLearnedPopup = true;
              
              if (hideTimeout) clearTimeout(hideTimeout);
              hideTimeout = setTimeout(() => showLearnedPopup = false, 2000);
          }
      } else {
          showLearnedPopup = false;
      }
  }

  // --- QUIZ LOGIC ---

  function startQuiz() {
      activeTab = 'quiz';
      if (!quizActive && !quizFinished) {
          quizActive = true;
          currentQIndex = 0;
          quizScore = 0;
          selectedOptionIndex = null;
          isChecked = false;
      }
  }

  function selectOption(idx) {
      if (isChecked) return;
      selectedOptionIndex = idx;
  }

  function checkAnswer() {
      isChecked = true;
      const q = quizData[currentQIndex];
      if (selectedOptionIndex === q.correct_index) {
          quizScore++;
      }
  }

  function nextQuestion() {
      if (currentQIndex < quizData.length - 1) {
          currentQIndex++;
          selectedOptionIndex = null;
          isChecked = false;
      } else {
          finishQuiz();
      }
  }

  async function finishQuiz() {
      quizActive = false;
      quizFinished = true;
      scorePct = Math.round((quizScore / quizData.length) * 100);
      try {
          await api.post('/save_quiz_result', {
              text_id: id,
              score: quizScore,
              total: quizData.length
          });
      } catch(e) {}
  }

  function restartQuiz() {
      quizFinished = false;
      startQuiz();
      scorePct = 0;
  }

  // --- ACTIONS ---

  async function toggleTextFav() {
      try {
          await api.post('/toggle_text_fav', { id });
          text.is_favorite = text.is_favorite ? 0 : 1;
      } catch(e) {}
  }

  async function toggleVocabFav(wid) {
      try {
          await api.post('/toggle_fav', { id: wid });
          // Update local state
          vocab = vocab.map(v => {
              if (v.id === wid) return { ...v, is_favorite: v.is_favorite ? 0 : 1 };
              return v;
          });
      } catch(e) { console.error(e); }
  }

  async function removeWord(wid) {
      if(!confirm(ui.confirm_delete_word)) return;
      try {
          await api.post('/remove_word', { id: wid, from_vocab: false });
          // Remove highlight locally
          const sIdx = sentences.findIndex(s => s.de_html.includes(`data-wid="${wid}"`));
          if (sIdx !== -1) {
              // Reload text to refresh highlights cleanly
              loadText();
          }
          // Remove from vocab list
          vocab = vocab.filter(v => v.id !== wid);
      } catch(e) {}
  }

  onMount(loadText);
  
  // Global click listener for learned words popup
  onMount(() => {
      document.addEventListener('click', handleLearnedClick);
  });
  onDestroy(() => {
      if (typeof document !== 'undefined') document.removeEventListener('click', handleLearnedClick);
      if (currentAudio) currentAudio.pause();
  });
</script>

<div class="view-container" on:mouseup={handleMouseUp} role="button" tabindex="0">
    {#if loading}
        <div style="text-align: center; padding: 50px; opacity: 0.6;">{ui.loading}</div>
    {:else if text}
        <div class="card">
            <h1 style="font-size:1.5rem; margin:0 0 4px 0;">{JSON.parse(text.title).de}</h1>
            <h2 style="font-size: 1rem; color: var(--on-surface); opacity: 0.6; margin: 0 0 16px 0; font-weight: 400;">
                {JSON.parse(text.title)[$user.interface_language === 'ukr' ? 'ukr' : 'eng'] || ''}
            </h2>
            
            <div class="toolbar">
                <span class="level-badge lvl-{text.level.toLowerCase()}">{text.level}</span>
                
                <button class="badge-btn" on:click={() => showTrans = !showTrans}>
                    <span class="material-symbols-outlined">{showTrans ? 'visibility_off' : 'translate'}</span>
                </button>
                
                <button class="badge-btn" on:click={toggleTextFav} style="color: {text.is_favorite ? '#d32f2f' : 'inherit'}">
                    <span class="material-symbols-outlined {text.is_favorite ? 'filled' : ''}">favorite</span>
                </button>

                <button class="btn-contained" on:click={playAll} style="margin-left: auto;">
                    <span class="material-symbols-outlined">{isPlayingAll ? 'pause' : 'play_arrow'}</span> 
                    {isPlayingAll ? ui.stop : ui.play_all}
                </button>
            </div>
            
            {#each sentences as s, i}
                <div class="de-line {playingIndex === i ? 'highlight-sentence' : ''}" id="sent-{i}" data-index={i} data-text={s.de}>
                    <div style="display:flex; justify-content: space-between; align-items: center;">
                        <div style="display:flex; align-items:center; gap:12px; flex: 1;">
                            <button class="btn-text" on:click={() => playAudio(s.de, i)} style="height:32px; width:32px; padding:0; min-width:32px;">
                                <span class="material-symbols-outlined" style="font-size:20px; color:var(--primary)">volume_up</span>
                            </button>
                            <span class="de-text">{@html s.de_html}</span>
                        </div>
                        <button class="btn-text" on:click={() => explainGrammar(i)} title={ui.grammar_tooltip} style="color: var(--primary); opacity: 0.5;">
                            <span class="material-symbols-outlined">{s.grammar_loading ? 'sync' : 'quiz'}</span>
                        </button>
                    </div>
                    
                    {#if showTrans}
                        <div class="trans-row">{s.display_trans}</div>
                    {/if}
                    
                    {#if s.grammar_explanation}
                        <div class="grammar-box">{@html s.grammar_explanation}</div>
                    {/if}
                </div>
            {/each}
        </div>

        <!-- TABS -->
        <div class="tabs-container">
            <button class="tab-btn {activeTab === 'vocab' ? 'active' : ''}" on:click={() => activeTab = 'vocab'}>{ui.vocab_tab}</button>
            {#if quizData.length > 0}
                <button class="tab-btn {activeTab === 'quiz' ? 'active' : ''}" on:click={startQuiz}>{ui.quiz_tab}</button>
            {/if}
        </div>

        <!-- VOCAB TAB -->
        {#if activeTab === 'vocab'}
            <div class="vocab-view">
                {#if vocab.length === 0}
                    <div class="card" style="text-align:center; opacity:0.6;">{ui.empty_vocab_prompt}</div>
                {/if}
                {#each vocab as v}
                    <div class="vocab-item">
                        <div style="display:flex; align-items:center; gap:12px;">
                            <button class="btn-text" on:click={() => playVocabPair(v.display, $user.interface_language === 'ukr' ? v.ua : v.en)}>
                                <span class="material-symbols-outlined" style="font-size:18px;">volume_up</span>
                            </button>
                            <div>
                                <span style="font-weight: 500; color: var(--primary); font-size: 1.1rem;">{v.display}</span>
                                <div style="font-size:0.85rem; opacity:0.7; margin-top:6px;">{$user.interface_language === 'ukr' ? v.ua : v.en}</div>
                            </div>
                        </div>
                        <button class="btn-text" on:click={() => toggleVocabFav(v.id)} style="color: {v.is_favorite ? '#FFC107' : 'inherit'}; min-width: 32px; padding: 0;">
                            <span class="material-symbols-outlined {v.is_favorite ? 'filled' : ''}">star</span>
                        </button>
                        <button class="btn-text" on:click={() => removeWord(v.id)} style="color:red;">
                            <span class="material-symbols-outlined">delete</span>
                        </button>
                    </div>
                {/each}
            </div>
        {/if}

        <!-- QUIZ TAB -->
        {#if activeTab === 'quiz'}
            <div class="quiz-container">
                {#if quizFinished}
                    <div class="results-view">
                        <div class="score-circle" style="width: 160px; height: 160px; margin-bottom: 20px;">
                            <svg viewBox="0 0 160 160">
                                <circle class="score-circle-bg" cx="80" cy="80" r="69"></circle>
                                <circle class="score-circle-fg" cx="80" cy="80" r="69" style="stroke-dashoffset: {434 - (scorePct / 100) * 434}; stroke: {scorePct >= 80 ? '#4CAF50' : scorePct >= 50 ? '#FFC107' : '#f44336'};"></circle>
                            </svg>
                            <span style="font-size: 2.5rem;">{scorePct}%</span>
                        </div>
                        <div style="font-size: 1.1rem; margin-bottom: 30px; opacity: 0.8;">{ui.your_score}</div>
                        <button class="btn-contained" on:click={restartQuiz}>{ui.retry_btn}</button>
                    </div>
                {:else}
                    <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                        <div style="font-weight: 500; opacity: 0.7;">{ui.quiz_tab} {currentQIndex + 1} / {quizData.length}</div>
                    </div>
                    <div class="quiz-progress-track">
                        <div class="quiz-progress-fill" style="width: {((currentQIndex) / quizData.length) * 100}%"></div>
                    </div>
                    
                    <div class="quiz-question">{quizData[currentQIndex].question}</div>
                    
                    <div class="quiz-options">
                        {#each quizData[currentQIndex].options as opt, idx}
                            <button class="quiz-option 
                                {selectedOptionIndex === idx ? 'selected' : ''} 
                                {isChecked && idx === quizData[currentQIndex].correct_index ? 'correct' : ''}
                                {isChecked && selectedOptionIndex === idx && idx !== quizData[currentQIndex].correct_index ? 'wrong' : ''}
                                {isChecked ? 'disabled' : ''}"
                                on:click={() => selectOption(idx)}>
                                {opt}
                            </button>
                        {/each}
                    </div>

                    <div style="margin-top: 24px; display: flex; justify-content: flex-end;">
                        {#if !isChecked}
                            <button class="btn-contained" disabled={selectedOptionIndex === null} on:click={checkAnswer}>{ui.check_btn}</button>
                        {:else}
                            <button class="btn-contained" on:click={nextQuestion}>{currentQIndex < quizData.length - 1 ? ui.next_btn : ui.finish_btn}</button>
                        {/if}
                    </div>
                {/if}
            </div>
        {/if}
    {/if}

    <!-- POPUPS -->
    {#if showPopup}
        <div id="pop" style={popupStyle} on:click|stopPropagation={quickTranslate}>
            {ui.add_translation}
        </div>
    {/if}

    {#if showLearnedPopup}
        <div id="learned-pop" style={learnedPopupStyle}>
            {@html learnedPopupContent}
        </div>
    {/if}
</div>

<style>
    .view-container { max-width: 800px; margin: 0 auto; padding-bottom: 100px; position: relative; }
    
    .toolbar { display:flex; align-items:center; gap:12px; margin-bottom:24px; flex-wrap:wrap; }
    
    .de-line { padding:8px 0; border-bottom:1px solid var(--border); transition: background-color 0.3s; }
    .de-text { font-size:1.1rem; font-weight:400; line-height:1.6; }
    .highlight-sentence { background-color: rgba(255, 235, 59, 0.3); border-radius: 4px; }
    
    .trans-row { color:var(--primary); padding-left:44px; font-size:1rem; margin-top:4px; }
    
    .grammar-box {
        background-color: rgba(25, 118, 210, 0.08); 
        color: var(--on-surface);
        padding: 12px 16px; border-radius: var(--radius); margin-top: 10px;
        font-size: 0.95rem; line-height: 1.6; border-left: 4px solid var(--primary);
    }

    .badge-btn {
        padding: 4px 12px; border-radius: 4px; display: inline-flex; align-items: center; justify-content: center;
        min-width: 28px; height: 30px; border: none; background: transparent; color: var(--on-surface);
        cursor: pointer; transition: all 0.2s;
    }
    .badge-btn:hover { opacity: 0.7; }

    /* Tabs */
    .tabs-container { display: flex; width: 100%; margin-top: 30px; }
    .tab-btn {
        flex: 1; padding: 12px; background: rgba(0,0,0,0.05); border: 1px solid var(--border);
        cursor: pointer; font-weight: 500; text-transform: uppercase; font-size: 0.9rem;
        color: var(--on-surface); opacity: 0.6;
    }
    .tab-btn.active { background: var(--primary); color: var(--on-primary); opacity: 1; border-color: var(--primary); }
    .tab-btn:first-child { border-radius: var(--radius) 0 0 var(--radius); }
    .tab-btn:last-child { border-radius: 0 var(--radius) var(--radius) 0; }

    /* Vocab */
    .vocab-view { display: flex; flex-direction: column; gap: 6px; margin-top: 20px; }
    .vocab-item {
        display:flex; justify-content:space-between; align-items:center; padding:12px 16px;
        border:1px solid var(--border); border-radius: var(--radius); background: var(--surface);
        box-shadow: var(--shadow);
    }

    /* Quiz */
    .quiz-container {
        background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
        padding: 24px; margin-top: 20px; box-shadow: var(--shadow);
    }
    .quiz-progress-track { width: 100%; height: 6px; background: rgba(0,0,0,0.1); border-radius: 3px; margin-bottom: 20px; overflow: hidden; }
    .quiz-progress-fill { height: 100%; background: var(--primary); transition: width 0.3s ease; }
    .quiz-question { font-size: 1.2rem; font-weight: 500; margin-bottom: 20px; }
    .quiz-options { display: flex; flex-direction: column; gap: 10px; }
    .quiz-option {
        padding: 12px 16px; border: 2px solid var(--border); border-radius: 8px; cursor: pointer;
        font-size: 1rem; background: transparent; color: var(--on-surface); text-align: left;
    }
    .quiz-option:hover:not(.disabled) { background: rgba(0,0,0,0.02); border-color: var(--primary); }
    .quiz-option.selected { border-color: var(--primary); background: rgba(25, 118, 210, 0.05); }
    .quiz-option.correct { border-color: #4CAF50 !important; background: rgba(76, 175, 80, 0.1) !important; color: #2E7D32; }
    .quiz-option.wrong { border-color: #f44336 !important; background: rgba(244, 67, 54, 0.1) !important; color: #c62828; }
    .quiz-option.disabled { pointer-events: none; }

    .results-view { display: flex; flex-direction: column; align-items: center; padding: 20px 0; animation: fadeIn 0.3s ease; }
    .score-circle {
        display: flex; align-items: center; justify-content: center; position: relative;
    }
    .score-circle svg { position: absolute; top: 0; left: 0; width: 100%; height: 100%; transform: rotate(-90deg); }
    .score-circle circle { fill: none; stroke-width: 22; stroke-linecap: round; }
    .score-circle-bg { stroke: #333; opacity: 0.1; }
    .score-circle-fg {
        stroke-dasharray: 434; /* 2 * PI * 69 */
        transition: stroke-dashoffset 1.5s ease-out;
    }

    /* Popups */
    #pop {
        position: absolute; background: var(--on-surface); color: var(--bg);
        padding: 8px 16px; border-radius: 4px; z-index: 2000; cursor: pointer;
        font-weight: 500; font-size: 0.8rem; box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    #learned-pop {
        position:absolute; background:var(--surface); color:var(--on-surface);
        padding:8px 12px; border-radius:4px; box-shadow:0 4px 12px rgba(0,0,0,0.15);
        z-index:101; border:1px solid var(--border); min-width:auto; max-width: 250px;
    }

    /* Global styles for dynamic content */
    :global(.learned) {
        background-color: rgba(25, 118, 210, 0.15);
        border-bottom: 2px solid var(--primary);
        cursor: pointer; border-radius: 3px; padding: 0 1px;
    }
    :global(body.dark-mode .learned) {
        background-color: rgba(144, 202, 249, 0.2);
        border-bottom-color: #90CAF9;
    }
</style>
