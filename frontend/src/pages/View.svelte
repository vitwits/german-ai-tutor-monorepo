<script>
  import { onMount, onDestroy, tick } from "svelte";
  import { fade } from "svelte/transition";
  import { tweened } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import api from "../lib/api";
  import { user } from "../stores/auth";
  import { router } from "tinro";
  import { addToast } from "../stores/toast";
  import { getUI } from "../lib/ui";
  import { confirmModal } from "../stores/confirm";
  import { getAudioCachePath, checkAudioExists } from "../lib/hashUtils";

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
  
  // Edit State
  let editingId = null;
  let editValue = "";
  let editingFieldType = ''; // 'ua' or 'en'
  
  // Quiz State
  let currentQIndex = 0;
  let quizScore = 0;
  let quizActive = false;
  let quizFinished = false;
  let selectedOptionIndex = null;
  let isChecked = false;
  let lastQuizResult = null;
  let showQuizSplash = false;
  let scorePct = 0;

  // Tweened store for smooth score animation
  const animatedScore = tweened(0, {
    duration: 1500,
    easing: cubicOut
  });

  // Popups
  let showPopup = false;
  let popupStyle = "";
  let selectedText = "";
  let selectionContext = "";
  let selectionSentenceIndex = -1;
  let selectionStartIndex = -1;
  let isTranslating = false; // Показать loader во время перевода
  let activeTranslationText = ""; // Отслеживание текущего перевода
  let popupHideTimeout; // Таймер для скриття попапу

  let showLearnedPopup = false;
  let learnedPopupContent = "";
  let learnedPopupStyle = "";
  let hideTimeout;

  // Grammar Cache
  let grammarCache = {};

  // Reactive UI strings
  $: ui = getUI($user?.interface_language || 'ukr');

  // Re-load text when id changes (only if user is loaded)
  $: if (id && $user) loadText();

  async function loadText() {
    loading = true;
    try {
      const res = await api.get(`/texts/${id}`);
      text = res.data.text;
      vocab = res.data.vocab || [];
      lastQuizResult = res.data.last_quiz_result;
      const grammarIndices = res.data.grammar_indices || [];
      
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
        let transText = s.ua;  // Changed from 'uk' to 'ua' to match API response
        if (userLang !== 'ukr') transText = s.en || s.ua;
        if (!transText) transText = s.en || s.ua;

        return { ...s, de_html: html, index: idx, has_grammar: grammarIndices.includes(idx), grammar_explanation: null, display_trans: transText };
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
          let audioUrl = null;
          
          // Step 1: Try to get audio from cache
          const cacheUrl = getAudioCachePath(txt, 'de');
          if (cacheUrl && await checkAudioExists(cacheUrl)) {
              audioUrl = cacheUrl;
          } else {
              // Step 2: Generate via TTS if cache miss
              const res = await api.post('/tts', { text: txt, source: 'texts' });
              audioUrl = res.data.url;
          }
          
          if (!audioUrl) {
              console.error('Failed to get audio URL');
              return;
          }
          
          return new Promise((resolve) => {
              currentAudio = new Audio(audioUrl);
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
          const res = await api.post('/tts_pair', { de_text: de, trans_text: trans, source: 'vocabulary' });
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
    // Блокируем выделение нового слова во время перевода
    if (isTranslating) {
        showPopup = false;
        return;
    }

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
    const transRow = sentenceEl.querySelector('.trans-row');
    
    // Перевіряємо, чи виділення **ТОЧНО** в .de-text (а не в .trans-row)
    if (!textSpan || !textSpan.contains(selection.anchorNode)) return;
    if (transRow && transRow.contains(selection.anchorNode)) return;

    // --- WORD COUNT LIMIT (тільки для .de-text) ---
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

    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    
    // Calculate precise index
    selectionStartIndex = getCharOffset(textSpan, range.startContainer, range.startOffset);

    // Position Popup
    
    if (window.innerWidth > 768) {
        // Use fixed positioning to avoid issues with relative containers
        popupStyle = `position: fixed; top: ${rect.top - 45}px; left: ${rect.left + (rect.width / 2)}px; transform: translateX(-50%); z-index: 2000;`;
    } else {
        popupStyle = `position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%); width: auto; min-width: 200px; text-align: center;`;
    }

    selectedText = textStr;
    selectionContext = sentenceEl.dataset.text;
    selectionSentenceIndex = parseInt(sentenceEl.dataset.index);
    showPopup = true;
    
    // Скидаємо попередній таймер якщо існує
    if (popupHideTimeout) clearTimeout(popupHideTimeout);
    
    // Запускаємо таймер на 2 секунди для автоматичного скриття
    popupHideTimeout = setTimeout(() => {
        if (showPopup && !isTranslating) {
            showPopup = false;
        }
    }, 2000);
  }

  function onPopupMouseEnter() {
    // Скасовуємо таймер прихованого коли курсор над попапом
    if (popupHideTimeout) {
        clearTimeout(popupHideTimeout);
        popupHideTimeout = null;
    }
  }

  function onPopupMouseLeave() {
    // Запускаємо таймер прихованого коли курсор покидає попап (2 секунди)
    popupHideTimeout = setTimeout(() => {
        showPopup = false;
    }, 2000);
  }

  async function reportText() {
    if (!text) return;
    
    const isUkr = $user?.interface_language === 'ukr';
    const title = isUkr ? "Повідомити про проблему?" : "Report issue?";
    const message = isUkr 
        ? "Цей текст буде позначений як проблемний для адміністраторів, і ви більше його не будете бачити."
        : "This text will be reported to administrators and won't appear for you again.";
    const okText = isUkr ? "Повідомити" : "Report";
    const cancelText = isUkr ? "Скасувати" : "Cancel";
    
    const confirmed = await confirmModal.ask(title, message, okText, cancelText, true);
    
    if (!confirmed) return;
    
    try {
        await api.post('/report_text', { id });
        addToast(ui.text_reported || "Reported", "success");
        router.goto('/library');
    } catch(e) { console.error(e); }
  }

  async function quickTranslate() {
    // Блокируем двойное нажатие
    if (isTranslating) return;
    
    isTranslating = true;
    activeTranslationText = selectedText;
    
    try {
        const res = await api.post('/quick_translate', {
            text: selectedText,
            ctx: selectionContext,
            tid: id,
            sent_idx: selectionSentenceIndex,
            start_char_index: selectionStartIndex
        });

        if (res.data.ok) {
            // Оновлюємо локально без перезавантаження
            const newWord = res.data.word;
            
            // Додаємо до vocab масиву
            vocab = [...vocab, newWord];
            vocabMap[newWord.id] = newWord;
            
            // Оновлюємо sentences з новим highlight
            const sentIdx = selectionSentenceIndex;
            const s = sentences[sentIdx];
            const originalText = s.de;
            
            // Перебудовуємо HTML з новим словом
            const sentVocab = vocab.filter(v => v.sentence_index === sentIdx);
            sentVocab.sort((a, b) => (b.start_index || 0) - (a.start_index || 0));
            
            let lastIdx = originalText.length;
            let html = "";
            
            sentVocab.forEach(v => {
                const start = v.start_index;
                const end = v.end_index;
                
                if (start !== null && start >= 0 && end <= originalText.length && start < end) {
                    html = originalText.substring(end, lastIdx) + html;
                    const wordVal = originalText.substring(start, end);
                    html = `<span class="learned" data-wid="${v.id}">${wordVal}</span>` + html;
                    lastIdx = start;
                }
            });
            
            html = originalText.substring(0, lastIdx) + html;
            
            // Оновлюємо речення
            sentences[sentIdx] = { ...sentences[sentIdx], de_html: html };
            sentences = sentences; // Trigger reactivity
            
            // Update energy if returned
            if (res.data.energy_left !== undefined) {
              user.update(u => ({
                ...u,
                billing: {
                  ...u.billing,
                  energy_left: res.data.energy_left,
                  daily_spending: res.data.daily_spending
                }
              }));
            }
            
            showPopup = false;
            window.getSelection().removeAllRanges();
            addToast(ui.word_added, "success");
        } else {
            // Показуємо "word_exists" як попередження (жовте), а не помилку (червоне)
            const toastType = res.data.error_key === 'word_exists' ? 'warning' : 'error';
            addToast(ui[res.data.error_key] || ui.translation_failed_msg, toastType);
        }
    } catch (e) {
        console.error(e);
        addToast(ui.error_generic, "error");
    } finally {
        isTranslating = false;
        activeTranslationText = "";
    }
  }
  
  function scrollToWord(wid) {
      const el = document.querySelector(`.learned[data-wid="${wid}"]`);
      if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          // Optional: highlight effect
          // el.classList.add('highlight-word');
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
              
              learnedPopupStyle = `top: ${rect.top - 8}px; left: ${rect.left + (rect.width/2)}px; transform: translate(-50%, -100%); display: block; position: fixed;`;
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
      switchTab('quiz');
  }

  function initQuizState() {
      activeTab = 'quiz';
      
      // Якщо квіз не активний, перевіряємо, чи є старий результат для показу
      if (!quizActive && lastQuizResult && lastQuizResult.score !== undefined) {
          quizFinished = true;
          quizScore = lastQuizResult.score;
          const total = lastQuizResult.total_questions || quizData.length;
          scorePct = Math.round((quizScore / total) * 100);
          animatedScore.set(scorePct, { duration: 0 });
      } 
      // Інакше починаємо новий (якщо не активний)
      else if (!quizActive && !quizFinished) {
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
      // FIX: Set the animated score. This will trigger the animation on both splash and embedded views.
      animatedScore.set(scorePct);
      showQuizSplash = true;
      
      // Оновлюємо локальний кеш результату
      lastQuizResult = { score: quizScore, total_questions: quizData.length };
      
      try {
          await api.post('/save_quiz_result', {
              text_id: id,
              score: quizScore,
              total: quizData.length
          });
      } catch(e) {}

      if (scorePct >= 100) {
          setTimeout(launchConfetti, 300);
      }
  }

  async function abortQuiz() {
      const ok = await confirmModal.ask(ui.abort_confirm_title, ui.abort_confirm_msg, ui.exit_btn, ui.btn_cancel, true);
      if (ok) {
          activeTab = 'vocab';
          quizActive = false;
          quizFinished = false; // Ensure we don't show results screen
      }
  }

  function restartQuiz() {
      showQuizSplash = false;
      quizFinished = false;
      quizActive = true;
      currentQIndex = 0;
      quizScore = 0;
      selectedOptionIndex = null;
      isChecked = false;
      scorePct = 0;
      animatedScore.set(0, { duration: 0 });
  }

  function closeSplash() {
      showQuizSplash = false;
      // Видаляємо конфетті
      const container = document.getElementById('quiz-splash');
      if (container) {
          const particles = container.querySelectorAll('.confetti');
          particles.forEach(p => p.remove());
      }
  }

  function launchConfetti() {
      const colors = ['#FFC107', '#2196F3', '#4CAF50', '#F44336', '#9C27B0'];
      const container = document.getElementById('quiz-splash');
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

  // --- TABS & NAVIGATION GUARD ---

  function switchTab(tab) {
      if (activeTab === tab) return;

      // Захист від випадкового виходу з квізу
      if (activeTab === 'quiz' && quizActive && (currentQIndex > 0 || isChecked)) {
          if (!confirm(ui.abort_confirm_msg)) return;
          // Якщо користувач погодився вийти - скидаємо прогрес
          quizActive = false;
          currentQIndex = 0;
          isChecked = false;
      }

      activeTab = tab;
      
      // Якщо пішли з квіза, але не було прогресу - просто скидаємо активність
      if (activeTab !== 'quiz') {
          quizActive = false;
      }
      if (tab === 'quiz') {
          initQuizState();
      }
  }

  // Захист від закриття вкладки/оновлення
  function handleBeforeUnload(e) {
      if (activeTab === 'quiz' && quizActive && (currentQIndex > 0 || isChecked)) {
          e.preventDefault();
          e.returnValue = '';
          return '';
      }
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
      // No confirm needed, using undo toast flow
      
      // 1. Optimistic UI update
      // Hide from vocab list
      vocab = vocab.filter(v => v.id !== wid);
      // Remove highlight from text
      const highlights = document.querySelectorAll(`.learned[data-wid="${wid}"]`);
      highlights.forEach(span => {
          const textNode = document.createTextNode(span.innerText);
          span.parentNode.replaceChild(textNode, span);
      });

      // 2. Set up delayed delete
      const deleteTimeout = setTimeout(() => {
          api.post('/remove_word', { id: wid, from_vocab: false }).catch(e => {
              console.error("Final delete failed:", e);
              addToast('Error, reloading...', 'error');
              setTimeout(() => location.reload(), 1500);
          });
      }, 5000);

      // 3. Show toast with undo
      const undo = () => {
          clearTimeout(deleteTimeout);
          loadText(); // Easiest way to restore state
      };

      addToast(ui.word_deleted || 'Word removed', "info", undo, 5000);
  }

  function startEdit(wid, currentVal, fieldType) {
      editingId = wid;
      editValue = currentVal;
      editingFieldType = fieldType;
  }

  function cancelEdit() {
      editingId = null;
      editValue = "";
      editingFieldType = '';
  }

  async function saveEdit(wid) {
      try {
          await api.post('/update_word', { id: wid, translation: editValue });
          vocab = vocab.map(v => {
              if (v.id === wid) {
                  const fieldName = editingFieldType === 'ua' ? 'ua' : 'en';
                  return { ...v, [fieldName]: editValue };
              }
              return v;
          });
          editingId = null;
      } catch(e) { addToast(ui.error_saving || "Error saving", "error"); }
  }
  
  // Global click listener for learned words popup
  onMount(() => {
      window.addEventListener('beforeunload', handleBeforeUnload);
      document.addEventListener('click', handleLearnedClick);
  });
  onDestroy(() => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      if (typeof document !== 'undefined') document.removeEventListener('click', handleLearnedClick);
      if (currentAudio) currentAudio.pause();
  });
</script>

<div class="view-container" onmouseup={handleMouseUp} role="button" tabindex="0">
    {#if loading}
        <div style="text-align: center; padding: 50px; opacity: 0.6;">{ui.loading}</div>
    {:else if text}
        <div class="card">
            <h1 style="font-size:1.5rem; margin:0 0 4px 0;">{JSON.parse(text.title).de}</h1>
            <h2 style="font-size: 1rem; color: var(--on-surface); opacity: 0.6; margin: 0 0 16px 0; font-weight: 400;">
                {JSON.parse(text.title)[$user.interface_language === 'ukr' ? 'ukr' : 'eng'] || ''}
            </h2>
            
            <div class="toolbar">
                <span class="level-badge lvl-{text.level.toLowerCase()}" style="margin-right: 12px;">{text.level}</span>
                
                <button class="badge-btn" onclick={() => showTrans = !showTrans}>
                    <span class="material-symbols-outlined">{showTrans ? 'visibility_off' : 'translate'}</span>
                </button>
                
                <button class="badge-btn" onclick={toggleTextFav} style="color: {text.is_favorite ? '#d32f2f' : 'inherit'}">
                    <span class="material-symbols-outlined {text.is_favorite ? 'filled' : ''}">favorite</span>
                </button>

                <button class="report-btn" title={ui.report_sentence} onclick={reportText}>
                    <span class="material-symbols-outlined">flag</span>
                </button>

                <button class="btn-contained" onclick={playAll} style="margin-left: auto;">
                    <span class="material-symbols-outlined">{isPlayingAll ? 'pause' : 'play_arrow'}</span> 
                    {isPlayingAll ? ui.stop : ui.play_all}
                </button>
            </div>
            
            {#each sentences as s, i}
                <div class="de-line {playingIndex === i ? 'highlight-sentence' : ''}" id="sent-{i}" data-index={i} data-text={s.de}>
                    <div style="display:flex; justify-content: space-between; align-items: center;">
                        <div style="display:flex; align-items:center; gap:12px; flex: 1;">
                <button class="btn-text" onclick={() => playAudio(s.de, i)} style="height:32px; width:32px; padding:0; min-width:32px;">
                                <span class="material-symbols-outlined" style="font-size:20px; color:var(--primary)">volume_up</span>
                            </button>
                            <span class="de-text">{@html s.de_html}</span>
                        </div>
                    </div>
                    
                    {#if showTrans}
                        <div class="trans-row">{s.display_trans}</div>
                    {/if}
                </div>
            {/each}
        </div>

        <!-- TABS -->
        <div class="tabs-container">
            <button class="tab-btn {activeTab === 'vocab' ? 'active' : ''}" onclick={() => switchTab('vocab')}>{ui.vocab_tab}</button>
            {#if quizData.length > 0}
                <button class="tab-btn {activeTab === 'quiz' ? 'active' : ''}" onclick={() => switchTab('quiz')}>{ui.quiz_tab}</button>
            {/if}
        </div>

        <!-- VOCAB TAB -->
        {#if activeTab === 'vocab'}
            <div class="vocab-view">
                {#if vocab.length === 0}
                    <div class="card" style="text-align:center; opacity:0.6;">{ui.empty_vocab_prompt}</div>
                {/if}
                {#each vocab as v}
                    <div class="vocab-item" role="button" tabindex="0" onclick={() => { if (!editingId) toggleVocabFav(v.id); }}>
                        <div style="display:flex; align-items:center; gap:12px; flex: 1; min-width: 0;">
                            <button class="btn-text" onclick={(e) => { e.stopPropagation(); playVocabPair(v.display, $user.interface_language === 'ukr' ? v.ua : v.en); }}>
                                <span class="material-symbols-outlined" style="font-size:18px;">volume_up</span>
                            </button>
                            <div style="overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0;">
                                <span style="font-weight: 500; color: var(--primary); font-size: 1.1rem; cursor: pointer;" onclick={(e) => { e.stopPropagation(); scrollToWord(v.id); }} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && scrollToWord(v.id)}>{v.display}</span>
                                <div style="font-size:0.85rem; opacity:0.7; margin-top:6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                    {#if editingId === v.id && editingFieldType === ($user.interface_language === 'ukr' ? 'ua' : 'en')}
                                        <input type="text" class="edit-input" bind:value={editValue} onclick={(e) => e.stopPropagation()} onkeydown={(e) => { e.stopPropagation(); if(e.key === 'Enter') saveEdit(v.id); }} />
                                    {:else}
                                        {$user.interface_language === 'ukr' ? v.ua : v.en}
                                    {/if}
                                </div>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 0;">
                            <button class="btn-text" onclick={(e) => { e.stopPropagation(); toggleVocabFav(v.id); }} style="color: {v.is_favorite ? '#FFC107' : 'inherit'}; min-width: 32px; padding: 0;">
                                <span class="material-symbols-outlined {v.is_favorite ? 'filled' : ''}">star</span>
                            </button>
                            {#if editingId === v.id}
                                <button class="btn-text" style="color:var(--primary); padding:0; min-width:32px;" onclick={(e) => { e.stopPropagation(); saveEdit(v.id); }}>
                                    <span class="material-symbols-outlined">check</span>
                                </button>
                                <button class="btn-text" style="padding:0; min-width:32px;" onclick={(e) => { e.stopPropagation(); cancelEdit(); }}>
                                    <span class="material-symbols-outlined">close</span>
                                </button>
                            {:else}
                                <button class="btn-text" style="color:var(--primary); opacity:0.7; padding:0; min-width:32px;" onclick={(e) => { e.stopPropagation(); startEdit(v.id, $user.interface_language === 'ukr' ? v.ua : v.en, $user.interface_language === 'ukr' ? 'ua' : 'en'); }}>
                                    <span class="material-symbols-outlined">edit</span>
                                </button>
                                <button class="btn-text" onclick={(e) => { e.stopPropagation(); removeWord(v.id); }} style="color:red; min-width: 32px; padding: 0;">
                                    <span class="material-symbols-outlined">delete</span>
                                </button>
                            {/if}
                        </div>
                    </div>
                {/each}
            </div>
        {/if}

        <!-- QUIZ TAB -->
        {#if activeTab === 'quiz'}
            <div class="quiz-container">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <div style="font-weight: 500; opacity: 0.7;">{ui.quiz_tab} {quizFinished ? quizData.length : currentQIndex + 1} / {quizData.length}</div>
                </div>
                
                {#if quizFinished}
                    <div class="results-view">
                        <div class="score-circle">
                    <svg viewBox="0 0 160 160" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;">
                                <circle class="score-circle-bg" cx="80" cy="80" r="69"></circle>
                            <circle class="score-circle-fg" cx="80" cy="80" r="69" style="stroke-dashoffset: {434 - ($animatedScore / 100) * 434}; stroke: {$animatedScore >= 80 ? '#4CAF50' : $animatedScore >= 50 ? '#FFC107' : '#f44336'};"></circle>
                            </svg>
                    <span style="font-size: 2.5rem; position: relative; z-index: 1;">{$animatedScore.toFixed(0)}%</span>
                        </div>
                <div style="font-size: 1.1rem; margin-bottom: 30px; opacity: 0.8;">{ui.your_score}</div>
                <button class="btn-contained" onclick={restartQuiz}>{ui.retry_btn}</button>
                    </div>
                {:else}
                    <div class="quiz-progress-track">
                        <div class="quiz-progress-fill" style="width: {((currentQIndex) / quizData.length) * 100}%"></div>
                    </div>
                    
                    <div class="quiz-question">{@html quizData[currentQIndex].question}</div>
                    
                    <div class="quiz-options">
                        {#each quizData[currentQIndex].options as opt, idx}
                            <button class="quiz-option 
                                {selectedOptionIndex === idx ? 'selected' : ''} 
                                {isChecked && idx === quizData[currentQIndex].correct_index ? 'correct' : ''}
                                {isChecked && selectedOptionIndex === idx && idx !== quizData[currentQIndex].correct_index ? 'wrong' : ''}
                                {isChecked ? 'disabled' : ''}"
                                onclick={() => selectOption(idx)}>
                                {opt}
                            </button>
                        {/each}
                    </div>

                    <!-- FOOTER ACTIONS -->
                    <div style="margin-top: 24px; display: flex; justify-content: space-between; align-items: center;">
                        <div style="display: flex; gap: 10px;">
                             <button class="btn-contained btn-danger" onclick={abortQuiz}>
                                {ui.abort_btn}
                             </button>
                             {#if isChecked}
                                <button class="btn-contained" onclick={restartQuiz} style="background-color: var(--secondary); color: black;">{ui.restart_btn}</button>
                             {/if}
                        </div>
                        
                        {#if !isChecked}
                            <button class="btn-contained" disabled={selectedOptionIndex === null} onclick={checkAnswer} style="min-width: 100px;">{ui.check_btn}</button>
                        {:else}
                            <button class="btn-contained" onclick={nextQuestion} style="min-width: 100px;">{currentQIndex < quizData.length - 1 ? ui.next_btn : ui.finish_btn}</button>
                        {/if}
                    </div>
                {/if}
            </div>
        {/if}
    {/if}

    <!-- POPUPS -->
    {#if showPopup}
        <button 
            type="button" 
            id="pop" 
            style={popupStyle} 
            onclick={(e) => { e.stopPropagation(); quickTranslate(); }} 
            disabled={isTranslating}
            onmouseenter={onPopupMouseEnter}
            onmouseleave={onPopupMouseLeave}
        >
            {#if isTranslating}
                <span class="loader-spinner"></span>
            {:else}
                {ui.add_translation}
            {/if}
        </button>
    {/if}

    {#if showLearnedPopup}
        <div id="learned-pop" style={learnedPopupStyle}>
            {@html learnedPopupContent}
        </div>
    {/if}

    <!-- QUIZ SPLASH SCREEN -->
    {#if showQuizSplash}
        <div id="quiz-splash" transition:fade={{ duration: 300 }}>
            <h2 style="margin-bottom: 30px;">{ui.quiz_completed}</h2>
            <div class="score-circle" style="width: 160px; height: 160px; margin-bottom: 20px;">
                <svg viewBox="0 0 160 160">
                    <circle class="score-circle-bg" cx="80" cy="80" r="69"></circle>
                    <circle class="score-circle-fg" cx="80" cy="80" r="69" style="stroke-dashoffset: {434 - ($animatedScore / 100) * 434}; stroke: {$animatedScore >= 80 ? '#4CAF50' : $animatedScore >= 50 ? '#FFC107' : '#f44336'};"></circle>
                </svg>
                <span id="splash-score">{$animatedScore.toFixed(0)}%</span>
            </div>
            <div style="font-size: 1.2rem; margin-bottom: 40px; opacity: 0.8;">{ui.your_score}</div>
            <div style="display: flex; gap: 20px;">
                <button class="btn-contained" style="background: white; color: black;" onclick={closeSplash}>{ui.done_btn}</button>
                <button class="btn-contained" onclick={restartQuiz}>{ui.retry_btn}</button>
            </div>
        </div>
    {/if}
</div>

<style>
    .view-container { max-width: 1180px; margin: 0 auto; padding-bottom: 100px; position: relative; }
    
    .toolbar { display:flex; align-items:center; gap:12px; margin-bottom:24px; flex-wrap:wrap; }
    
    .de-line { padding:8px 0; border-bottom:1px solid var(--border); transition: background-color 0.3s; }
    .de-text { font-size:1.1rem; font-weight:400; line-height:1.6; font-family: var(--font-text); }
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

    .report-btn {
        padding: 4px 12px; border-radius: 4px; display: inline-flex; align-items: center; justify-content: center;
        min-width: 28px; height: 30px; border: none; background: transparent; color: #d32f2f;
        cursor: pointer; transition: opacity 0.2s; opacity: 0.5;
    }
    .report-btn:hover { opacity: 1; }

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
        box-shadow: var(--shadow); font-family: var(--font-text);
    }
    
    .edit-input { 
        width: 100%; 
        border: none; 
        background: transparent; 
        font: inherit; 
        font-size: 1.1rem; 
        font-family: var(--font-text);
        outline: none; 
        padding: 0; 
        margin: 0; 
        color: inherit; 
        border-bottom: 1px solid var(--primary); 
        border-radius: 0;
    }

    /* Quiz */
    .quiz-container {
        background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
        padding: 24px; margin-top: 20px; box-shadow: var(--shadow);
    }
    .quiz-progress-track { width: 100%; height: 6px; background: rgba(0,0,0,0.1); border-radius: 3px; margin-bottom: 20px; overflow: hidden; }
    .quiz-progress-fill { height: 100%; background: var(--primary); transition: width 0.3s ease; }
    .quiz-question { font-size: 1.2rem; font-weight: 500; margin-bottom: 20px; line-height: 1.4; }
    .quiz-options { display: flex; flex-direction: column; gap: 10px; }
    .quiz-option {
        padding: 12px 16px; border: 2px solid var(--border); border-radius: 8px; cursor: pointer;
        font-size: 1rem; background: transparent; color: var(--on-surface); text-align: left; transition: all 0.2s;
        text-transform: none; justify-content: flex-start; height: auto; line-height: 1.4; font-weight: normal;
    }
    /* Скидаємо стилі кнопки для quiz-option, щоб вона виглядала як div */
    .quiz-option:hover:not(.disabled) { background: rgba(0,0,0,0.02); border-color: var(--primary); }
    .quiz-option.selected { border-color: var(--primary); background: rgba(25, 118, 210, 0.05); }
    .quiz-option.correct { border-color: #4CAF50 !important; background: rgba(76, 175, 80, 0.1) !important; color: #2E7D32; }
    .quiz-option.wrong { border-color: #f44336 !important; background: rgba(244, 67, 54, 0.1) !important; color: #c62828; }
    .quiz-option.disabled { pointer-events: none; }

    .results-view { display: flex; flex-direction: column; align-items: center; padding: 20px 0; animation: fadeIn 0.3s ease; }
    .score-circle {
        display: flex; align-items: center; justify-content: center; position: relative; width: 160px; height: 160px; margin-bottom: 20px;
    }
    .score-circle svg { position: absolute; top: 0; left: 0; width: 100%; height: 100%; transform: rotate(-90deg); }
    .score-circle circle { fill: none; stroke-width: 22; stroke-linecap: round; }
    .score-circle-bg { stroke: #333; opacity: 0.1; }
    .score-circle-fg {
        stroke-dasharray: 434; /* 2 * PI * 69 */
        transition: stroke-dashoffset 1.5s ease-out;
    }

    /* Splash Screen */
    #quiz-splash {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(8px);
        z-index: 10000; display: flex; flex-direction: column;
        align-items: center; justify-content: center; color: white;
    }
    #splash-score { font-size: 2.5rem; font-weight: 700; position: absolute; color: white; }

    /* Confetti */
    :global(.confetti) { 
        position: fixed; width: 10px; height: 10px; z-index: 10001; pointer-events: none; top: -20px;
    }

    /* Popups */
    #pop {
        position: absolute; background: var(--on-surface); color: var(--bg);
        padding: 8px 16px; border-radius: 4px; z-index: 2000; cursor: pointer;
        border: none; font-family: inherit; height: auto; text-transform: none;
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

    .btn-danger {
        background-color: #d32f2f;
        color: white;
    }

    /* Loader Spinner */
    .loader-spinner {
        display: inline-block;
        width: 12px;
        height: 12px;
        border: 2px solid rgba(0, 0, 0, 0.1);
        border-radius: 50%;
        border-top-color: var(--primary);
        animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    #pop {
        transition: opacity 0.3s ease-out;
    }

    #pop:disabled {
        cursor: not-allowed;
        pointer-events: none;
    }
</style>
