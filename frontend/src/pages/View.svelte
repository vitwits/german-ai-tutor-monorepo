<script>
    /* eslint-disable */
    import { onMount, onDestroy, tick } from "svelte";
    import { fade } from "svelte/transition";
    import { tweened } from "svelte/motion";
    import { cubicOut } from "svelte/easing";
    import api from "../lib/api";
    import { user } from "../stores/auth";
    import { router } from "tinro";
    import { addToast } from "../stores/toast";
    import { getUI } from "../lib/ui";
    import { confirmModal } from "../stores/confirm";

    export let id;

    let text = null;
    let sentences = [];
    let vocab = [];
    let vocabMap = {};
    let quizData = [];
    let loading = true;

    // UI State
    let activeTab = "vocab"; // 'vocab' or 'quiz'
    let showTrans = false;
    let isPlayingAll = false;
    let playingIndex = -1; // Index of sentence currently playing in Play All
    let currentAudio = null;
    let userInitiatedPlay = false; // true if user clicked Play (vs Play All calling playAudio)
    let vocabPlayingId = null; // ID of vocabulary word currently playing
    let currentVocabPlayId = null; // Track which vocab play session is active (to abort old ones)
    let showDictation = false;
    let dictationOrder = [];
    let dictationCursor = 0;
    let dictationInput = "";
    let dictationResult = null;
    let dictationChecking = false;
    let dictationPlaying = false;
    let dictationPlaybackRate = 0.8;
    let dictationCurrentSentenceIndex = -1;
    let dictationCurrentSentence = null;
    let dictationHasNext = false;
    let showDictationResumePrompt = false;
    let pendingDictationProgress = null;
    let dictationPassedMap = {};
    let dictationPassedCurrentSentence = false;
    let dictationCompletedOnce = false;
    let showDictationSplash = false;
    let showSentenceTranslationTest = false;
    let sentenceTranslationOrder = [];
    let sentenceTranslationCursor = 0;
    let sentenceTranslationInput = "";
    let sentenceTranslationResult = null;
    let sentenceTranslationChecking = false;
    let sentenceTranslationCurrentSentenceIndex = -1;
    let sentenceTranslationCurrentSentence = null;
    let sentenceTranslationHasNext = false;
    let showSentenceTranslationResumePrompt = false;
    let pendingSentenceTranslationProgress = null;
    let sentenceTranslationPassedMap = {};
    let sentenceTranslationPassedCurrentSentence = false;
    let sentenceTranslationCompletedOnce = false;
    let showSentenceTranslationSplash = false;
    const DICTATION_PASS_SCORE = 95;
    const SENTENCE_TRANSLATION_PASS_SCORE = 95;

    let editingTitle = false;
    let editTitleValue = "";

    async function saveTitleEdit() {
        const trimmed = editTitleValue.trim().slice(0, 60);
        if (!trimmed) return;
        try {
            await api.post("/rename_text", { id, title: trimmed });
            text = { ...text, custom_title: trimmed };
            editingTitle = false;
        } catch (e) {
            console.error(e);
            addToast(ui.error_generic, "error");
        }
    }

    function cancelTitleEdit() {
        editingTitle = false;
    }

    // Edit State
    let editingId = null;
    let editValue = "";
    let editingFieldType = ""; // 'ua' or 'en'

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
        easing: cubicOut,
    });

    // Popups
    let showPopup = false;
    let popupStyle = "";
    let selectedText = "";
    let selectionContext = "";
    let selectionSentenceIndex = -1;
    let selectionStartIndex = -1;
    let isTranslating = false; // Показать loader во время перевода
    let popupHideTimeout; // Таймер для скриття попапу

    let showLearnedPopup = false;
    let learnedPopupContent = "";
    let learnedPopupStyle = "";
    let learnedPopupSticky = false;
    let hideTimeout;

    let isSingleWordSelected = false;
    let explainedWordsMap = {}; // { explainedId: { sentenceIndex, startIndex, endIndex, text, explanation } }

    // Grammar Cache
    let grammarCache = {};

    // Sentence button modes: tracks hover state and mode for each sentence
    let sentenceButtonMode = {}; // { sentenceIndex: 'normal' | 'play' | 'translate' }
    let sentenceHoverTimers = {}; // { sentenceIndex: timeoutId }
    let sentenceTranslationDisplay = {}; // { sentenceIndex: true/false }
    let sentenceTranslationTimers = {}; // { sentenceIndex: timeoutId }

    // Reactive UI strings
    $: ui = getUI($user?.interface_language || "ukr");
    $: isSingleWordSelected =
        selectedText
            .trim()
            .split(/\s+/)
            .filter((w) => w.length > 0).length === 1;

    // Re-load text when id changes (only if user is loaded)
    // ⭐ Залежимо тільки від id, НЕ від $user — інакше user.update() перезавантажує сторінку
    let prevId = null;
    $: if (id && id !== prevId && $user) {
        prevId = id;
        loadText();
        fetchDictationState();
        fetchSentenceTranslationState();
    }

    async function loadText() {
        loading = true;
        try {
            const res = await api.get(`/texts/${id}`);
            text = res.data.text;
            vocab = res.data.vocab || [];
            const explainedWords = res.data.explained_words || [];
            lastQuizResult = res.data.last_quiz_result;
            const grammarIndices = res.data.grammar_indices || [];

            explainedWordsMap = {};
            explainedWords.forEach((w) => {
                explainedWordsMap[w.id] = {
                    id: w.id,
                    sentenceIndex: w.sentence_index,
                    startIndex: w.start_index,
                    endIndex: w.end_index,
                    text: w.text,
                    explanation: w.explanation,
                };
            });

            // Build Vocab Map for quick lookup
            vocab.forEach((v) => (vocabMap[v.id] = v));

            // Parse Content
            const rawSentences = JSON.parse(text.content_json);

            // Parse Quiz
            if (text.quiz_json) {
                try {
                    quizData = JSON.parse(text.quiz_json);
                } catch (e) {}
            }

            // Process sentences for highlighting
            sentences = rawSentences.map((s, idx) => {
                const originalText = s.de;
                const sentVocab = vocab.filter((v) => v.sentence_index === idx);

                // Сортуємо у зворотному порядку (від кінця до початку),
                // щоб вставка тегів не зсувала індекси для попередніх слів
                sentVocab.sort(
                    (a, b) => (b.start_index || 0) - (a.start_index || 0),
                );

                let lastIdx = originalText.length;
                let html = "";

                sentVocab.forEach((v) => {
                    const start = v.start_index;
                    const end = v.end_index;

                    // Перевіряємо валідність індексів
                    if (
                        start !== null &&
                        start >= 0 &&
                        end <= originalText.length &&
                        start < end
                    ) {
                        // Додаємо текст ПІСЛЯ слова
                        html = originalText.substring(end, lastIdx) + html;
                        // Додаємо саме слово в обгортці
                        const wordVal = originalText.substring(start, end);
                        html =
                            `<span class="learned" data-wid="${v.id}">${wordVal}</span>` +
                            html;
                        lastIdx = start;
                    }
                });

                // Додаємо початок речення
                html = originalText.substring(0, lastIdx) + html;

                // Determine translation based on user language
                // const userLang = $user ? $user.interface_language : 'ukr';
                const userLang = $user?.interface_language || "ukr";
                // Fallback logic: try target lang, then english, then whatever is available
                let transText = s.ua; // Changed from 'uk' to 'ua' to match API response
                if (userLang !== "ukr") transText = s.en || s.ua;
                if (!transText) transText = s.en || s.ua;

                return {
                    ...s,
                    de_html: html,
                    index: idx,
                    has_grammar: grammarIndices.includes(idx),
                    grammar_explanation: null,
                    display_trans: transText,
                };
            });

            for (let i = 0; i < sentences.length; i++) {
                refreshSentenceHtml(i);
            }
        } catch (e) {
            console.error(e);
            addToast("Error loading text", "error");
            router.goto("/library");
        } finally {
            loading = false;
            // Підсвічуємо речення якщо прийшли з Vocab через hash
            highlightSentenceFromHash();
        }
    }

    // --- AUDIO LOGIC ---

    // Track which audio is currently being played to detect duplicate calls
    let lastPlayedIdx = -1;

    $: dictationCurrentSentenceIndex =
        dictationOrder.length > 0 && dictationCursor >= 0
            ? dictationOrder[dictationCursor]
            : -1;
    $: dictationCurrentSentence =
        dictationCurrentSentenceIndex >= 0
            ? sentences[dictationCurrentSentenceIndex]
            : null;
    $: dictationHasNext = dictationCursor < dictationOrder.length - 1;
    $: dictationPassedCurrentSentence =
        !!dictationResult &&
        Number(dictationResult.similarity_score || 0) >= DICTATION_PASS_SCORE;

    $: dictationPassedCount = Object.keys(dictationPassedMap).length;

    $: sentenceTranslationCurrentSentenceIndex =
        sentenceTranslationOrder.length > 0 && sentenceTranslationCursor >= 0
            ? sentenceTranslationOrder[sentenceTranslationCursor]
            : -1;
    $: sentenceTranslationCurrentSentence =
        sentenceTranslationCurrentSentenceIndex >= 0
            ? sentences[sentenceTranslationCurrentSentenceIndex]
            : null;
    $: sentenceTranslationHasNext =
        sentenceTranslationCursor < sentenceTranslationOrder.length - 1;
    $: sentenceTranslationPassedCurrentSentence =
        !!sentenceTranslationResult &&
        !!sentenceTranslationResult.is_correct &&
        Number(sentenceTranslationResult.accuracy_score || 0) >=
            SENTENCE_TRANSLATION_PASS_SCORE;

    $: sentenceTranslationPassedCount = Object.keys(
        sentenceTranslationPassedMap,
    ).length;

    async function fetchDictationState() {
        if (!id) return { completed_once: false, progress: null };
        try {
            const res = await api.get(`/texts/${id}/dictation_progress`);
            dictationCompletedOnce = !!res.data?.completed_once;
            return res.data || { completed_once: false, progress: null };
        } catch (e) {
            dictationCompletedOnce = false;
            return { completed_once: false, progress: null };
        }
    }

    async function clearDictationProgressOnServer(keepCompleted = true) {
        if (!id) return;
        try {
            await api.post(`/texts/${id}/dictation_progress/clear`, {
                keep_completed: keepCompleted,
            });
            if (!keepCompleted) dictationCompletedOnce = false;
        } catch (e) {}
    }

    async function saveDictationProgressToServer() {
        if (!id) return;
        const passedIndices = Object.keys(dictationPassedMap).map((v) =>
            Number(v),
        );

        if (!passedIndices.length) {
            await clearDictationProgressOnServer(true);
            return;
        }

        try {
            await api.post(`/texts/${id}/dictation_progress/save`, {
                order: dictationOrder,
                cursor: dictationCursor,
                passed_indices: passedIndices,
                playback_rate: dictationPlaybackRate,
            });
        } catch (e) {}
    }

    async function markDictationCompletedOnServer() {
        if (!id) return;
        dictationCompletedOnce = true;
        try {
            await api.post(`/texts/${id}/dictation_progress/complete`, {});
        } catch (e) {}
    }

    async function fetchSentenceTranslationState() {
        if (!id) return { completed_once: false, progress: null };
        try {
            const res = await api.get(
                `/texts/${id}/sentence_translation_test/progress`,
            );
            sentenceTranslationCompletedOnce = !!res.data?.completed_once;
            return res.data || { completed_once: false, progress: null };
        } catch (e) {
            sentenceTranslationCompletedOnce = false;
            return { completed_once: false, progress: null };
        }
    }

    async function clearSentenceTranslationProgressOnServer(
        keepCompleted = true,
    ) {
        if (!id) return;
        try {
            await api.post(
                `/texts/${id}/sentence_translation_test/progress/clear`,
                {
                    keep_completed: keepCompleted,
                },
            );
            if (!keepCompleted) sentenceTranslationCompletedOnce = false;
        } catch (e) {}
    }

    async function saveSentenceTranslationProgressToServer() {
        if (!id) return;
        const passedIndices = Object.keys(sentenceTranslationPassedMap).map(
            (v) => Number(v),
        );

        if (!passedIndices.length) {
            await clearSentenceTranslationProgressOnServer(true);
            return;
        }

        try {
            await api.post(
                `/texts/${id}/sentence_translation_test/progress/save`,
                {
                    order: sentenceTranslationOrder,
                    cursor: sentenceTranslationCursor,
                    passed_indices: passedIndices,
                },
            );
        } catch (e) {}
    }

    async function markSentenceTranslationCompletedOnServer() {
        if (!id) return;
        sentenceTranslationCompletedOnce = true;
        try {
            await api.post(
                `/texts/${id}/sentence_translation_test/progress/complete`,
                {},
            );
        } catch (e) {}
    }

    async function openSentenceTranslationTest() {
        if (!sentences.length) return;
        showDictation = false;
        stopCurrentPlayback();
        const state = await fetchSentenceTranslationState();
        const savedProgress = state?.progress || null;

        if (
            savedProgress &&
            savedProgress.order.length === sentences.length &&
            savedProgress.passed_indices.length > 0
        ) {
            pendingSentenceTranslationProgress = savedProgress;
            showSentenceTranslationResumePrompt = true;
            showSentenceTranslationTest = true;
            return;
        }

        await startSentenceTranslationFromScratch();
    }

    async function startSentenceTranslationFromScratch() {
        await clearSentenceTranslationProgressOnServer(true);
        pendingSentenceTranslationProgress = null;
        showSentenceTranslationResumePrompt = false;
        sentenceTranslationOrder = shuffledIndices(sentences.length);
        sentenceTranslationCursor = 0;
        sentenceTranslationInput = "";
        sentenceTranslationResult = null;
        sentenceTranslationChecking = false;
        sentenceTranslationPassedMap = {};
        showSentenceTranslationSplash = false;
        showSentenceTranslationTest = true;
    }

    async function continueSentenceTranslationProgress() {
        const saved = pendingSentenceTranslationProgress;
        if (!saved || !Array.isArray(saved.order)) {
            await startSentenceTranslationFromScratch();
            return;
        }

        const passedMap = {};
        saved.passed_indices.forEach((idx) => {
            if (Number.isInteger(idx) && idx >= 0 && idx < sentences.length) {
                passedMap[idx] = true;
            }
        });

        const savedOrder = saved.order.filter(
            (idx) =>
                Number.isInteger(idx) && idx >= 0 && idx < sentences.length,
        );
        if (savedOrder.length !== sentences.length) {
            await startSentenceTranslationFromScratch();
            return;
        }

        let restoredCursor = Math.max(
            0,
            Math.min(saved.cursor || 0, savedOrder.length - 1),
        );
        while (
            restoredCursor < savedOrder.length &&
            passedMap[savedOrder[restoredCursor]]
        ) {
            restoredCursor += 1;
        }
        if (restoredCursor >= savedOrder.length) {
            restoredCursor = savedOrder.length - 1;
        }

        sentenceTranslationOrder = savedOrder;
        sentenceTranslationCursor = restoredCursor;
        sentenceTranslationInput = "";
        sentenceTranslationResult = null;
        sentenceTranslationChecking = false;
        sentenceTranslationPassedMap = passedMap;
        showSentenceTranslationResumePrompt = false;
        pendingSentenceTranslationProgress = null;
        showSentenceTranslationSplash = false;
        showSentenceTranslationTest = true;
    }

    async function closeSentenceTranslationTest() {
        showSentenceTranslationTest = false;
        showSentenceTranslationResumePrompt = false;
        pendingSentenceTranslationProgress = null;
        sentenceTranslationChecking = false;
        sentenceTranslationResult = null;
        sentenceTranslationInput = "";
        if (sentenceTranslationPassedCount > 0) {
            await saveSentenceTranslationProgressToServer();
        } else {
            await clearSentenceTranslationProgressOnServer(true);
        }
    }

    async function checkSentenceTranslation() {
        if (
            !sentenceTranslationCurrentSentence ||
            !sentenceTranslationInput.trim() ||
            sentenceTranslationChecking
        ) {
            return;
        }

        sentenceTranslationChecking = true;
        try {
            const res = await api.post(
                `/texts/${id}/sentence_translation_test/check`,
                {
                    sentence_index: sentenceTranslationCurrentSentenceIndex,
                    user_text: sentenceTranslationInput,
                    source_text:
                        sentenceTranslationCurrentSentence.display_trans,
                },
            );
            sentenceTranslationResult = res.data;
        } catch (e) {
            console.error(e);
            addToast(ui.error_generic, "error");
        } finally {
            sentenceTranslationChecking = false;
        }
    }

    async function nextSentenceTranslationSentence() {
        if (!sentenceTranslationPassedCurrentSentence) {
            addToast(ui.sentence_translation_need_repeat, "info");
            return;
        }

        if (sentenceTranslationCurrentSentenceIndex >= 0) {
            sentenceTranslationPassedMap = {
                ...sentenceTranslationPassedMap,
                [sentenceTranslationCurrentSentenceIndex]: true,
            };
            await saveSentenceTranslationProgressToServer();
        }

        if (!sentenceTranslationHasNext) {
            showSentenceTranslationTest = false;
            showSentenceTranslationResumePrompt = false;
            showSentenceTranslationSplash = true;
            await markSentenceTranslationCompletedOnServer();
            await clearSentenceTranslationProgressOnServer(true);
            setTimeout(
                () => launchConfettiInto("sentence-translation-splash"),
                250,
            );
            return;
        }

        sentenceTranslationCursor += 1;
        sentenceTranslationInput = "";
        sentenceTranslationResult = null;
        await saveSentenceTranslationProgressToServer();
    }

    async function retrySentenceTranslationSentence() {
        await checkSentenceTranslation();
    }

    function closeSentenceTranslationSplash() {
        showSentenceTranslationSplash = false;
        const container = document.getElementById(
            "sentence-translation-splash",
        );
        if (container) {
            const particles = container.querySelectorAll(".confetti");
            particles.forEach((p) => p.remove());
        }
    }

    function restartSentenceTranslationExam() {
        closeSentenceTranslationSplash();
        startSentenceTranslationFromScratch();
    }

    function stopCurrentPlayback() {
        isPlayingAll = false;
        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }
        playingIndex = -1;
        userInitiatedPlay = false;
        lastPlayedIdx = -1;
        vocabPlayingId = null;
        currentVocabPlayId = null;
    }

    function shuffledIndices(len) {
        const arr = Array.from({ length: len }, (_, i) => i);
        for (let i = arr.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [arr[i], arr[j]] = [arr[j], arr[i]];
        }
        return arr;
    }

    async function openDictation() {
        if (!sentences.length) return;
        showSentenceTranslationTest = false;
        stopCurrentPlayback();
        const state = await fetchDictationState();
        const savedProgress = state?.progress || null;

        if (
            savedProgress &&
            savedProgress.order.length === sentences.length &&
            savedProgress.passed_indices.length > 0
        ) {
            pendingDictationProgress = savedProgress;
            showDictationResumePrompt = true;
            showDictation = true;
            return;
        }

        await startDictationFromScratch();
    }

    async function startDictationFromScratch() {
        await clearDictationProgressOnServer(true);
        pendingDictationProgress = null;
        showDictationResumePrompt = false;
        dictationOrder = shuffledIndices(sentences.length);
        dictationCursor = 0;
        dictationInput = "";
        dictationResult = null;
        dictationChecking = false;
        dictationPlaying = false;
        dictationPlaybackRate = 0.8;
        dictationPassedMap = {};
        showDictationSplash = false;
        showDictation = true;
    }

    async function continueDictationProgress() {
        const saved = pendingDictationProgress;
        if (!saved || !Array.isArray(saved.order)) {
            await startDictationFromScratch();
            return;
        }

        const passedMap = {};
        saved.passed_indices.forEach((idx) => {
            if (Number.isInteger(idx) && idx >= 0 && idx < sentences.length) {
                passedMap[idx] = true;
            }
        });

        const savedOrder = saved.order.filter(
            (idx) =>
                Number.isInteger(idx) && idx >= 0 && idx < sentences.length,
        );
        if (savedOrder.length !== sentences.length) {
            await startDictationFromScratch();
            return;
        }

        let restoredCursor = Math.max(
            0,
            Math.min(saved.cursor || 0, savedOrder.length - 1),
        );
        while (
            restoredCursor < savedOrder.length &&
            passedMap[savedOrder[restoredCursor]]
        ) {
            restoredCursor += 1;
        }
        if (restoredCursor >= savedOrder.length) {
            restoredCursor = savedOrder.length - 1;
        }

        dictationOrder = savedOrder;
        dictationCursor = restoredCursor;
        dictationInput = "";
        dictationResult = null;
        dictationChecking = false;
        dictationPlaying = false;
        dictationPlaybackRate = Math.min(
            1,
            Math.max(0.4, Number(saved.playback_rate || 0.8)),
        );
        dictationPassedMap = passedMap;
        showDictationResumePrompt = false;
        pendingDictationProgress = null;
        showDictationSplash = false;
        showDictation = true;
    }

    async function closeDictation() {
        showDictation = false;
        showDictationResumePrompt = false;
        pendingDictationProgress = null;
        dictationPlaying = false;
        dictationChecking = false;
        dictationResult = null;
        dictationInput = "";
        if (dictationPassedCount > 0) {
            await saveDictationProgressToServer();
        } else {
            await clearDictationProgressOnServer(true);
        }
        stopCurrentPlayback();
    }

    async function playDictationSentence() {
        if (!dictationCurrentSentence || dictationPlaying) return;
        dictationPlaying = true;
        try {
            await playAudio(
                dictationCurrentSentence.de,
                dictationCurrentSentenceIndex,
                dictationPlaybackRate,
                true,
            );
        } finally {
            dictationPlaying = false;
        }
    }

    function stopDictationSentence() {
        if (currentAudio && playingIndex === dictationCurrentSentenceIndex) {
            currentAudio.pause();
            dictationPlaying = false;
        }
    }

    async function toggleDictationPlayback() {
        if (
            currentAudio &&
            currentAudio.paused &&
            playingIndex === dictationCurrentSentenceIndex
        ) {
            currentAudio.playbackRate = dictationPlaybackRate;
            dictationPlaying = true;
            currentAudio.play().catch(() => {
                dictationPlaying = false;
            });
            return;
        }

        if (dictationPlaying) {
            stopDictationSentence();
            return;
        }
        await playDictationSentence();
    }

    function restartDictationSentence() {
        if (!dictationCurrentSentence) return;

        if (currentAudio && playingIndex === dictationCurrentSentenceIndex) {
            currentAudio.currentTime = 0;
            currentAudio.playbackRate = dictationPlaybackRate;
            currentAudio.play().catch(() => {});
            dictationPlaying = true;
            return;
        }

        playDictationSentence();
    }

    function updateDictationSpeed(delta) {
        const nextRate = Math.min(
            1,
            Math.max(
                0.4,
                Math.round((dictationPlaybackRate + delta) * 10) / 10,
            ),
        );
        dictationPlaybackRate = nextRate;
        if (currentAudio && playingIndex === dictationCurrentSentenceIndex) {
            currentAudio.playbackRate = dictationPlaybackRate;
        }
    }

    async function nextDictationSentence() {
        if (!dictationPassedCurrentSentence) {
            addToast(ui.dictation_need_repeat, "info");
            return;
        }

        if (dictationCurrentSentenceIndex >= 0) {
            dictationPassedMap = {
                ...dictationPassedMap,
                [dictationCurrentSentenceIndex]: true,
            };
            await saveDictationProgressToServer();
        }

        if (!dictationHasNext) {
            showDictation = false;
            showDictationResumePrompt = false;
            showDictationSplash = true;
            await markDictationCompletedOnServer();
            await clearDictationProgressOnServer(true);
            setTimeout(() => launchConfettiInto("dictation-splash"), 250);
            return;
        }

        dictationCursor += 1;
        dictationInput = "";
        dictationResult = null;
        await saveDictationProgressToServer();
        await tick();
        await playDictationSentence();
    }

    async function retryDictationSentence() {
        dictationInput = "";
        dictationResult = null;
        await tick();
        await playDictationSentence();
    }

    function closeDictationSplash() {
        showDictationSplash = false;
        const container = document.getElementById("dictation-splash");
        if (container) {
            const particles = container.querySelectorAll(".confetti");
            particles.forEach((p) => p.remove());
        }
    }

    function restartDictationExam() {
        closeDictationSplash();
        startDictationFromScratch();
    }

    async function checkDictation() {
        if (
            !dictationCurrentSentence ||
            !dictationInput.trim() ||
            dictationChecking
        )
            return;

        if (currentAudio && playingIndex === dictationCurrentSentenceIndex) {
            currentAudio.pause();
            dictationPlaying = false;
        }

        dictationChecking = true;
        try {
            const res = await api.post(`/texts/${id}/dictation_check`, {
                sentence_index: dictationCurrentSentenceIndex,
                user_text: dictationInput,
            });
            dictationResult = res.data;
        } catch (e) {
            console.error(e);
            addToast(ui.error_generic, "error");
        } finally {
            dictationChecking = false;
        }
    }

    async function playAudio(
        txt,
        idx = -1,
        playbackRate = 1,
        preserveOnPause = false,
    ) {
        // If user clicks the same sentence while it's playing, pause it
        if (
            userInitiatedPlay &&
            idx === lastPlayedIdx &&
            currentAudio &&
            !currentAudio.paused
        ) {
            currentAudio.pause();
            currentAudio = null;
            playingIndex = -1;
            userInitiatedPlay = false;
            lastPlayedIdx = -1;
            return;
        }

        // Stop any currently playing audio (from previous playback)
        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }

        // If user clicked Play and Play All is running, stop Play All
        if (userInitiatedPlay && isPlayingAll) {
            isPlayingAll = false;
        }

        // Set highlighting and track this as the new playback
        if (idx !== -1) {
            playingIndex = idx;
            lastPlayedIdx = idx;
        }

        try {
            // Request audio for specific lesson sentence (generates on-demand)
            const res = await api.post(`/texts/${id}/generate_sentence_audio`, {
                sentence_index: idx,
                text: txt,
            });
            const audioUrl = res.data.url;

            if (!audioUrl) {
                console.error("Failed to get audio URL");
                if (!isPlayingAll) playingIndex = -1;
                userInitiatedPlay = false;
                lastPlayedIdx = -1;
                return Promise.resolve();
            }

            return new Promise((resolve) => {
                let settled = false;
                const finish = () => {
                    if (settled) return;
                    settled = true;
                    currentAudio = null;
                    if (!isPlayingAll) playingIndex = -1;
                    if (idx === dictationCurrentSentenceIndex) {
                        dictationPlaying = false;
                    }
                    userInitiatedPlay = false;
                    lastPlayedIdx = -1;
                    resolve();
                };

                currentAudio = new Audio(audioUrl);
                currentAudio.playbackRate = playbackRate;
                currentAudio.onended = finish;
                currentAudio.onerror = finish;
                currentAudio.onpause = () => {
                    if (preserveOnPause) {
                        if (settled) return;
                        resolve();
                        return;
                    }
                    finish();
                };
                currentAudio.play().catch((e) => {
                    finish();
                });
            });
        } catch (e) {
            console.error(e);
            if (!isPlayingAll) playingIndex = -1;
            userInitiatedPlay = false;
            lastPlayedIdx = -1;
            return Promise.resolve();
        }
    }

    async function playAll() {
        if (isPlayingAll) {
            isPlayingAll = false;
            if (currentAudio) currentAudio.pause();
            currentAudio = null;
            playingIndex = -1;
            userInitiatedPlay = false;
            lastPlayedIdx = -1;
            return;
        }

        // Clean up any existing playback state
        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }
        playingIndex = -1;
        userInitiatedPlay = false;
        lastPlayedIdx = -1;

        isPlayingAll = true;

        for (let i = 0; i < sentences.length; i++) {
            // Check if someone interrupted Play All by clicking on a specific sentence
            if (!isPlayingAll) break;

            playingIndex = i;

            // Scroll to sentence
            const el = document.getElementById(`sent-${i}`);
            if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });

            await playAudio(sentences[i].de, i);

            // Check again after playAudio completes
            if (!isPlayingAll) break;
            await new Promise((r) => setTimeout(r, 600));
        }

        isPlayingAll = false;
        playingIndex = -1;
        userInitiatedPlay = false;
        lastPlayedIdx = -1;
    }

    async function playVocabPair(de, trans, vocabId) {
        // If clicking the same word that's playing, toggle pause
        if (vocabPlayingId === vocabId && currentAudio) {
            currentAudio.pause();
            vocabPlayingId = null;
            return;
        }

        // Stop any currently playing audio and mark old session as aborted
        if (currentAudio) currentAudio.pause();
        const playSessionId = {}; // Unique object to track this play session
        currentVocabPlayId = playSessionId;
        vocabPlayingId = vocabId;

        try {
            const res = await api.post("/tts_pair", {
                de_text: de,
                trans_text: trans,
                source: "vocabulary",
            });
            const urls = res.data.urls;

            for (const url of urls) {
                // If this session was aborted (user clicked another word), stop immediately
                if (currentVocabPlayId !== playSessionId) {
                    return;
                }

                await new Promise((resolve) => {
                    currentAudio = new Audio(url);
                    currentAudio.onended = () => {
                        // Only resolve if this session is still active
                        if (currentVocabPlayId === playSessionId) {
                            resolve();
                        }
                    };
                    currentAudio.play().catch(resolve);
                });
                await new Promise((r) => setTimeout(r, 300));
            }

            // Clear playing state when finished (only if still current session)
            if (currentVocabPlayId === playSessionId) {
                vocabPlayingId = null;
            }
        } catch (e) {
            console.error(e);
            if (currentVocabPlayId === playSessionId) {
                vocabPlayingId = null;
            }
        }
    }

    // --- TRANSLATION & SELECTION ---

    function getCharOffset(container, node, offset) {
        let charCount = 0;
        const walker = document.createTreeWalker(
            container,
            NodeFilter.SHOW_TEXT,
            null,
            false,
        );
        let currentNode;
        while ((currentNode = walker.nextNode())) {
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

        if (
            event.target.closest("button") ||
            event.target.closest("#pop") ||
            event.target.classList.contains("learned") ||
            event.target.classList.contains("explained-word")
        )
            return;

        const selection = window.getSelection();
        let textStr = selection.toString().trim();

        // --- AUTO-EXPAND SELECTION LOGIC (From old project) ---
        if (!selection.isCollapsed && selection.rangeCount > 0) {
            const range = selection.getRangeAt(0);
            // Separator characters (everything that is NOT part of a word)
            const isSeparator = (char) => /[\s.,!?;:()\[\]"'«»]/.test(char);

            const container = range.commonAncestorContainer;
            const el =
                container.nodeType === 3 ? container.parentElement : container;

            // Work only inside lesson text
            if (el.closest && el.closest(".de-text")) {
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

        const sentenceEl = event.target.closest(".de-line");
        if (!sentenceEl) {
            showPopup = false;
            return;
        }

        const textSpan = sentenceEl.querySelector(".de-text");
        const transRow = sentenceEl.querySelector(".trans-row");

        // Перевіряємо, чи виділення **ТОЧНО** в .de-text (а не в .trans-row)
        if (!textSpan || !textSpan.contains(selection.anchorNode)) return;
        if (transRow && transRow.contains(selection.anchorNode)) return;

        // --- WORD COUNT LIMIT (тільки для .de-text) ---
        const wordCount = textStr
            .split(/\s+/)
            .filter((w) => w.length > 0).length;
        if (wordCount > 4) {
            addToast(ui.selection_limited_toast, "warning");
            showPopup = false;
            return;
        }

        // Stop if selection hits a learned word
        if (selection.rangeCount > 0) {
            const range = selection.getRangeAt(0);
            const fragment = range.cloneContents();
            if (fragment.querySelector(".learned, .explained-word")) {
                // Reset if crossing learned word
                showPopup = false;
                return;
            }
        }

        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();

        // Calculate precise index
        selectionStartIndex = getCharOffset(
            textSpan,
            range.startContainer,
            range.startOffset,
        );

        // Position Popup

        if (window.innerWidth > 768) {
            // Use fixed positioning to avoid issues with relative containers
            popupStyle = `position: fixed; top: ${rect.top - 45}px; left: ${rect.left + rect.width / 2}px; transform: translateX(-50%); z-index: 2000;`;
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

    function buildSentenceHtml(sentenceIndex) {
        const sentence = sentences[sentenceIndex];
        if (!sentence) return "";

        const originalText = sentence.de;

        const markers = [];
        const sentVocab = vocab.filter(
            (v) => v.sentence_index === sentenceIndex,
        );
        sentVocab.forEach((v) => {
            const start = v.start_index;
            const end = v.end_index;
            if (
                start !== null &&
                start !== undefined &&
                start >= 0 &&
                end <= originalText.length &&
                start < end
            ) {
                markers.push({
                    type: "learned",
                    start,
                    end,
                    id: v.id,
                });
            }
        });

        Object.values(explainedWordsMap).forEach((item) => {
            if (item.sentenceIndex !== sentenceIndex) return;
            if (
                item.startIndex >= 0 &&
                item.endIndex <= originalText.length &&
                item.startIndex < item.endIndex
            ) {
                markers.push({
                    type: "explained",
                    start: item.startIndex,
                    end: item.endIndex,
                    id: item.id,
                });
            }
        });

        markers.sort((a, b) => b.start - a.start);

        let html = "";
        let lastIdx = originalText.length;

        markers.forEach((m) => {
            html = originalText.substring(m.end, lastIdx) + html;
            const wordVal = originalText.substring(m.start, m.end);
            if (m.type === "learned") {
                html =
                    `<span class="learned" data-wid="${m.id}">${wordVal}</span>` +
                    html;
            } else {
                html =
                    `<span class="explained-word" data-eid="${m.id}">${wordVal}</span>` +
                    html;
            }
            lastIdx = m.start;
        });

        html = originalText.substring(0, lastIdx) + html;
        return html;
    }

    function refreshSentenceHtml(sentenceIndex) {
        const sentence = sentences[sentenceIndex];
        if (!sentence) return;
        sentences[sentenceIndex] = {
            ...sentence,
            de_html: buildSentenceHtml(sentenceIndex),
        };
        sentences = sentences;
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function renderExplainItems(items) {
        if (!Array.isArray(items) || items.length === 0) return "";
        const isUkr = $user?.interface_language === "ukr";
        const rows = items
            .map((item) => {
                const w = escapeHtml(item.word);
                const translation = isUkr
                    ? escapeHtml(item.translation_uk)
                    : escapeHtml(item.translation_en);
                return `<li class="explain-item"><span class="explain-lemma">${w}</span><span class="explain-sep">-</span><span class="explain-translation">${translation}</span></li>`;
            })
            .join("");
        return `<ul class="explain-list">${rows}</ul>`;
    }

    function formatExplanationPopup(explanation) {
        if (!explanation || typeof explanation !== "object") {
            return `<div style="font-weight:500; color:var(--primary);">${escapeHtml(ui.explain_no_data || "No explanation data")}</div>`;
        }

        const targetWord = escapeHtml(explanation.target_word || "");
        const derivatives = explanation.derivatives || {};

        let html = `<div style="font-weight:700; color:var(--primary); margin-bottom:8px;">${targetWord}</div>`;

        const nouns = renderExplainItems(derivatives.nouns);
        const verbs = renderExplainItems(derivatives.verbs);
        const adjAdv = renderExplainItems(derivatives.adjectives_adverbs);
        const synonyms = renderExplainItems(explanation.synonyms);
        const antonyms = renderExplainItems(explanation.antonyms);

        const wrapSection = (cls, title, body) =>
            `<section class="explain-section ${cls}"><div class="explain-section-title">${title}</div>${body}</section>`;

        html = `<div class="explain-popup">${html}`;

        if (nouns)
            html += wrapSection(
                "explain-nouns",
                escapeHtml(ui.explain_nouns || "Nouns"),
                nouns,
            );
        if (verbs)
            html += wrapSection(
                "explain-verbs",
                escapeHtml(ui.explain_verbs || "Verbs"),
                verbs,
            );
        if (adjAdv)
            html += wrapSection(
                "explain-adj-adv",
                escapeHtml(ui.explain_adj_adv || "Adjectives / Adverbs"),
                adjAdv,
            );
        if (synonyms)
            html += wrapSection(
                "explain-synonyms",
                escapeHtml(ui.explain_synonyms || "Synonyms"),
                synonyms,
            );
        if (antonyms)
            html += wrapSection(
                "explain-antonyms",
                escapeHtml(ui.explain_antonyms || "Antonyms"),
                antonyms,
            );

        html += "</div>";

        return html;
    }

    function clearLearnedPopupTimer() {
        if (hideTimeout) {
            clearTimeout(hideTimeout);
            hideTimeout = null;
        }
    }

    function closeLearnedPopup() {
        clearLearnedPopupTimer();
        showLearnedPopup = false;
        learnedPopupSticky = false;
    }

    function scheduleLearnedPopupHide(delayMs = 2000) {
        if (learnedPopupSticky) return;
        clearLearnedPopupTimer();
        hideTimeout = setTimeout(() => {
            showLearnedPopup = false;
        }, delayMs);
    }

    function onLearnedPopupMouseEnter() {
        clearLearnedPopupTimer();
    }

    function onLearnedPopupMouseLeave() {
        scheduleLearnedPopupHide(1200);
    }

    function buildLearnedPopupStyle(rect, preferAbove = true) {
        const margin = 12;
        const centerX = rect.left + rect.width / 2;
        const clampedLeft = Math.max(
            margin,
            Math.min(window.innerWidth - margin, centerX),
        );

        const canPlaceAbove = rect.top > 240;
        if (preferAbove && canPlaceAbove) {
            return `top: ${rect.top - 8}px; left: ${clampedLeft}px; transform: translate(-50%, -100%); display: block; position: fixed;`;
        }

        return `top: ${rect.bottom + 10}px; left: ${clampedLeft}px; transform: translateX(-50%); display: block; position: fixed;`;
    }

    function buildExplainPopupStyle() {
        return "top: 6vh; left: 50%; transform: translateX(-50%); display: block; position: fixed; width: min(576px, 94vw); max-height: 88vh;";
    }

    function onPopupMouseLeave() {
        // Запускаємо таймер прихованого коли курсор покидає попап (2 секунди)
        popupHideTimeout = setTimeout(() => {
            showPopup = false;
        }, 2000);
    }

    async function reportText() {
        if (!text) return;

        const isUkr = $user?.interface_language === "ukr";
        const title = isUkr ? "Повідомити про проблему?" : "Report issue?";
        const message = isUkr
            ? "Цей текст буде позначений як проблемний для адміністраторів, і ви більше його не будете бачити."
            : "This text will be reported to administrators and won't appear for you again.";
        const okText = isUkr ? "Повідомити" : "Report";
        const cancelText = isUkr ? "Скасувати" : "Cancel";

        const confirmed = await confirmModal.ask(
            title,
            message,
            okText,
            cancelText,
            true,
        );

        if (!confirmed) return;

        try {
            await api.post("/report_text", { id });
            addToast(ui.text_reported || "Reported", "success");
            router.goto("/library");
        } catch (e) {
            console.error(e);
        }
    }

    async function quickTranslate() {
        // Блокируем двойное нажатие
        if (isTranslating) return;

        isTranslating = true;

        try {
            const res = await api.post("/quick_translate", {
                text: selectedText,
                ctx: selectionContext,
                tid: id,
                sent_idx: selectionSentenceIndex,
                start_char_index: selectionStartIndex,
            });

            if (res.data.ok) {
                // Оновлюємо локально без перезавантаження
                const newWord = res.data.word;

                // Додаємо до vocab масиву
                vocab = [...vocab, newWord];
                vocabMap[newWord.id] = newWord;

                // Оновлюємо sentences з новим highlight
                const sentIdx = selectionSentenceIndex;
                refreshSentenceHtml(sentIdx);

                // Update energy if returned
                if (res.data.energy_left !== undefined) {
                    user.update((u) => ({
                        ...u,
                        billing: {
                            ...u.billing,
                            energy_left: res.data.energy_left,
                            daily_spending: res.data.daily_spending,
                        },
                    }));
                }

                showPopup = false;
                window.getSelection().removeAllRanges();
                addToast(ui.word_added, "success");
            } else {
                // Показуємо "word_exists" як попередження (жовте), а не помилку (червоне)
                const toastType =
                    res.data.error_key === "word_exists" ? "warning" : "error";
                addToast(
                    ui[res.data.error_key] || ui.translation_failed_msg,
                    toastType,
                );
            }
        } catch (e) {
            console.error(e);
            addToast(ui.error_generic, "error");
        } finally {
            isTranslating = false;
        }
    }

    async function onExplainClick() {
        if (isTranslating) return;
        if (!isSingleWordSelected) {
            addToast(ui.explain_single_word_only, "warning");
            return;
        }

        isTranslating = true;
        try {
            const res = await api.post("/explain_word", {
                text: selectedText,
                tid: id,
                sent_idx: selectionSentenceIndex,
                start_char_index: selectionStartIndex,
            });

            if (!res.data?.ok) {
                addToast(
                    ui[res.data?.error_key] || ui.explain_failed_msg,
                    "error",
                );
                return;
            }

            const explained = res.data.explained_word;
            explainedWordsMap[explained.id] = {
                id: explained.id,
                sentenceIndex: explained.sentence_index,
                startIndex: explained.start_index,
                endIndex: explained.end_index,
                text: explained.text,
                explanation: explained.explanation,
            };
            explainedWordsMap = explainedWordsMap;

            refreshSentenceHtml(selectionSentenceIndex);

            showPopup = false;
            window.getSelection().removeAllRanges();
            addToast(ui.explain_ready, "success");
        } catch (e) {
            console.error(e);
            addToast(ui.explain_failed_msg, "error");
        } finally {
            isTranslating = false;
        }
    }

    function scrollToWord(wid) {
        const el = document.querySelector(`.learned[data-wid="${wid}"]`);
        if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "center" });
            // Optional: highlight effect
            // el.classList.add('highlight-word');
        }
    }

    // --- LEARNED WORD POPUP ---

    function handleLearnedClick(e) {
        const target = e.target;

        // Ignore clicks inside popup content itself.
        if (target.closest("#learned-pop")) {
            return;
        }

        if (target.classList.contains("learned")) {
            const wid = target.dataset.wid;
            const word = vocabMap[wid];
            if (word) {
                const rect = target.getBoundingClientRect();

                const trans =
                    $user.interface_language === "ukr" ? word.ua : word.en;
                learnedPopupContent = `<div style="font-weight:500; color:var(--bg);">${trans}</div>`;

                learnedPopupSticky = false;
                learnedPopupStyle = buildLearnedPopupStyle(rect, true);
                showLearnedPopup = true;
                scheduleLearnedPopupHide(2000);
            }
        } else if (target.classList.contains("explained-word")) {
            const eid = target.dataset.eid;
            const explained = explainedWordsMap[eid];
            if (explained?.explanation) {
                learnedPopupContent = formatExplanationPopup(
                    explained.explanation,
                );

                learnedPopupSticky = true;
                clearLearnedPopupTimer();
                learnedPopupStyle = buildExplainPopupStyle();
                showLearnedPopup = true;
            }
        } else {
            closeLearnedPopup();
        }
    }

    // --- QUIZ LOGIC ---

    function startQuiz() {
        switchTab("quiz");
    }

    function initQuizState() {
        activeTab = "quiz";

        // Якщо квіз не активний, перевіряємо, чи є старий результат для показу
        if (
            !quizActive &&
            lastQuizResult &&
            lastQuizResult.score !== undefined
        ) {
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
            await api.post("/save_quiz_result", {
                text_id: id,
                score: quizScore,
                total: quizData.length,
            });
        } catch (e) {}

        if (scorePct >= 100) {
            setTimeout(launchConfetti, 300);
        }
    }

    async function abortQuiz() {
        const ok = await confirmModal.ask(
            ui.abort_confirm_title,
            ui.abort_confirm_msg,
            ui.exit_btn,
            ui.btn_cancel,
            true,
        );
        if (ok) {
            activeTab = "vocab";
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
        const container = document.getElementById("quiz-splash");
        if (container) {
            const particles = container.querySelectorAll(".confetti");
            particles.forEach((p) => p.remove());
        }
    }

    function launchConfetti() {
        launchConfettiInto("quiz-splash");
    }

    function launchConfettiInto(containerId) {
        const colors = ["#FFC107", "#2196F3", "#4CAF50", "#F44336", "#9C27B0"];
        const container = document.getElementById(containerId);
        if (!container) return;

        for (let i = 0; i < 50; i++) {
            const el = document.createElement("div");
            el.classList.add("confetti");
            el.style.left = Math.random() * 100 + "%";
            el.style.backgroundColor =
                colors[Math.floor(Math.random() * colors.length)];
            el.style.animation = `fall ${Math.random() * 3 + 2}s linear forwards`;
            container.appendChild(el);
        }
    }

    // --- TABS & NAVIGATION GUARD ---

    // Sentence button hover/translation modes
    function onSentenceButtonHover(sentenceIndex) {
        // Clear any existing timer for this sentence
        if (sentenceHoverTimers[sentenceIndex]) {
            clearTimeout(sentenceHoverTimers[sentenceIndex]);
        }

        // Set mode to 'play' immediately
        sentenceButtonMode[sentenceIndex] = "play";
        sentenceButtonMode = sentenceButtonMode; // Trigger reactivity

        // Start timer to switch to 'translate' mode after 1 second
        sentenceHoverTimers[sentenceIndex] = setTimeout(() => {
            sentenceButtonMode[sentenceIndex] = "translate";
            sentenceButtonMode = sentenceButtonMode; // Trigger reactivity
        }, 1000);
    }

    function onSentenceButtonLeave(sentenceIndex) {
        // Clear timer
        if (sentenceHoverTimers[sentenceIndex]) {
            clearTimeout(sentenceHoverTimers[sentenceIndex]);
            delete sentenceHoverTimers[sentenceIndex];
        }

        // Reset mode to normal
        sentenceButtonMode[sentenceIndex] = "normal";
        sentenceButtonMode = sentenceButtonMode; // Trigger reactivity
    }

    function onSentenceButtonClick(sentenceIndex, sentence) {
        const mode = sentenceButtonMode[sentenceIndex];

        if (mode === "translate" || mode === "normal") {
            // Show translation for 5 seconds
            sentenceTranslationDisplay[sentenceIndex] = true;
            sentenceTranslationDisplay = sentenceTranslationDisplay; // Trigger reactivity

            // Clear previous timer if exists
            if (sentenceTranslationTimers[sentenceIndex]) {
                clearTimeout(sentenceTranslationTimers[sentenceIndex]);
            }

            // Hide translation after 5 seconds
            sentenceTranslationTimers[sentenceIndex] = setTimeout(() => {
                sentenceTranslationDisplay[sentenceIndex] = false;
                sentenceTranslationDisplay = sentenceTranslationDisplay; // Trigger reactivity
                delete sentenceTranslationTimers[sentenceIndex];
            }, 5000);
        } else if (mode === "play") {
            // Play audio (same as before)
            userInitiatedPlay = true;
            playAudio(sentence.de, sentenceIndex);
        }
    }

    function switchTab(tab) {
        if (activeTab === tab) return;

        // Захист від випадкового виходу з квізу
        if (
            activeTab === "quiz" &&
            quizActive &&
            (currentQIndex > 0 || isChecked)
        ) {
            if (!confirm(ui.abort_confirm_msg)) return;
            // Якщо користувач погодився вийти - скидаємо прогрес
            quizActive = false;
            currentQIndex = 0;
            isChecked = false;
        }

        activeTab = tab;

        // Якщо пішли з квіза, але не було прогресу - просто скидаємо активність
        if (activeTab !== "quiz") {
            quizActive = false;
        }
        if (tab === "quiz") {
            initQuizState();
        }
    }

    // Захист від закриття вкладки/оновлення
    function handleBeforeUnload(e) {
        if (
            activeTab === "quiz" &&
            quizActive &&
            (currentQIndex > 0 || isChecked)
        ) {
            e.preventDefault();
            e.returnValue = "";
            return "";
        }
    }

    function handleViewKeydown(e) {
        if (showSentenceTranslationSplash) {
            if (e.key === "Escape") {
                e.preventDefault();
                closeSentenceTranslationSplash();
            }
            return;
        }

        if (showSentenceTranslationTest) {
            if (e.key === "Escape") {
                e.preventDefault();
                closeSentenceTranslationTest();
            }
            return;
        }

        if (showDictationSplash) {
            if (e.key === "Escape") {
                e.preventDefault();
                closeDictationSplash();
            }
            return;
        }

        if (!showDictation) return;

        if (e.key === "1") {
            e.preventDefault();
            toggleDictationPlayback();
            return;
        }

        if (e.key === "2") {
            e.preventDefault();
            restartDictationSentence();
            return;
        }

        if (e.key === "3") {
            e.preventDefault();
            updateDictationSpeed(-0.1);
            return;
        }

        if (e.key === "4") {
            e.preventDefault();
            updateDictationSpeed(0.1);
            return;
        }

        if (e.key === "Escape") {
            e.preventDefault();
            closeDictation();
        }
    }

    // --- ACTIONS ---

    async function toggleTextFav() {
        try {
            await api.post("/toggle_text_fav", { id });
            text.is_favorite = text.is_favorite ? 0 : 1;
        } catch (e) {}
    }

    async function toggleVocabFav(wid) {
        try {
            await api.post("/toggle_fav", { id: wid });
            // Update local state
            vocab = vocab.map((v) => {
                if (v.id === wid)
                    return { ...v, is_favorite: v.is_favorite ? 0 : 1 };
                return v;
            });
        } catch (e) {
            console.error(e);
        }
    }

    async function removeWord(wid) {
        // No confirm needed, using undo toast flow

        // 1. Optimistic UI update
        // Hide from vocab list
        vocab = vocab.filter((v) => v.id !== wid);
        // Remove highlight from text
        const highlights = document.querySelectorAll(
            `.learned[data-wid="${wid}"]`,
        );
        highlights.forEach((span) => {
            const textNode = document.createTextNode(span.innerText);
            span.parentNode.replaceChild(textNode, span);
        });

        // 2. Set up delayed delete
        const deleteTimeout = setTimeout(() => {
            api.post("/remove_word", { id: wid, from_vocab: false }).catch(
                (e) => {
                    console.error("Final delete failed:", e);
                    addToast("Error, reloading...", "error");
                    setTimeout(() => location.reload(), 1500);
                },
            );
        }, 5000);

        // 3. Show toast with undo
        const undo = () => {
            clearTimeout(deleteTimeout);
            loadText(); // Easiest way to restore state
        };

        addToast(ui.word_deleted || "Word removed", "info", undo, 5000);
    }

    function startEdit(wid, currentVal, fieldType) {
        editingId = wid;
        editValue = currentVal;
        editingFieldType = fieldType;
    }

    function cancelEdit() {
        editingId = null;
        editValue = "";
        editingFieldType = "";
    }

    async function saveEdit(wid) {
        try {
            await api.post("/update_word", { id: wid, translation: editValue });
            vocab = vocab.map((v) => {
                if (v.id === wid) {
                    const fieldName = editingFieldType === "ua" ? "ua" : "en";
                    return { ...v, [fieldName]: editValue };
                }
                return v;
            });
            editingId = null;
        } catch (e) {
            addToast(ui.error_saving || "Error saving", "error");
        }
    }

    // Global click listener for learned words popup
    onMount(() => {
        window.addEventListener("beforeunload", handleBeforeUnload);
        document.addEventListener("click", handleLearnedClick);
        window.addEventListener("keydown", handleViewKeydown);
        fetchDictationState();
        fetchSentenceTranslationState();
    });

    // Підсвічування речення при переході з Vocab (через URL hash #sent-N)
    async function highlightSentenceFromHash() {
        const hash = window.location.hash; // e.g. #sent-3
        if (!hash || !hash.startsWith("#sent-")) return;

        await tick();
        const el = document.getElementById(hash.slice(1)); // 'sent-3'
        if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "center" });
            el.classList.add("highlight-sentence");
            setTimeout(() => el.classList.remove("highlight-sentence"), 2500);
            // Очищуємо hash щоб не підсвічувати при наступному re-render
            history.replaceState(null, "", window.location.pathname);
        }
    }

    onDestroy(() => {
        window.removeEventListener("beforeunload", handleBeforeUnload);
        if (typeof document !== "undefined")
            document.removeEventListener("click", handleLearnedClick);
        window.removeEventListener("keydown", handleViewKeydown);
        if (currentAudio) currentAudio.pause();

        clearLearnedPopupTimer();

        // Clean up all timers
        Object.values(sentenceHoverTimers).forEach((timer) =>
            clearTimeout(timer),
        );
        Object.values(sentenceTranslationTimers).forEach((timer) =>
            clearTimeout(timer),
        );
    });
</script>

<div
    class="view-container"
    onmouseup={handleMouseUp}
    role="button"
    tabindex="0"
>
    {#if loading}
        <div style="text-align: center; padding: 50px; opacity: 0.6;">
            {ui.loading}
        </div>
    {:else if text}
        <div class="card">
            {#if editingTitle}
                <div
                    style="display:flex; align-items:center; gap:6px; margin:0 0 4px 0;"
                >
                    <input
                        type="text"
                        class="edit-input"
                        bind:value={editTitleValue}
                        maxlength="60"
                        style="font-size:1.4rem; font-weight:600; flex:1;"
                        onkeydown={(e) => {
                            if (e.key === "Enter") saveTitleEdit();
                            if (e.key === "Escape") cancelTitleEdit();
                        }}
                    />
                    <button
                        class="btn-text"
                        onclick={saveTitleEdit}
                        style="padding:0; min-width:32px;"
                    >
                        <span class="material-symbols-outlined">check</span>
                    </button>
                    <button
                        class="btn-text"
                        onclick={cancelTitleEdit}
                        style="padding:0; min-width:32px;"
                    >
                        <span class="material-symbols-outlined">close</span>
                    </button>
                </div>
            {:else}
                <div
                    style="display:flex; align-items:center; gap:6px; margin:0 0 4px 0;"
                >
                    <h1 style="font-size:1.5rem; margin:0; flex:1;">
                        {text.custom_title || JSON.parse(text.title).de}
                    </h1>
                    <button
                        class="btn-text"
                        onclick={() => {
                            editTitleValue =
                                text.custom_title || JSON.parse(text.title).de;
                            editingTitle = true;
                        }}
                        style="padding:0; min-width:28px; opacity:0.4;"
                        title="Rename"
                    >
                        <span
                            class="material-symbols-outlined"
                            style="font-size:18px;">edit</span
                        >
                    </button>
                </div>
            {/if}
            <h2
                style="font-size: 1rem; color: var(--on-surface); opacity: 0.6; margin: 0 0 16px 0; font-weight: 400;"
            >
                {JSON.parse(text.title)[
                    $user.interface_language === "ukr" ? "ukr" : "eng"
                ] || ""}
            </h2>

            <div class="toolbar">
                <span
                    class="level-badge lvl-{text.level.toLowerCase()}"
                    style="margin-right: 12px;">{text.level}</span
                >

                <button
                    class="badge-btn"
                    onclick={() => (showTrans = !showTrans)}
                >
                    <span class="material-symbols-outlined"
                        >{showTrans ? "visibility_off" : "translate"}</span
                    >
                </button>

                <button
                    class="badge-btn"
                    onclick={toggleTextFav}
                    style="color: {text.is_favorite ? '#d32f2f' : 'inherit'}"
                >
                    <span
                        class="material-symbols-outlined {text.is_favorite
                            ? 'filled'
                            : ''}">favorite</span
                    >
                </button>

                <button
                    class="report-btn"
                    title={ui.report_sentence}
                    onclick={reportText}
                >
                    <span class="material-symbols-outlined">flag</span>
                </button>

                <button
                    class="badge-btn dictation-launch-btn"
                    onclick={openDictation}
                    style="margin-left: auto;"
                    title={ui.dictation}
                >
                    <span class="material-symbols-outlined">stylus_note</span>
                    {#if dictationCompletedOnce}
                        <span
                            class="dictation-done-badge"
                            title={ui.dictation_completed_badge || "Completed"}
                        >
                            <span class="material-symbols-outlined"
                                >check_circle</span
                            >
                        </span>
                    {/if}
                </button>

                <button
                    class="badge-btn dictation-launch-btn"
                    onclick={openSentenceTranslationTest}
                    title={ui.sentence_translation_test}
                >
                    <span class="material-symbols-outlined">g_translate</span>
                    {#if sentenceTranslationCompletedOnce}
                        <span
                            class="dictation-done-badge"
                            title={ui.sentence_translation_completed_badge ||
                                "Completed"}
                        >
                            <span class="material-symbols-outlined"
                                >check_circle</span
                            >
                        </span>
                    {/if}
                </button>

                <button class="btn-contained" onclick={playAll}>
                    <span class="material-symbols-outlined"
                        >{isPlayingAll ? "pause" : "play_arrow"}</span
                    >
                    {isPlayingAll ? ui.stop : ui.play_all}
                </button>
            </div>

            <div class="text-body">
                {#each sentences as s, i}<span
                        class="de-line {playingIndex === i
                            ? 'highlight-sentence'
                            : ''}"
                        id="sent-{i}"
                        data-index={i}
                        data-text={s.de}
                        ><span
                            class="sent-num-btn {playingIndex === i &&
                            currentAudio &&
                            !currentAudio.paused
                                ? 'playing'
                                : ''}"
                            role="button"
                            tabindex="0"
                            onmouseenter={() => onSentenceButtonHover(i)}
                            onmouseleave={() => onSentenceButtonLeave(i)}
                            onclick={() => onSentenceButtonClick(i, s)}
                            onkeydown={(e) =>
                                e.key === "Enter" &&
                                onSentenceButtonClick(i, s)}
                            ><span class="sent-num-label">{i + 1}</span><span
                                class="sent-num-icon material-symbols-outlined"
                                >{sentenceButtonMode[i] === "translate" &&
                                !showTrans
                                    ? "translate"
                                    : playingIndex === i &&
                                        currentAudio &&
                                        !currentAudio.paused
                                      ? "pause"
                                      : "play_arrow"}</span
                            ></span
                        ><span class="de-text">{@html s.de_html}</span
                        >{#if showTrans}
                            <span class="trans-row">{s.display_trans}</span
                            >{/if}{#if sentenceTranslationDisplay[i]}
                            <span class="sentence-translation-popup"
                                >{s.display_trans}</span
                            >{/if}</span
                    >
                {/each}
            </div>
        </div>

        {#if showDictation}
            <div class="dictation-overlay" role="dialog" aria-modal="true">
                {#if !showDictationResumePrompt}
                    <button
                        class="dictation-close-btn"
                        onclick={closeDictation}
                        aria-label="Close"
                    >
                        <span class="material-symbols-outlined">close</span>
                        <div class="dictation-close-hint">Esc</div>
                    </button>
                {/if}

                <div class="dictation-container">
                    {#if showDictationResumePrompt}
                        <div class="dictation-resume-actions">
                            <button
                                class="btn-contained"
                                onclick={startDictationFromScratch}
                            >
                                {ui.dictation_restart_btn || ui.restart_btn}
                            </button>
                            <button
                                class="btn-contained"
                                onclick={continueDictationProgress}
                            >
                                {ui.dictation_continue_btn || ui.continue_btn}
                            </button>
                        </div>
                    {:else}
                        <div class="fc-progress-wrapper">
                            <div class="fc-progress-track">
                                <div
                                    class="fc-progress-fill"
                                    style="width: {(dictationCursor /
                                        Math.max(dictationOrder.length, 1)) *
                                        100}%"
                                ></div>
                            </div>
                            <div class="fc-progress-text">
                                {Math.min(
                                    dictationCursor + 1,
                                    dictationOrder.length,
                                )} / {dictationOrder.length}
                            </div>
                        </div>

                        <div class="dictation-main-actions">
                            <button
                                class="dictation-play-btn"
                                onclick={toggleDictationPlayback}
                                disabled={!dictationCurrentSentence}
                            >
                                <span class="material-symbols-outlined"
                                    >{dictationPlaying
                                        ? "pause"
                                        : "play_arrow"}</span
                                >
                            </button>
                            <div class="dictation-play-caption">
                                {ui.dictation_play_btn ||
                                    (($user?.interface_language || "ukr") ===
                                    "eng"
                                        ? "Play"
                                        : "Грати")}
                            </div>
                            <div class="dictation-play-hotkey">
                                {ui.dictation_hotkeys_hint ||
                                    (($user?.interface_language || "ukr") ===
                                    "eng"
                                        ? "1 Play/Stop - 2 Restart - 3 Slower - 4 Faster"
                                        : "1 Грати/Пауза - 2 Спочатку - 3 Повільніше - 4 Швидше")}
                            </div>
                        </div>

                        {#if !dictationResult}
                            <textarea
                                class="dictation-input"
                                bind:value={dictationInput}
                                placeholder={ui.dictation_input_placeholder}
                                rows="4"
                            ></textarea>
                        {/if}

                        <div class="dictation-actions">
                            {#if !dictationResult}
                                <button
                                    class="btn-contained"
                                    onclick={checkDictation}
                                    disabled={!dictationInput.trim() ||
                                        dictationChecking}
                                >
                                    {ui.dictation_check_btn}
                                </button>
                            {:else}
                                <button
                                    class="btn-contained"
                                    onclick={retryDictationSentence}
                                >
                                    {ui.retry_btn}
                                </button>
                                <button
                                    class="btn-contained dictation-next-btn"
                                    onclick={nextDictationSentence}
                                    disabled={!dictationPassedCurrentSentence ||
                                        dictationPlaying}
                                >
                                    {dictationHasNext
                                        ? ui.dictation_next_btn
                                        : ui.dictation_finish_btn ||
                                          ui.done_btn}
                                </button>
                            {/if}
                        </div>

                        {#if dictationResult}
                            <div class="dictation-result-card">
                                <div class="dictation-score">
                                    {ui.dictation_similarity}:
                                    <strong
                                        >{Number(
                                            dictationResult.similarity_score,
                                        ).toFixed(2)}%</strong
                                    >
                                </div>

                                {#if !dictationPassedCurrentSentence}
                                    <div class="dictation-repeat-warning">
                                        {ui.dictation_need_repeat}
                                    </div>
                                {/if}

                                <div class="dictation-diff-block">
                                    <div class="dictation-diff-label">
                                        {ui.dictation_original}
                                    </div>
                                    <div class="dictation-diff-line expected">
                                        {#each dictationResult.segments as seg}
                                            {#if seg.expected}
                                                <span
                                                    class="diff-chip {seg.type}"
                                                >
                                                    {seg.expected}
                                                </span>
                                            {/if}
                                        {/each}
                                    </div>
                                </div>

                                <div class="dictation-diff-block">
                                    <div class="dictation-diff-label">
                                        {ui.dictation_your_text}
                                    </div>
                                    <div class="dictation-diff-line actual">
                                        {#each dictationResult.segments as seg}
                                            {#if seg.actual}
                                                <span
                                                    class="diff-chip {seg.type}"
                                                >
                                                    {seg.actual}
                                                </span>
                                            {:else if seg.type === "delete"}
                                                <span
                                                    class="diff-chip diff-missing"
                                                >
                                                    [missing]
                                                </span>
                                            {/if}
                                        {/each}
                                    </div>
                                </div>
                            </div>
                        {/if}
                    {/if}
                </div>
            </div>
        {/if}

        {#if showSentenceTranslationTest}
            <div class="dictation-overlay" role="dialog" aria-modal="true">
                {#if !showSentenceTranslationResumePrompt}
                    <button
                        class="dictation-close-btn"
                        onclick={closeSentenceTranslationTest}
                        aria-label="Close"
                    >
                        <span class="material-symbols-outlined">close</span>
                        <div class="dictation-close-hint">Esc</div>
                    </button>
                {/if}

                <div class="dictation-container translation-test-container">
                    {#if showSentenceTranslationResumePrompt}
                        <div class="dictation-resume-actions">
                            <button
                                class="btn-contained"
                                onclick={startSentenceTranslationFromScratch}
                            >
                                {ui.dictation_restart_btn || ui.restart_btn}
                            </button>
                            <button
                                class="btn-contained"
                                onclick={continueSentenceTranslationProgress}
                            >
                                {ui.dictation_continue_btn || ui.continue_btn}
                            </button>
                        </div>
                    {:else}
                        <div class="fc-progress-wrapper">
                            <div class="fc-progress-track">
                                <div
                                    class="fc-progress-fill"
                                    style="width: {(sentenceTranslationCursor /
                                        Math.max(
                                            sentenceTranslationOrder.length,
                                            1,
                                        )) *
                                        100}%"
                                ></div>
                            </div>
                            <div class="fc-progress-text">
                                {Math.min(
                                    sentenceTranslationCursor + 1,
                                    sentenceTranslationOrder.length,
                                )} / {sentenceTranslationOrder.length}
                            </div>
                        </div>

                        <div class="translation-source-card">
                            <div class="translation-source-label">
                                {ui.sentence_translation_source_label}
                            </div>
                            <div class="translation-source-text">
                                {sentenceTranslationCurrentSentence?.display_trans ||
                                    ""}
                            </div>
                        </div>

                        <textarea
                            class="dictation-input"
                            bind:value={sentenceTranslationInput}
                            placeholder={ui.sentence_translation_input_placeholder}
                            rows="4"
                            disabled={sentenceTranslationChecking}
                        ></textarea>

                        <div class="dictation-actions">
                            {#if !sentenceTranslationResult}
                                <button
                                    class="btn-contained"
                                    onclick={checkSentenceTranslation}
                                    disabled={!sentenceTranslationInput.trim() ||
                                        sentenceTranslationChecking}
                                >
                                    {#if sentenceTranslationChecking}
                                        <span class="loader-spinner"></span>
                                        {ui.loading}
                                    {:else}
                                        {ui.sentence_translation_check_btn}
                                    {/if}
                                </button>
                            {:else}
                                <button
                                    class="btn-contained"
                                    onclick={retrySentenceTranslationSentence}
                                    disabled={!sentenceTranslationInput.trim() ||
                                        sentenceTranslationChecking}
                                >
                                    {#if sentenceTranslationChecking}
                                        <span class="loader-spinner"></span>
                                        {ui.loading}
                                    {:else}
                                        {ui.retry_btn}
                                    {/if}
                                </button>
                                <button
                                    class="btn-contained dictation-next-btn"
                                    onclick={nextSentenceTranslationSentence}
                                    disabled={!sentenceTranslationPassedCurrentSentence}
                                >
                                    {sentenceTranslationHasNext
                                        ? ui.sentence_translation_next_btn
                                        : ui.sentence_translation_finish_btn}
                                </button>
                            {/if}
                        </div>

                        {#if sentenceTranslationResult}
                            <div class="dictation-result-card">
                                <div class="dictation-score">
                                    {ui.sentence_translation_accuracy}:
                                    <strong
                                        >{Number(
                                            sentenceTranslationResult.accuracy_score,
                                        ).toFixed(2)}%</strong
                                    >
                                </div>

                                {#if !sentenceTranslationPassedCurrentSentence}
                                    <div class="dictation-repeat-warning">
                                        {ui.sentence_translation_need_repeat}
                                    </div>
                                {/if}

                                <div class="dictation-diff-block">
                                    <div class="dictation-diff-label">
                                        {ui.sentence_translation_hint}
                                    </div>
                                    <div class="dictation-diff-line">
                                        {sentenceTranslationResult.feedback}
                                    </div>
                                </div>

                                {#if sentenceTranslationPassedCurrentSentence && sentenceTranslationResult.expected_text}
                                    <div class="dictation-diff-block">
                                        <div class="dictation-diff-label">
                                            {ui.dictation_original}
                                        </div>
                                        <div
                                            class="dictation-diff-line sentence-translation-correct"
                                        >
                                            {sentenceTranslationResult.expected_text}
                                        </div>
                                    </div>
                                {/if}
                            </div>
                        {/if}
                    {/if}
                </div>
            </div>
        {/if}

        {#if showDictationSplash}
            <div id="dictation-splash" transition:fade={{ duration: 300 }}>
                <h2 style="margin-bottom: 20px;">
                    {ui.dictation_completed_title || ui.quiz_completed}
                </h2>
                <div
                    style="font-size: 1.05rem; margin-bottom: 34px; opacity: 0.85; text-align: center;"
                >
                    {ui.dictation_completed_subtitle || ui.dictation_done}
                </div>
                <div style="display: flex; gap: 20px;">
                    <button
                        class="btn-contained"
                        style="background: white; color: black;"
                        onclick={closeDictationSplash}
                    >
                        {ui.dictation_finish_btn || ui.done_btn}
                    </button>
                    <button
                        class="btn-contained"
                        onclick={restartDictationExam}
                    >
                        {ui.dictation_repeat_btn || ui.retry_btn}
                    </button>
                </div>
            </div>
        {/if}

        {#if showSentenceTranslationSplash}
            <div
                id="sentence-translation-splash"
                transition:fade={{ duration: 300 }}
            >
                <h2 style="margin-bottom: 20px;">
                    {ui.sentence_translation_completed_title ||
                        ui.dictation_completed_title}
                </h2>
                <div
                    style="font-size: 1.05rem; margin-bottom: 34px; opacity: 0.85; text-align: center;"
                >
                    {ui.sentence_translation_completed_subtitle ||
                        ui.dictation_completed_subtitle}
                </div>
                <div style="display: flex; gap: 20px;">
                    <button
                        class="btn-contained"
                        style="background: white; color: black;"
                        onclick={closeSentenceTranslationSplash}
                    >
                        {ui.sentence_translation_finish_btn || ui.done_btn}
                    </button>
                    <button
                        class="btn-contained"
                        onclick={restartSentenceTranslationExam}
                    >
                        {ui.dictation_repeat_btn || ui.retry_btn}
                    </button>
                </div>
            </div>
        {/if}

        <!-- TABS -->
        <div class="tabs-container">
            <button
                class="tab-btn {activeTab === 'vocab' ? 'active' : ''}"
                onclick={() => switchTab("vocab")}>{ui.vocab_tab}</button
            >
            {#if quizData.length > 0}
                <button
                    class="tab-btn {activeTab === 'quiz' ? 'active' : ''}"
                    onclick={() => switchTab("quiz")}>{ui.quiz_tab}</button
                >
            {/if}
        </div>

        <!-- VOCAB TAB -->
        {#if activeTab === "vocab"}
            <div class="vocab-view">
                {#if vocab.length === 0}
                    <div class="card" style="text-align:center; opacity:0.6;">
                        {ui.empty_vocab_prompt}
                    </div>
                {/if}
                {#each vocab as v}
                    <div
                        class="vocab-item"
                        role="button"
                        tabindex="0"
                        onclick={() => {
                            if (!editingId) toggleVocabFav(v.id);
                        }}
                        onkeydown={(e) => {
                            if (e.key === "Enter" && !editingId)
                                toggleVocabFav(v.id);
                        }}
                    >
                        <div
                            style="display:flex; align-items:center; gap:12px; flex: 1; min-width: 0;"
                        >
                            <button
                                class="btn-text"
                                onclick={(e) => {
                                    e.stopPropagation();
                                    playVocabPair(
                                        v.display,
                                        $user.interface_language === "ukr"
                                            ? v.ua
                                            : v.en,
                                        v.id,
                                    );
                                }}
                            >
                                <span
                                    class="material-symbols-outlined"
                                    style="font-size:18px;"
                                    >{vocabPlayingId === v.id
                                        ? "pause"
                                        : "volume_up"}</span
                                >
                            </button>
                            <div
                                style="overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0;"
                            >
                                <span
                                    style="font-weight: 500; color: var(--primary); font-size: 1.1rem; cursor: pointer;"
                                    onclick={(e) => {
                                        e.stopPropagation();
                                        scrollToWord(v.id);
                                    }}
                                    role="button"
                                    tabindex="0"
                                    onkeydown={(e) =>
                                        e.key === "Enter" && scrollToWord(v.id)}
                                    >{v.display}</span
                                >
                                <div
                                    style="font-size:0.85rem; opacity:0.7; margin-top:6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
                                >
                                    {#if editingId === v.id && editingFieldType === ($user.interface_language === "ukr" ? "ua" : "en")}
                                        <input
                                            type="text"
                                            class="edit-input"
                                            bind:value={editValue}
                                            onclick={(e) => e.stopPropagation()}
                                            onkeydown={(e) => {
                                                e.stopPropagation();
                                                if (e.key === "Enter")
                                                    saveEdit(v.id);
                                            }}
                                        />
                                    {:else}
                                        {$user.interface_language === "ukr"
                                            ? v.ua
                                            : v.en}
                                    {/if}
                                </div>
                            </div>
                        </div>
                        <div
                            style="display: flex; align-items: center; gap: 0;"
                        >
                            <button
                                class="btn-text"
                                onclick={(e) => {
                                    e.stopPropagation();
                                    toggleVocabFav(v.id);
                                }}
                                style="color: {v.is_favorite
                                    ? '#FFC107'
                                    : 'inherit'}; min-width: 32px; padding: 0;"
                            >
                                <span
                                    class="material-symbols-outlined {v.is_favorite
                                        ? 'filled'
                                        : ''}">star</span
                                >
                            </button>
                            {#if editingId === v.id}
                                <button
                                    class="btn-text"
                                    style="color:var(--primary); padding:0; min-width:32px;"
                                    onclick={(e) => {
                                        e.stopPropagation();
                                        saveEdit(v.id);
                                    }}
                                >
                                    <span class="material-symbols-outlined"
                                        >check</span
                                    >
                                </button>
                                <button
                                    class="btn-text"
                                    style="padding:0; min-width:32px;"
                                    onclick={(e) => {
                                        e.stopPropagation();
                                        cancelEdit();
                                    }}
                                >
                                    <span class="material-symbols-outlined"
                                        >close</span
                                    >
                                </button>
                            {:else}
                                <button
                                    class="btn-text"
                                    style="color:var(--primary); opacity:0.7; padding:0; min-width:32px;"
                                    onclick={(e) => {
                                        e.stopPropagation();
                                        startEdit(
                                            v.id,
                                            $user.interface_language === "ukr"
                                                ? v.ua
                                                : v.en,
                                            $user.interface_language === "ukr"
                                                ? "ua"
                                                : "en",
                                        );
                                    }}
                                >
                                    <span class="material-symbols-outlined"
                                        >edit</span
                                    >
                                </button>
                                <button
                                    class="btn-text"
                                    onclick={(e) => {
                                        e.stopPropagation();
                                        removeWord(v.id);
                                    }}
                                    style="color:red; min-width: 32px; padding: 0;"
                                >
                                    <span class="material-symbols-outlined"
                                        >delete</span
                                    >
                                </button>
                            {/if}
                        </div>
                    </div>
                {/each}
            </div>
        {/if}

        <!-- QUIZ TAB -->
        {#if activeTab === "quiz"}
            <div class="quiz-container">
                <div
                    style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;"
                >
                    <div style="font-weight: 500; opacity: 0.7;">
                        {ui.quiz_tab}
                        {quizFinished ? quizData.length : currentQIndex + 1} / {quizData.length}
                    </div>
                </div>

                {#if quizFinished}
                    <div class="results-view">
                        <div class="score-circle">
                            <svg
                                viewBox="0 0 160 160"
                                style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
                            >
                                <circle
                                    class="score-circle-bg"
                                    cx="80"
                                    cy="80"
                                    r="69"
                                ></circle>
                                <circle
                                    class="score-circle-fg"
                                    cx="80"
                                    cy="80"
                                    r="69"
                                    style="stroke-dashoffset: {434 -
                                        ($animatedScore / 100) *
                                            434}; stroke: {$animatedScore >= 80
                                        ? '#4CAF50'
                                        : $animatedScore >= 50
                                          ? '#FFC107'
                                          : '#f44336'};"
                                ></circle>
                            </svg>
                            <span
                                style="font-size: 2.5rem; position: relative; z-index: 1;"
                                >{$animatedScore.toFixed(0)}%</span
                            >
                        </div>
                        <div
                            style="font-size: 1.1rem; margin-bottom: 30px; opacity: 0.8;"
                        >
                            {ui.your_score}
                        </div>
                        <button class="btn-contained" onclick={restartQuiz}
                            >{ui.retry_btn}</button
                        >
                    </div>
                {:else}
                    <div class="quiz-progress-track">
                        <div
                            class="quiz-progress-fill"
                            style="width: {(currentQIndex / quizData.length) *
                                100}%"
                        ></div>
                    </div>

                    <div class="quiz-question">
                        {@html quizData[currentQIndex].question}
                    </div>

                    <div class="quiz-options">
                        {#each quizData[currentQIndex].options as opt, idx}
                            <button
                                class="quiz-option
                                {selectedOptionIndex === idx ? 'selected' : ''} 
                                {isChecked &&
                                idx === quizData[currentQIndex].correct_index
                                    ? 'correct'
                                    : ''}
                                {isChecked &&
                                selectedOptionIndex === idx &&
                                idx !== quizData[currentQIndex].correct_index
                                    ? 'wrong'
                                    : ''}
                                {isChecked ? 'disabled' : ''}"
                                onclick={() => selectOption(idx)}
                            >
                                {opt}
                            </button>
                        {/each}
                    </div>

                    <!-- FOOTER ACTIONS -->
                    <div
                        style="margin-top: 24px; display: flex; justify-content: space-between; align-items: center;"
                    >
                        <div style="display: flex; gap: 10px;">
                            <button
                                class="btn-contained btn-danger"
                                onclick={abortQuiz}
                            >
                                {ui.abort_btn}
                            </button>
                            {#if isChecked}
                                <button
                                    class="btn-contained"
                                    onclick={restartQuiz}
                                    style="background-color: var(--secondary); color: black;"
                                    >{ui.restart_btn}</button
                                >
                            {/if}
                        </div>

                        {#if !isChecked}
                            <button
                                class="btn-contained"
                                disabled={selectedOptionIndex === null}
                                onclick={checkAnswer}
                                style="min-width: 100px;">{ui.check_btn}</button
                            >
                        {:else}
                            <button
                                class="btn-contained"
                                onclick={nextQuestion}
                                style="min-width: 100px;"
                                >{currentQIndex < quizData.length - 1
                                    ? ui.next_btn
                                    : ui.finish_btn}</button
                            >
                        {/if}
                    </div>
                {/if}
            </div>
        {/if}
    {/if}

    <!-- POPUPS -->
    {#if showPopup}
        <div
            id="pop"
            style={popupStyle}
            onmouseenter={onPopupMouseEnter}
            onmouseleave={onPopupMouseLeave}
        >
            <button
                type="button"
                class="pop-option"
                onclick={(e) => {
                    e.stopPropagation();
                    quickTranslate();
                }}
                disabled={isTranslating}
            >
                {#if isTranslating}
                    <span class="loader-spinner"></span>
                {:else}
                    {ui.add_translation}
                {/if}
            </button>
            {#if isSingleWordSelected}
                <span class="pop-separator">|</span>
                <button
                    type="button"
                    class="pop-option"
                    onclick={(e) => {
                        e.stopPropagation();
                        onExplainClick();
                    }}
                    disabled={isTranslating}
                >
                    {ui.explain_selection}
                </button>
            {/if}
        </div>
    {/if}

    {#if showLearnedPopup}
        <div
            id="learned-pop"
            class:sticky={learnedPopupSticky}
            style={learnedPopupStyle}
            onmouseenter={onLearnedPopupMouseEnter}
            onmouseleave={onLearnedPopupMouseLeave}
        >
            {#if learnedPopupSticky}
                <button
                    type="button"
                    class="popup-close"
                    onclick={(e) => {
                        e.stopPropagation();
                        closeLearnedPopup();
                    }}
                >
                    ×
                </button>
            {/if}
            <div class="learned-popup-content">
                {@html learnedPopupContent}
            </div>
        </div>
    {/if}

    <!-- QUIZ SPLASH SCREEN -->
    {#if showQuizSplash}
        <div id="quiz-splash" transition:fade={{ duration: 300 }}>
            <h2 style="margin-bottom: 30px;">{ui.quiz_completed}</h2>
            <div
                class="score-circle"
                style="width: 160px; height: 160px; margin-bottom: 20px;"
            >
                <svg viewBox="0 0 160 160">
                    <circle class="score-circle-bg" cx="80" cy="80" r="69"
                    ></circle>
                    <circle
                        class="score-circle-fg"
                        cx="80"
                        cy="80"
                        r="69"
                        style="stroke-dashoffset: {434 -
                            ($animatedScore / 100) *
                                434}; stroke: {$animatedScore >= 80
                            ? '#4CAF50'
                            : $animatedScore >= 50
                              ? '#FFC107'
                              : '#f44336'};"
                    ></circle>
                </svg>
                <span id="splash-score">{$animatedScore.toFixed(0)}%</span>
            </div>
            <div style="font-size: 1.2rem; margin-bottom: 40px; opacity: 0.8;">
                {ui.your_score}
            </div>
            <div style="display: flex; gap: 20px;">
                <button
                    class="btn-contained"
                    style="background: white; color: black;"
                    onclick={closeSplash}>{ui.done_btn}</button
                >
                <button class="btn-contained" onclick={restartQuiz}
                    >{ui.retry_btn}</button
                >
            </div>
        </div>
    {/if}
</div>

<style>
    .view-container {
        max-width: 1180px;
        margin: 0 auto;
        padding-bottom: 100px;
        position: relative;
    }

    .view-container .card {
        padding: 40px;
    }

    .toolbar {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 24px;
        flex-wrap: wrap;
    }

    .text-body {
        text-align: justify;
        line-height: 2.4;
        margin-bottom: 16px;
    }
    .de-line {
        display: inline;
        transition: background-color 0.3s;
    }
    .de-line::after {
        content: " ";
    }
    .sent-num-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: #e91e8c;
        color: white;
        font-size: 0.65rem;
        font-weight: 700;
        border-radius: 4px;
        margin-right: 5px;
        vertical-align: 3px;
        font-family: var(--font-interface);
        line-height: 1;
        width: 22px;
        height: 16px;
        cursor: pointer;
        transition: background-color 0.15s;
        flex-shrink: 0;
        user-select: none;
    }
    .sent-num-btn:hover {
        background: #e91e8c;
        vertical-align: 0px;
    }
    .sent-num-label {
        display: inline;
    }
    .sent-num-icon {
        display: none;
        font-size: 13px;
        line-height: 1;
    }
    .sent-num-btn:hover .sent-num-label,
    .sent-num-btn.playing .sent-num-label {
        display: none;
    }
    .sent-num-btn:hover .sent-num-icon,
    .sent-num-btn.playing .sent-num-icon {
        display: flex;
        align-items: center;
        height: 100%;
        vertical-align: 0px;
    }
    .de-text {
        display: inline;
        font-size: 1.1rem;
        font-weight: 400;
        font-family: var(--font-text);
    }
    .highlight-sentence {
        background-color: rgba(255, 235, 59, 0.3);
        border-radius: 4px;
    }

    .trans-row {
        display: inline;
        color: var(--primary);
        font-size: 1.1rem;
        margin-left: 6px;
    }

    .sentence-translation-popup {
        display: inline;
        color: var(--primary);
        font-size: 1.1rem;
        margin-left: 6px;
        animation: fadeInOut 5s ease-in-out;
    }

    @keyframes fadeInOut {
        0%,
        100% {
            opacity: 0;
        }
        10%,
        90% {
            opacity: 1;
        }
    }

    .grammar-box {
        background-color: rgba(25, 118, 210, 0.08);
        color: var(--on-surface);
        padding: 12px 16px;
        border-radius: var(--radius);
        margin-top: 10px;
        font-size: 0.95rem;
        line-height: 1.6;
        border-left: 4px solid var(--primary);
    }

    .badge-btn {
        padding: 4px 12px;
        border-radius: 4px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 28px;
        height: 30px;
        border: none;
        background: transparent;
        color: var(--on-surface);
        cursor: pointer;
        transition: all 0.2s;
    }
    .badge-btn:hover {
        opacity: 0.7;
    }

    .dictation-launch-btn {
        width: 36px;
        height: 36px;
        min-width: 36px;
        border: 1px solid var(--border);
        border-radius: 8px;
        position: relative;
    }

    .dictation-done-badge {
        position: absolute;
        right: -7px;
        top: -7px;
        width: 18px;
        height: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #2e7d32;
        background: var(--bg);
        border-radius: 50%;
    }

    .dictation-done-badge .material-symbols-outlined {
        font-size: 18px;
    }

    .dictation-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: var(--bg);
        z-index: 2000;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
        scrollbar-gutter: stable;
        overflow-x: hidden;
    }

    .dictation-overlay :global(*) {
        outline: none !important;
    }

    .dictation-close-btn {
        position: absolute;
        top: 24px;
        right: 24px;
        z-index: 2005;
        background: none;
        border: none;
        color: var(--on-surface);
        cursor: pointer;
        padding: 8px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 2px;
    }

    .dictation-close-btn .material-symbols-outlined {
        font-size: 30px;
    }

    .dictation-close-hint {
        font-size: 0.75rem;
        font-weight: 600;
        opacity: 0.85;
    }

    .dictation-container {
        width: 100%;
        max-width: 600px;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        gap: 26px;
        background: transparent;
        padding: 66px 20px 34px;
        box-sizing: border-box;
        overflow-y: auto;
        overflow-x: hidden;
    }

    .dictation-resume-actions {
        display: flex;
        justify-content: center;
        gap: 50px;
        margin: auto 0;
    }

    .dictation-resume-actions .btn-contained {
        width: 100%;
        min-width: 240px;
    }

    .fc-progress-wrapper {
        padding: 0 24px;
        margin-bottom: 0;
        text-align: center;
    }

    .fc-progress-track {
        height: 12px;
        background: rgba(0, 0, 0, 0.1);
        border-radius: 6px;
        overflow: hidden;
        margin-bottom: 4px;
    }

    .fc-progress-fill {
        height: 100%;
        background: var(--primary);
        width: 0%;
        transition: width 0.3s;
    }

    .fc-progress-text {
        font-size: 0.8rem;
        opacity: 0.6;
    }

    .dictation-main-actions {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        margin-bottom: 0;
    }

    .dictation-play-btn {
        width: 120px;
        height: 120px;
        border-radius: 50%;
        background: var(--primary);
        color: white;
        border: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 8px 20px rgba(25, 118, 210, 0.4);
        transition: transform 0.2s;
    }

    .dictation-play-btn:active {
        transform: scale(0.95);
    }

    .dictation-play-btn .material-symbols-outlined {
        font-size: 64px;
    }

    .dictation-play-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
        transform: none;
    }

    .dictation-play-caption {
        margin-top: 14px;
        margin-bottom: 14px;
        opacity: 0.8;
        font-weight: 500;
        font-size: 1.2rem;
    }

    .dictation-play-hotkey {
        margin-top: 4px;
        opacity: 0.65;
        font-weight: 500;
        font-size: 0.85rem;
    }

    .dictation-input {
        width: 100%;
        min-height: 200px;
        resize: vertical;
        border: 2px solid var(--border);
        border-radius: 16px;
        padding: 18px 20px;
        box-sizing: border-box;
        font-size: 1.4rem;
        line-height: 1.5;
        font-family: var(--font-text);
        color: var(--on-surface);
        background: rgba(0, 0, 0, 0.02);
        margin-bottom: 0;
    }

    .dictation-input:focus {
        outline: none;
        border-color: var(--primary);
        background: rgba(25, 118, 210, 0.04);
    }

    .translation-source-card {
        border: 2px solid var(--border);
        border-radius: 16px;
        padding: 16px 18px;
        background: rgba(25, 118, 210, 0.04);
    }

    .translation-source-label {
        font-size: 0.85rem;
        opacity: 0.7;
        font-weight: 600;
        margin-bottom: 8px;
    }

    .translation-source-text {
        font-size: 1.15rem;
        line-height: 1.45;
        font-family: var(--font-text);
    }

    .sentence-translation-correct {
        color: #2e7d32;
        font-weight: 600;
    }

    .dictation-actions {
        display: flex;
        gap: 10px;
        margin-bottom: 0;
        justify-content: space-between;
    }

    .dictation-actions .btn-contained {
        min-width: 130px;
    }

    .dictation-next-btn:disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }

    .dictation-repeat-warning {
        color: #b26a00;
        font-size: 0.95rem;
        font-weight: 600;
        margin-bottom: 2px;
    }

    .dictation-result-card {
        border: none;
        border-radius: 0;
        padding: 0;
        background: transparent;
        display: grid;
        gap: 12px;
    }

    .dictation-score {
        font-size: 1.1rem;
    }

    .dictation-diff-label {
        font-size: 0.9rem;
        opacity: 0.65;
        margin-bottom: 4px;
        font-weight: 600;
    }

    .dictation-diff-line {
        white-space: pre-wrap;
        line-height: 1.6;
        font-size: 1.08rem;
        border-radius: 0;
        padding: 0;
        background: transparent;
    }

    .diff-chip.equal {
        background: transparent;
    }

    .diff-chip.replace {
        background: rgba(255, 152, 0, 0.22);
        border-radius: 4px;
    }

    .diff-chip.delete {
        background: rgba(244, 67, 54, 0.2);
        border-radius: 4px;
    }

    .diff-chip.insert {
        background: rgba(33, 150, 243, 0.2);
        border-radius: 4px;
    }

    .diff-chip.diff-missing {
        background: rgba(244, 67, 54, 0.2);
        border-radius: 4px;
        font-style: italic;
        padding: 0 4px;
    }

    @media (max-width: 768px) {
        .dictation-container {
            padding: 72px 20px 24px;
            gap: 16px;
            max-width: 100%;
            height: 100%;
        }

        .dictation-play-btn {
            width: 108px;
            height: 108px;
        }

        .dictation-play-btn .material-symbols-outlined {
            font-size: 54px;
        }

        .dictation-play-caption {
            margin-top: 10px;
            font-size: 1rem;
        }

        .dictation-play-hotkey {
            font-size: 0.8rem;
        }

        .dictation-input {
            min-height: 140px;
            font-size: 1.1rem;
        }

        .dictation-actions {
            flex-direction: column;
        }

        .dictation-actions .btn-contained {
            width: 100%;
        }

        .dictation-close-btn {
            right: 12px;
            top: 12px;
        }
    }

    .report-btn {
        padding: 4px 12px;
        border-radius: 4px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 28px;
        height: 30px;
        border: none;
        background: transparent;
        color: #d32f2f;
        cursor: pointer;
        transition: opacity 0.2s;
        opacity: 0.5;
    }
    .report-btn:hover {
        opacity: 1;
    }

    /* Tabs */
    .tabs-container {
        display: flex;
        width: 100%;
        margin-top: 30px;
    }
    .tab-btn {
        flex: 1;
        padding: 12px;
        background: rgba(0, 0, 0, 0.05);
        border: 1px solid var(--border);
        cursor: pointer;
        font-weight: 500;
        text-transform: uppercase;
        font-size: 0.9rem;
        color: var(--on-surface);
        opacity: 0.6;
    }
    .tab-btn.active {
        background: var(--primary);
        color: var(--on-primary);
        opacity: 1;
        border-color: var(--primary);
    }
    .tab-btn:first-child {
        border-radius: var(--radius) 0 0 var(--radius);
    }
    .tab-btn:last-child {
        border-radius: 0 var(--radius) var(--radius) 0;
    }

    /* Vocab */
    .vocab-view {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-top: 20px;
    }
    .vocab-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        background: var(--surface);
        box-shadow: var(--shadow);
        font-family: var(--font-text);
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
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 24px;
        margin-top: 20px;
        box-shadow: var(--shadow);
    }
    .quiz-progress-track {
        width: 100%;
        height: 6px;
        background: rgba(0, 0, 0, 0.1);
        border-radius: 3px;
        margin-bottom: 20px;
        overflow: hidden;
    }
    .quiz-progress-fill {
        height: 100%;
        background: var(--primary);
        transition: width 0.3s ease;
    }
    .quiz-question {
        font-size: 1.2rem;
        font-weight: 500;
        margin-bottom: 20px;
        line-height: 1.4;
    }
    .quiz-options {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    .quiz-option {
        padding: 12px 16px;
        border: 2px solid var(--border);
        border-radius: 8px;
        cursor: pointer;
        font-size: 1rem;
        background: transparent;
        color: var(--on-surface);
        text-align: left;
        transition: all 0.2s;
        text-transform: none;
        justify-content: flex-start;
        height: auto;
        line-height: 1.4;
        font-weight: normal;
    }
    /* Скидаємо стилі кнопки для quiz-option, щоб вона виглядала як div */
    .quiz-option:hover:not(.disabled) {
        background: rgba(0, 0, 0, 0.02);
        border-color: var(--primary);
    }
    .quiz-option.selected {
        border-color: var(--primary);
        background: rgba(25, 118, 210, 0.05);
    }
    .quiz-option.correct {
        border-color: #4caf50 !important;
        background: rgba(76, 175, 80, 0.1) !important;
        color: #2e7d32;
    }
    .quiz-option.wrong {
        border-color: #f44336 !important;
        background: rgba(244, 67, 54, 0.1) !important;
        color: #c62828;
    }
    .quiz-option.disabled {
        pointer-events: none;
    }

    .results-view {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 20px 0;
        animation: fadeIn 0.3s ease;
    }
    .score-circle {
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
        width: 160px;
        height: 160px;
        margin-bottom: 20px;
    }
    .score-circle svg {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        transform: rotate(-90deg);
    }
    .score-circle circle {
        fill: none;
        stroke-width: 22;
        stroke-linecap: round;
    }
    .score-circle-bg {
        stroke: #333;
        opacity: 0.1;
    }
    .score-circle-fg {
        stroke-dasharray: 434; /* 2 * PI * 69 */
        transition: stroke-dashoffset 1.5s ease-out;
    }

    /* Splash Screen */
    #quiz-splash {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.85);
        backdrop-filter: blur(8px);
        z-index: 10000;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        color: white;
    }
    #dictation-splash,
    #sentence-translation-splash {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.85);
        backdrop-filter: blur(8px);
        z-index: 10000;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        color: white;
    }
    #splash-score {
        font-size: 2.5rem;
        font-weight: 700;
        position: absolute;
        color: white;
    }

    /* Confetti */
    :global(.confetti) {
        position: fixed;
        width: 10px;
        height: 10px;
        z-index: 10001;
        pointer-events: none;
        top: -20px;
    }

    /* Popups */
    #pop {
        position: absolute;
        background: var(--on-surface);
        color: var(--bg);
        padding: 8px 16px;
        border-radius: 4px;
        z-index: 2000;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border: none;
        font-family: inherit;
        height: auto;
        text-transform: none;
        font-weight: 500;
        font-size: 0.8rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }
    .pop-option {
        background: transparent;
        color: inherit;
        border: none;
        padding: 0;
        height: auto;
        min-width: 0;
        font: inherit;
        text-transform: none;
        cursor: pointer;
    }
    .pop-option:disabled {
        cursor: not-allowed;
        opacity: 0.7;
    }
    .pop-separator {
        opacity: 0.7;
        user-select: none;
    }
    #learned-pop {
        position: absolute;
        background: var(--on-surface);
        color: var(--bg);
        padding: 8px 12px;
        border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        z-index: 2100;
        border: none;
        min-width: 0;
        width: fit-content;
        max-width: min(320px, 92vw);
        max-height: 82vh;
        overflow-y: auto;
        font-family: var(--font-text);
        line-height: 1.45;
        position: relative;
        word-break: break-word;
    }
    .learned-popup-content {
        padding-right: 0;
    }
    #learned-pop.sticky {
        background: var(--surface);
        color: var(--on-surface);
        min-width: min(576px, 94vw);
        width: min(576px, 94vw);
        max-width: 94vw;
        max-height: 88vh;
        padding: 18px 18px 16px 18px;
        border: 1px solid var(--border);
    }
    #learned-pop.sticky .learned-popup-content {
        padding-right: 10px;
        margin-top: 10px;
    }
    .popup-close {
        position: absolute;
        top: 6px;
        right: 6px;
        border: none;
        background: transparent;
        color: var(--on-surface);
        font-size: 1rem;
        cursor: pointer;
        width: 24px;
        height: 24px;
        padding: 0;
        line-height: 1;
        min-width: 24px;
    }
    #learned-pop.sticky .popup-close {
        top: 10px;
        right: 10px;
        width: 30px;
        height: 30px;
        min-width: 30px;
        font-size: 1.3rem;
        border-radius: 6px;
        background: rgba(0, 0, 0, 0.06);
    }

    :global(.explain-popup) {
        border-radius: 10px;
        padding: 12px;
    }
    :global(.explain-popup > div:first-child) {
        font-size: 1.15rem;
        line-height: 1.2;
    }
    :global(.explain-section) {
        margin-top: 10px;
        padding: 9px 10px;
        border-radius: 8px;
        border: 1px solid transparent;
    }
    :global(.explain-section-title) {
        font-weight: 700;
        margin-bottom: 6px;
        font-family: var(--font-interface);
        font-size: 0.78rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    :global(.explain-nouns) {
        background: rgba(30, 136, 229, 0.08);
        border-color: rgba(30, 136, 229, 0.28);
    }
    :global(.explain-nouns .explain-section-title) {
        color: #1565c0;
    }
    :global(.explain-verbs) {
        background: rgba(67, 160, 71, 0.1);
        border-color: rgba(67, 160, 71, 0.3);
    }
    :global(.explain-verbs .explain-section-title) {
        color: #2e7d32;
    }
    :global(.explain-adj-adv) {
        background: rgba(123, 31, 162, 0.09);
        border-color: rgba(123, 31, 162, 0.26);
    }
    :global(.explain-adj-adv .explain-section-title) {
        color: #6a1b9a;
    }
    :global(.explain-synonyms) {
        background: rgba(251, 140, 0, 0.12);
        border-color: rgba(251, 140, 0, 0.28);
    }
    :global(.explain-synonyms .explain-section-title) {
        color: #ef6c00;
    }
    :global(.explain-antonyms) {
        background: rgba(229, 57, 53, 0.11);
        border-color: rgba(229, 57, 53, 0.28);
    }
    :global(.explain-antonyms .explain-section-title) {
        color: #c62828;
    }
    :global(.explain-list) {
        margin: 0;
        padding-left: 16px;
        display: grid;
        gap: 5px;
    }
    :global(.explain-item) {
        line-height: 1.35;
    }
    :global(.explain-lemma) {
        color: #212121;
        font-weight: 700;
    }
    :global(.explain-sep) {
        margin: 0 6px;
        opacity: 0.6;
    }
    :global(.explain-translation) {
        color: #455a64;
        font-style: italic;
    }

    /* Global styles for dynamic content */
    :global(.learned) {
        background-color: rgba(25, 118, 210, 0.15);
        border-bottom: 2px solid var(--primary);
        cursor: pointer;
        border-radius: 3px;
        padding: 0 1px;
    }
    :global(body.dark-mode .learned) {
        background-color: rgba(144, 202, 249, 0.2);
        border-bottom-color: #90caf9;
    }
    :global(.explained-word) {
        background-color: rgba(255, 214, 10, 0.32);
        border-bottom: 2px solid #f4b400;
        cursor: pointer;
        border-radius: 3px;
        padding: 0 1px;
    }
    :global(body.dark-mode .explained-word) {
        background-color: rgba(255, 214, 10, 0.42);
        border-bottom-color: #ffd54f;
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
        to {
            transform: rotate(360deg);
        }
    }

    #pop {
        transition: opacity 0.3s ease-out;
    }

    #pop:disabled {
        cursor: not-allowed;
        pointer-events: none;
    }
</style>
