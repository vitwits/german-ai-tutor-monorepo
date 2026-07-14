<script>
    /* eslint-disable */
    import { onMount, onDestroy } from "svelte";
    import api from "../lib/api";
    import { user } from "../stores/auth";
    import { addToast } from "../stores/toast";
    import { getUI } from "../lib/ui";
    import { router } from "tinro";
    import { confirmModal } from "../stores/confirm";

    // Data State
    let items = $state([]);
    let loading = $state(false);
    let total = $state(0);
    let page = $state(1);
    let totalPages = $state(1);

    // Filter State
    let activeTab = $state("words"); // 'words' only
    let viewMode = $state("list"); // 'list' | 'grid'
    let selectedLevels = $state([]);
    let searchQuery = $state("");
    const allLevels = ["A1", "A2", "B1", "B2", "C1", "C2"];
    let expandedContexts = $state({}); // Change from Set to object
    let searchFocused = $state(false);

    let searchTimeout;

    // Flashcard Session State
    let showSession = $state(false);
    let sessionCards = $state([]);
    let originalSessionCards = $state([]);
    let currentCardIdx = $state(0);
    let isFlipped = $state(false);
    let fcMode = $state("study"); // 'study' | 'review'
    let fcIsPlaying = $state(false);
    let fcReviewStarted = $state(false);
    let fcStats = $state({ easy: 0, medium: 0, hard: 0 });
    let fcLoopTimeout = null;
    let currentAudio = null;
    let fcIsRandom = $state(false);
    let fcAudioEnabled = $state(true);
    let fcStudyLoop = $state(false); // Цикличное воспроизведение в режиме Study
    let fcReverseMode = $state(false); // Показывать перевод сначала, потом немецкий
    let fcUseContextMode = $state(false); // Показувати речення замість слів

    // Session Completion Splash Screen
    let showSessionSplash = $state(false);
    let sessionScore = $state(0);

    // Add Custom Word State
    let showAddWordDialog = $state(false);
    let customWordInput = $state("");
    let addingWord = $state(false);
    let customWordInputRef = $state(null); // Посилання на input елемент

    let hasCtxTrans = $derived(originalSessionCards.some((c) => c.ctx_trans));

    // Player State (Removed - sentences no longer supported)

    // Editing State
    let editingId = $state(null);
    let editValue = $state("");

    // Обчислення "розумного" діапазону сторінок для пагінації
    let paginationRange = $derived.by(() => {
        const delta = 1; // Кількість сторінок до/після поточної
        const range = [];
        for (let i = 1; i <= totalPages; i++) {
            if (
                i === 1 ||
                i === totalPages ||
                (i >= page - delta && i <= page + delta)
            ) {
                range.push(i);
            }
        }
        const withDots = [];
        let l;
        for (let i of range) {
            if (l) {
                if (i - l === 2) withDots.push(l + 1);
                else if (i - l !== 1) withDots.push("...");
            }
            withDots.push(i);
            l = i;
        }
        return withDots;
    });

    let ui = $derived(getUI($user?.interface_language || "ukr"));

    async function loadData() {
        loading = true;
        try {
            const params = {
                page,
                mode: activeTab,
                per_page: 30, // Оновлено до 30 елементів
                levels: selectedLevels.join(","),
                q: searchQuery,
            };
            const res = await api.get("/vocab", { params });
            items = res.data.items;
            total = res.data.total;
            totalPages = res.data.pages;
        } catch (e) {
            console.error(e);
        } finally {
            loading = false;
        }
    }

    function onSearchChange() {
        clearTimeout(searchTimeout);
        page = 1;
        searchTimeout = setTimeout(loadData, 300);
    }

    function clearSearch() {
        searchQuery = "";
        page = 1;
        loadData();
    }

    function switchTab(tab) {
        activeTab = tab;
        page = 1;
        searchQuery = "";
        items = [];
        expandedContexts = {}; // Закриваємо всі контексти при переключенні вкладки
        loadData();
    }

    function toggleLevel(lvl) {
        if (selectedLevels.includes(lvl)) {
            selectedLevels = selectedLevels.filter((l) => l !== lvl);
        } else {
            selectedLevels = [...selectedLevels, lvl];
        }
        page = 1;
        loadData();
    }

    function changePage(newPage) {
        if (newPage >= 1 && newPage <= totalPages) {
            page = newPage;
            loadData();
        }
    }

    // --- FLASHCARD LOGIC ---

    function shuffleArray(arr) {
        const shuffled = [...arr];
        for (let i = shuffled.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
        }
        return shuffled;
    }

    async function startSession() {
        if (document.activeElement instanceof HTMLElement)
            document.activeElement.blur();
        loading = true;
        try {
            const limit =
                fcMode === "study"
                    ? $user?.study_batch_size || 50 // Study: використовуємо study_batch_size
                    : $user?.vocab_session_size || 20; // Review: використовуємо vocab_session_size
            const levels = selectedLevels.join(",");

            // Передаємо mode параметр - Study або Review
            const res = await api.get(
                `/vocab/session?mode=${fcMode}&limit=${limit}&levels=${levels}`,
            );
            sessionCards = shuffleArray(res.data);
            originalSessionCards = [...sessionCards];

            if (sessionCards.length > 0) {
                showSession = true;
                currentCardIdx = 0;
                isFlipped = false;
                fcStats = { easy: 0, medium: 0, hard: 0 };
                fcIsPlaying = false;
                fcStudyLoop = false; // Цикл отключен по умолчанию
                fcReviewStarted = fcMode === "review" ? false : true; // Study auto-plays, Review needs manual start
                fcIsRandom = true; // Завжди рандомний порядок
                fcUseContextMode = false; // По замовчуванню - слова
            } else {
                addToast("No words found for session", "info");
            }
        } catch (e) {
            console.error(e);
        } finally {
            loading = false;
        }
    }

    async function fcClose() {
        // Для Study режиму: записуємо всі переглянуті слова в БД
        if (fcMode === "study" && sessionCards.length > 0) {
            try {
                const wordIds = sessionCards.map((card) => card.id);
                await api.post("/vocab/record_study_views", wordIds);
            } catch (e) {
                console.error("Failed to record study views:", e);
            }
        }

        showSession = false;
        fcIsPlaying = false;
        fcStudyLoop = false;
        if (fcLoopTimeout) clearTimeout(fcLoopTimeout);
        if (currentAudio) currentAudio.pause();
    }

    function fcSetMode(mode) {
        fcMode = mode;
        // Reset logic when switching modes if needed
        if (mode === "review") {
            fcIsPlaying = false;
            if (fcLoopTimeout) clearTimeout(fcLoopTimeout);
        }
    }

    function closeSplash() {
        showSessionSplash = false;
        loadData();
    }

    function continueSplash() {
        showSessionSplash = false;
        // Перезагружаємо сесію з тією ж конфігурацією
        startSession();
    }

    function openAddWordDialog() {
        showAddWordDialog = true;
        customWordInput = "";
        // Фокусуємо input після того як попап відкривається
        setTimeout(() => {
            if (customWordInputRef) customWordInputRef.focus();
        }, 0);
    }

    function closeAddWordDialog() {
        showAddWordDialog = false;
        customWordInput = "";
    }

    async function addCustomWord() {
        if (!customWordInput.trim()) {
            addToast(ui.add_custom_word_empty, "error");
            return;
        }

        const words = customWordInput.trim().split(/\s+/);
        if (words.length > 4) {
            addToast(ui.add_custom_word_max_words, "error");
            return;
        }

        addingWord = true;
        try {
            const response = await api.post("/vocab/add_custom", {
                text: customWordInput.trim(),
            });

            if (response.data && response.data.success === false) {
                addToast(
                    response.data.error || ui.add_custom_word_invalid,
                    "error",
                );
                return;
            }

            addToast(ui.add_custom_word_success, "success");
            closeAddWordDialog();
            loadData();
        } catch (error) {
            console.error("Error adding custom word:", error);
            addToast(
                error.response?.data?.error || ui.add_custom_word_error,
                "error",
            );
        } finally {
            addingWord = false;
        }
    }

    function launchConfetti() {
        const colors = ["#FFC107", "#2196F3", "#4CAF50", "#F44336", "#9C27B0"];
        const container = document.getElementById("vocab-splash");
        if (!container) return;

        for (let i = 0; i < 50; i++) {
            const el = document.createElement("div");
            el.classList.add("vocab-confetti");
            el.style.left = Math.random() * 100 + "%";
            el.style.backgroundColor =
                colors[Math.floor(Math.random() * colors.length)];
            el.style.animation = `fall ${Math.random() * 3 + 2}s linear forwards`;
            container.appendChild(el);
        }
    }

    // Study Loop (Auto-play)
    async function runStudyLoop() {
        if (!fcIsPlaying || !showSession || fcMode !== "study") return;

        const card = sessionCards[currentCardIdx];
        isFlipped = false;

        // Helper logic for German audio
        const playGerman = async () => {
            let deUrl = card.audio_de_url;
            if (!deUrl) {
                try {
                    const res = await api.post("/vocab/generate_audio", {
                        text: card.display,
                        lang: "de",
                    });
                    deUrl = res.data.url;
                } catch (e) {
                    console.error(e);
                }
            }
            if (deUrl) await playAudioPromise(deUrl);
        };

        // Helper logic for Translation audio
        const playTranslation = async () => {
            const transLang = $user?.interface_language === "ukr" ? "uk" : "en";
            let transUrls = card.audio_trans_urls;
            if (!transUrls || transUrls.length === 0) {
                try {
                    const transParts = card.trans
                        .split(",")
                        .map((p) => p.trim())
                        .filter((p) => p);
                    transUrls = [];
                    for (const part of transParts) {
                        const res = await api.post("/vocab/generate_audio", {
                            text: part,
                            lang: transLang,
                        });
                        if (res.data.url) transUrls.push(res.data.url);
                    }
                } catch (e) {
                    console.error(e);
                }
            }
            if (transUrls && transUrls.length > 0) {
                for (const url of transUrls) {
                    if (!fcIsPlaying) break;
                    await playAudioPromise(url);
                }
            }
        };

        // 1. Play Front Audio (based on direction)
        if (fcAudioEnabled && !fcUseContextMode) {
            if (fcReverseMode) await playTranslation();
            else await playGerman();
        } else {
            await new Promise((r) =>
                setTimeout(r, fcUseContextMode ? 3000 : 1000),
            );
        }

        if (!fcIsPlaying) return;

        // 2. Wait
        await new Promise((r) => (fcLoopTimeout = setTimeout(r, 1500)));
        if (!fcIsPlaying) return;

        // 3. Flip
        isFlipped = true;

        // 4. Play Back Audio (based on direction)
        if (fcAudioEnabled && !fcUseContextMode) {
            if (fcReverseMode) await playGerman();
            else await playTranslation();
        } else {
            await new Promise((r) =>
                setTimeout(r, fcUseContextMode ? 3000 : 1000),
            );
        }

        if (!fcIsPlaying) return;

        // 5. Wait
        await new Promise((r) => (fcLoopTimeout = setTimeout(r, 2500)));
        if (!fcIsPlaying) return;

        // 6. Next
        const nextIdx = currentCardIdx + 1;

        // Если достигли конца списка
        if (nextIdx >= sessionCards.length) {
            if (fcStudyLoop) {
                // Цикл включен - продолжаем с начала
                currentCardIdx = 0;
                runStudyLoop();
            } else {
                // Цикл отключен - закрыть сессию и показать сплеш
                await fcClose();
                sessionScore = 100; // 100% для Study (все слова просмотрены)
                showSessionSplash = true;
            }
        } else {
            currentCardIdx = nextIdx;
            runStudyLoop();
        }
    }

    function toggleFcPlay() {
        if (fcMode !== "study") return; // Тільки для Study режиму
        fcIsPlaying = !fcIsPlaying;
        if (fcIsPlaying) runStudyLoop();
        else {
            if (fcLoopTimeout) clearTimeout(fcLoopTimeout);
            if (currentAudio) currentAudio.pause();
        }
    }

    function startReview() {
        // Тільки для Review режиму - починаємо з першого слова
        if (fcMode === "review") {
            fcReviewStarted = true;
            currentCardIdx = 0;
            const card = sessionCards[currentCardIdx];
            if (fcAudioEnabled && !fcUseContextMode) {
                if (fcReverseMode) {
                    // Play translation sequentially
                    const transLang =
                        $user?.interface_language === "ukr" ? "uk" : "en";
                    (async () => {
                        const transParts = card.trans
                            .split(",")
                            .map((p) => p.trim())
                            .filter((p) => p);
                        for (const part of transParts) {
                            try {
                                const res = await api.post(
                                    "/vocab/generate_audio",
                                    { text: part, lang: transLang },
                                );
                                if (res.data.url)
                                    await playAudioPromise(res.data.url);
                            } catch (e) {
                                console.error(e);
                            }
                        }
                    })();
                } else {
                    playAudio(card.audio_de_url);
                }
            }
        }
    }

    async function flipCard() {
        // Study режим: не дозволяємо flip (це auto-play)
        if (fcMode === "study") return;

        // Review режим: flip карточки
        if (!fcReviewStarted) return;
        isFlipped = !isFlipped;
        if (isFlipped) {
            const card = sessionCards[currentCardIdx];
            if (fcAudioEnabled && !fcUseContextMode) {
                if (fcReverseMode) {
                    // Back side is German in reverse mode
                    playAudio(card.audio_de_url);
                } else {
                    // Back side is Translation in normal mode
                    if (card.audio_trans_urls?.length) {
                        for (const url of card.audio_trans_urls)
                            await playAudioPromise(url);
                    } else {
                        const transLang =
                            $user?.interface_language === "ukr" ? "uk" : "en";
                        const transParts = card.trans
                            .split(",")
                            .map((p) => p.trim())
                            .filter((p) => p);
                        for (const part of transParts) {
                            const res = await api.post(
                                "/vocab/generate_audio",
                                { text: part, lang: transLang },
                            );
                            if (res.data.url)
                                await playAudioPromise(res.data.url);
                        }
                    }
                }
            }
        }
    }

    function nextCard() {
        if (fcLoopTimeout) clearTimeout(fcLoopTimeout);
        if (currentAudio) currentAudio.pause();

        // В Study режиме: не циклируем при ручном переключении, если цикл отключен
        if (fcMode === "study") {
            const nextIdx = currentCardIdx + 1;
            if (nextIdx >= sessionCards.length) {
                fcIsPlaying = false;
                fcClose();
                sessionScore = 100;
                showSessionSplash = true;
                return;
            }
            currentCardIdx = nextIdx;
        } else {
            // Review режим: циклируем как обычно
            currentCardIdx = (currentCardIdx + 1) % sessionCards.length;
        }

        isFlipped = false;

        // Якщо було включено в Study - продовжуємо цикл з наступним словом
        if (fcMode === "study" && fcIsPlaying) {
            runStudyLoop();
        } else {
            fcIsPlaying = false;
        }

        // Перевіримо, чи ми в Study режимі і досягли кінця списку
        if (
            fcMode === "study" &&
            currentCardIdx >= sessionCards.length - 1 &&
            !fcStudyLoop
        ) {
            fcIsPlaying = false;
            fcClose();
            sessionScore = 100;
            showSessionSplash = true;
        }
    }

    function toggleFcAudio() {
        fcAudioEnabled = !fcAudioEnabled;
    }

    function toggleFcContextMode() {
        if (!hasCtxTrans) {
            addToast(
                ui.fc_no_ctx_trans || "No context translations available",
                "info",
            );
            return;
        }

        fcUseContextMode = !fcUseContextMode;
        isFlipped = false;

        // Зупиняємо програвання при зміні режиму
        if (fcLoopTimeout) clearTimeout(fcLoopTimeout);
        if (currentAudio) currentAudio.pause();
        fcIsPlaying = false;

        if (fcUseContextMode) {
            sessionCards = originalSessionCards.filter((c) => c.ctx_trans);
        } else {
            sessionCards = [...originalSessionCards];
        }

        if (currentCardIdx >= sessionCards.length) currentCardIdx = 0;
    }

    function toggleFcReverseMode() {
        fcReverseMode = !fcReverseMode;
        isFlipped = false; // Сбросить флип при переключении режима
    }

    function prevCard() {
        if (fcLoopTimeout) clearTimeout(fcLoopTimeout);
        if (currentAudio) currentAudio.pause();

        // В Study режиме: не циклируем при ручном переключении
        if (fcMode === "study") {
            const prevIdx = currentCardIdx - 1;
            if (prevIdx < 0) {
                fcIsPlaying = false;
                return;
            }
            currentCardIdx = prevIdx;
        } else {
            // Review режим: циклируем как обычно
            currentCardIdx =
                (currentCardIdx - 1 + sessionCards.length) %
                sessionCards.length;
        }
        isFlipped = false;
        // Якщо було включено в Study - продовжуємо цикл з попереднім словом
        if (fcMode === "study" && fcIsPlaying) {
            runStudyLoop();
        } else {
            fcIsPlaying = false;
        }
    }

    async function rateCard(rating) {
        const card = sessionCards[currentCardIdx];

        // === STUDY MODE: Просто продовжуємо, без обновлення БД ===
        if (fcMode === "study") {
            currentCardIdx = (currentCardIdx + 1) % sessionCards.length;
            isFlipped = false;
            return;
        }

        // === REVIEW MODE: Обновлюємо SM-2 та переходимо до наступного ===
        fcStats[rating]++;
        try {
            await api.post("/vocab/update_progress", { id: card.id, rating });

            isFlipped = false;
            if (currentCardIdx < sessionCards.length - 1) {
                currentCardIdx++;
                const nextCard = sessionCards[currentCardIdx];
                if (fcAudioEnabled && !fcUseContextMode) {
                    if (fcReverseMode) {
                        const transLang =
                            $user?.interface_language === "ukr" ? "uk" : "en";
                        (async () => {
                            const transParts = nextCard.trans
                                .split(",")
                                .map((p) => p.trim())
                                .filter((p) => p);
                            for (const part of transParts) {
                                try {
                                    const res = await api.post(
                                        "/vocab/generate_audio",
                                        { text: part, lang: transLang },
                                    );
                                    if (res.data.url)
                                        await playAudioPromise(res.data.url);
                                } catch (e) {
                                    console.error(e);
                                }
                            }
                        })();
                    } else {
                        playAudio(nextCard.audio_de_url);
                    }
                }
            } else {
                // Кінець сесії Review - показуємо splash screen
                showSessionSplash = true;
                // Розраховуємо score тільки для Review режиму
                if (fcMode === "review") {
                    const total = fcStats.easy + fcStats.medium + fcStats.hard;
                    const score =
                        total > 0
                            ? Math.round((fcStats.easy / total) * 100)
                            : 0;
                    sessionScore = score;

                    // Запускаємо конфеті якщо perfect (100% easy або всі карти rated)
                    if (score === 100) {
                        setTimeout(launchConfetti, 300);
                    }
                }
                showSession = false;
            }
        } catch (e) {
            console.error(e);
        }
    }

    // --- AUDIO & UTILS ---

    function playAudio(url) {
        if (!url) return;
        if (currentAudio) currentAudio.pause();
        currentAudio = new Audio(url);
        currentAudio.play().catch((e) => console.log(e));
    }

    function playAudioPromise(url) {
        return new Promise((resolve) => {
            if (!url) {
                resolve();
                return;
            }
            if (currentAudio) currentAudio.pause();
            currentAudio = new Audio(url);
            currentAudio.onended = resolve;
            currentAudio.onerror = resolve;
            currentAudio.play().catch(resolve);
        });
    }

    async function playVocabPair(
        de,
        trans = "",
        audioDeUrl = null,
        audioTransUrls = [],
    ) {
        if (currentAudio) currentAudio.pause();

        try {
            // Determine translation language based on user's interface language
            const transLang = $user?.interface_language === "ukr" ? "uk" : "en";

            // Play German if available or generate if missing
            if (de) {
                let urlToPlay = audioDeUrl;

                // If no cached URL, generate it
                if (!urlToPlay) {
                    try {
                        const res = await api.post("/vocab/generate_audio", {
                            text: de,
                            lang: "de",
                        });
                        urlToPlay = res.data.url;
                    } catch (e) {
                        console.error("Failed to generate German audio:", e);
                        return;
                    }
                }

                if (urlToPlay) {
                    await playAudioPromise(urlToPlay);
                    await new Promise((r) => setTimeout(r, 300));
                }
            }

            // Play translation (from cache or generate if missing)
            if (trans) {
                if (audioTransUrls && audioTransUrls.length > 0) {
                    // Have cached URLs, play them
                    for (const url of audioTransUrls) {
                        if (url) {
                            await playAudioPromise(url);
                            await new Promise((r) => setTimeout(r, 300));
                        }
                    }
                } else {
                    // No cached URLs - need to generate for each part
                    try {
                        // Split translation by commas
                        const transParts = trans
                            .split(",")
                            .map((p) => p.trim())
                            .filter((p) => p);
                        for (const part of transParts) {
                            const res = await api.post(
                                "/vocab/generate_audio",
                                { text: part, lang: transLang },
                            );
                            if (res.data.url) {
                                await playAudioPromise(res.data.url);
                                await new Promise((r) => setTimeout(r, 300));
                            }
                        }
                    } catch (e) {
                        console.error(
                            "Failed to generate translation audio:",
                            e,
                        );
                    }
                }
            }
        } catch (e) {
            console.error("Playback error:", e);
        }
    }

    async function playSentencePair(s) {
        // Removed - sentences no longer supported
    }

    // --- ITEM ACTIONS ---

    function toggleContext(id) {
        if (expandedContexts[id]) {
            // Закриваємо контекст цього слова
            delete expandedContexts[id];
        } else {
            // Закриваємо всі інші контексти
            expandedContexts = {};
            // Відкриваємо контекст цього слова
            expandedContexts[id] = true;
        }
    }

    async function deleteItem(id, isSentence = false) {
        const originalItems = [...items];
        const itemToDelete = items.find(
            (i) => (isSentence ? i.fav_id : i.id) === id,
        );
        if (!itemToDelete) return;

        // 1. Optimistic UI update
        items = items.filter((i) => (isSentence ? i.fav_id : i.id) !== id);

        // 2. Set up delayed delete
        const deleteTimeout = setTimeout(() => {
            const url = isSentence ? "/remove_fav_sentence" : "/remove_word";
            const payload = { id };
            if (!isSentence) payload.from_vocab = true;

            api.post(url, payload).catch((e) => {
                console.error("Final delete failed:", e);
            });
        }, 5000);

        // 3. Show toast with undo
        const undo = () => {
            clearTimeout(deleteTimeout);
            items = originalItems;
        };

        const message = isSentence
            ? ui.sentence_removed_fav || "Sentence removed from favorites"
            : ui.word_deleted || "Word deleted";
        addToast(message, "info", undo, 5000);
    }

    function startEdit(id, currentVal) {
        editingId = id;
        editValue = currentVal;
    }

    function cancelEdit() {
        editingId = null;
        editValue = "";
    }

    async function saveEdit(id) {
        try {
            const res = await api.post("/update_word", {
                id,
                translation: editValue,
            });
            // Update both translation and audio URLs from response
            items = items.map((i) =>
                i.id === id
                    ? {
                          ...i,
                          display_trans: editValue,
                          audio_trans_urls: res.data.audio_trans_urls || [],
                      }
                    : i,
            );
            editingId = null;
        } catch (e) {
            addToast("Error saving", "error");
        }
    }

    function handleGlobalClick(e) {
        if (editingId) cancelEdit();
        if (Object.keys(expandedContexts).length > 0) {
            expandedContexts = {};
        }
    }

    function handleWindowBlur() {
        if (editingId) cancelEdit();
        if (Object.keys(expandedContexts).length > 0) {
            expandedContexts = {};
        }
    }

    function handleKeydown(e) {
        if (!showSession) return;

        if (e.key === "Escape") {
            fcClose();
            return;
        }

        if (fcMode === "study") {
            if (e.code === "Space") {
                e.preventDefault();
                toggleFcPlay();
            }
            if (e.key === "ArrowRight") nextCard();
            if (e.key === "ArrowLeft") prevCard();
        } else {
            // Review
            if (!fcReviewStarted) {
                if (e.code === "Space") {
                    e.preventDefault();
                    startReview();
                }
                return;
            }
            if (!isFlipped) {
                if (e.code === "Space") {
                    e.preventDefault();
                    flipCard();
                }
            } else {
                if (e.key === "1" || e.key === "ArrowLeft") rateCard("hard");
                if (e.key === "2" || e.key === "ArrowDown") rateCard("medium");
                if (e.key === "3" || e.key === "ArrowRight") rateCard("easy");
            }
        }
    }

    onMount(() => {
        loadData();
        window.addEventListener("click", handleGlobalClick);
        window.addEventListener("blur", handleWindowBlur);
        window.addEventListener("keydown", handleKeydown);
    });

    onDestroy(() => {
        if (fcLoopTimeout) clearTimeout(fcLoopTimeout);
        if (currentAudio) currentAudio.pause();
        window.removeEventListener("click", handleGlobalClick);
        window.removeEventListener("blur", handleWindowBlur);
        window.removeEventListener("keydown", handleKeydown);
        expandedContexts = {}; // Закриваємо всі контексти при виході зе сторінки
    });

    function handleCardLeave(e) {
        if (viewMode !== "grid") return;
        const card = e.currentTarget;
        if (card.classList.contains("flipped")) {
            card._flipTimeout = setTimeout(() => {
                card.classList.remove("flipped");
                card._flipTimeout = null;
            }, 400);
        }
    }

    function handleCardEnter(e) {
        const card = e.currentTarget;
        if (card._flipTimeout) {
            clearTimeout(card._flipTimeout);
            card._flipTimeout = null;
        }
    }
</script>

<div class="vocab-header-controls">
    <div class="practice-row">
        <button
            class="btn-contained practice-btn"
            onclick={() => {
                fcMode = "study";
                startSession();
            }}
        >
            <span class="material-symbols-outlined">headphones</span><span
                class="practice-btn-label">{ui.mode_training}</span
            >
        </button>
        <button
            class="btn-contained practice-btn"
            onclick={() => {
                fcMode = "review";
                startSession();
            }}
        >
            <span class="material-symbols-outlined">school</span><span
                class="practice-btn-label">{ui.mode_test}</span
            >
        </button>
        <button
            class="btn-contained practice-btn add-word-btn"
            onclick={openAddWordDialog}
        >
            <span class="material-symbols-outlined">add</span><span
                class="practice-btn-label">{ui.add_custom_word_btn_label}</span
            >
        </button>
    </div>

    <div class="filters-row" class:search-active={searchFocused}>
        <div class="search-wrap">
            <span class="material-symbols-outlined search-icon">search</span>
            <input
                type="text"
                class="search-input"
                placeholder={ui.search || "Search..."}
                bind:value={searchQuery}
                oninput={onSearchChange}
                onfocus={() => (searchFocused = true)}
                onblur={() => (searchFocused = false)}
            />
            {#if searchQuery}
                <button class="clear-search-btn" onclick={clearSearch}
                    ><span class="material-symbols-outlined">close</span
                    ></button
                >
            {/if}
        </div>

        <div class="filters-right">
            <div class="level-filters">
                {#each allLevels as lvl}
                    <button
                        class="lvl-filter"
                        class:active={selectedLevels.includes(lvl)}
                        onclick={() => toggleLevel(lvl)}
                        data-lvl={lvl}
                    >
                        {lvl}
                    </button>
                {/each}
            </div>

            <div class="view-toggles">
                <button
                    class="view-btn"
                    class:active={viewMode === "list"}
                    onclick={() => (viewMode = "list")}
                >
                    <span class="material-symbols-outlined">view_list</span>
                </button>
                <button
                    class="view-btn"
                    class:active={viewMode === "grid"}
                    onclick={() => (viewMode = "grid")}
                >
                    <span class="material-symbols-outlined">grid_view</span>
                </button>
            </div>
        </div>
    </div>
</div>

{#if showSession}
    <div class="session-overlay" role="dialog" aria-modal="true">
        <button class="fc-close-btn" onclick={fcClose} aria-label="Close">
            <span class="material-symbols-outlined" style="font-size: 32px;"
                >close</span
            >
            <div
                style="font-size: 0.9rem; font-weight: bold; opacity: 0.8; text-align: center; margin-top: 2px;"
            >
                Esc
            </div>
        </button>

        <div class="fc-container">
            <div class="fc-top-controls"></div>

            {#if fcMode === "review"}
                <div class="fc-progress-wrapper">
                    <div class="fc-progress-track">
                        <div
                            class="fc-progress-fill"
                            style="width: {(currentCardIdx /
                                sessionCards.length) *
                                100}%"
                        ></div>
                    </div>
                    <div class="fc-progress-text">
                        {currentCardIdx + 1} / {sessionCards.length}
                    </div>
                </div>
            {/if}

            <div class="fc-card-area">
                {#if fcMode === "review" && !fcReviewStarted}
                    <div class="fc-start-overlay">
                        <button
                            class="fc-start-btn"
                            onclick={(e) => {
                                e.stopPropagation();
                                startReview();
                            }}
                        >
                            <span class="material-symbols-outlined"
                                >play_arrow</span
                            >
                        </button>
                        <div
                            style="margin-top: 24px; opacity: 0.8; font-weight: 500; font-size: 1.2rem;"
                        >
                            {ui.fc_start_review}
                        </div>
                    </div>
                {/if}

                <div
                    class="fc-card"
                    class:flipped={isFlipped}
                    onclick={flipCard}
                    onkeydown={(e) =>
                        (e.key === "Enter" || e.key === " ") && flipCard()}
                    role="button"
                    tabindex="0"
                    style="display: {fcMode === 'review' && !fcReviewStarted
                        ? 'none'
                        : 'block'}"
                >
                    {#if fcReverseMode}
                        <!-- Режим развернутый: переводы сначала -->
                        <div class="fc-face fc-front">
                            <span
                                class="level-badge lvl-{sessionCards[
                                    currentCardIdx
                                ].level?.toLowerCase()}"
                                style="position:absolute; top:20px; left:20px; z-index: 5;"
                            >
                                {sessionCards[currentCardIdx].level || "?"}
                            </span>
                            <div
                                class={fcUseContextMode ? "fc-ctx" : "fc-word"}
                            >
                                {fcUseContextMode
                                    ? sessionCards[currentCardIdx].ctx_trans
                                    : sessionCards[currentCardIdx].trans}
                            </div>
                        </div>

                        <div class="fc-face fc-back">
                            <div
                                class={fcUseContextMode ? "fc-ctx" : "fc-word"}
                            >
                                {fcUseContextMode
                                    ? sessionCards[currentCardIdx].ctx
                                    : sessionCards[currentCardIdx].display}
                            </div>
                            {#if !fcUseContextMode && (fcMode === "review" || !fcIsPlaying)}
                                <div class="fc-ctx" style="margin-top: 20px;">
                                    {sessionCards[currentCardIdx].ctx}
                                </div>
                                {#if sessionCards[currentCardIdx].ctx_trans}
                                    <div
                                        class="fc-ctx-trans"
                                        style="opacity: 0.7; font-size: 1.1rem; margin-top: 10px; font-style: italic;"
                                    >
                                        {sessionCards[currentCardIdx].ctx_trans}
                                    </div>
                                {/if}
                            {/if}
                        </div>
                    {:else}
                        <!-- Нормальный режим: немецкий сначала -->
                        <div class="fc-face fc-front">
                            <span
                                class="level-badge lvl-{sessionCards[
                                    currentCardIdx
                                ].level?.toLowerCase()}"
                                style="position:absolute; top:20px; left:20px; z-index: 5;"
                            >
                                {sessionCards[currentCardIdx].level || "?"}
                            </span>
                            <div
                                class={fcUseContextMode ? "fc-ctx" : "fc-word"}
                            >
                                {fcUseContextMode
                                    ? sessionCards[currentCardIdx].ctx
                                    : sessionCards[currentCardIdx].display}
                            </div>
                        </div>

                        <div class="fc-face fc-back">
                            <div
                                class={fcUseContextMode ? "fc-ctx" : "fc-trans"}
                            >
                                {fcUseContextMode
                                    ? sessionCards[currentCardIdx].ctx_trans
                                    : sessionCards[currentCardIdx].trans}
                            </div>
                            {#if !fcUseContextMode && (fcMode === "review" || !fcIsPlaying)}
                                <div class="fc-ctx">
                                    {sessionCards[currentCardIdx].ctx}
                                </div>
                                {#if sessionCards[currentCardIdx].ctx_trans}
                                    <div
                                        class="fc-ctx-trans"
                                        style="opacity: 0.7; font-size: 1.1rem; margin-top: 10px; font-style: italic;"
                                    >
                                        {sessionCards[currentCardIdx].ctx_trans}
                                    </div>
                                {/if}
                            {/if}
                        </div>
                    {/if}
                </div>
            </div>

            {#if fcMode === "review" && fcReviewStarted}
                <div class="fc-review-hint-text">
                    {ui.fc_review_hint}
                </div>
            {/if}

            {#if fcMode === "study"}
                <div class="fc-study-hint-text">
                    {ui.fc_study_hint}
                </div>
            {/if}

            <div class="fc-bottom-controls">
                {#if fcMode === "study"}
                    <div class="fc-ctrl-row">
                        <button
                            class="fc-icon-btn"
                            class:active={fcAudioEnabled}
                            onclick={(e) => {
                                e.stopPropagation();
                                toggleFcAudio();
                            }}
                        >
                            <span class="material-symbols-outlined"
                                >volume_up</span
                            >
                        </button>
                        <button
                            class="fc-icon-btn"
                            class:active={fcReverseMode}
                            onclick={(e) => {
                                e.stopPropagation();
                                toggleFcReverseMode();
                            }}
                            title="Переключить порядок: перевод сначала"
                        >
                            <span class="material-symbols-outlined">flip</span>
                        </button>
                        <button class="fc-play-btn" onclick={toggleFcPlay}>
                            <span class="material-symbols-outlined"
                                >{fcIsPlaying ? "pause" : "play_arrow"}</span
                            >
                        </button>
                        <button
                            class="fc-icon-btn"
                            class:active={fcUseContextMode}
                            onclick={(e) => {
                                e.stopPropagation();
                                toggleFcContextMode();
                            }}
                            title="Режим речень"
                        >
                            <span class="material-symbols-outlined"
                                >description</span
                            >
                        </button>
                        <button
                            class="fc-icon-btn"
                            class:active={fcStudyLoop}
                            onclick={(e) => {
                                e.stopPropagation();
                                fcStudyLoop = !fcStudyLoop;
                            }}
                        >
                            <span class="material-symbols-outlined">repeat</span
                            >
                        </button>
                    </div>
                {:else if !isFlipped}
                    {#if !fcReviewStarted}
                        <div class="fc-ctrl-row">
                            <button
                                class="fc-icon-btn"
                                class:active={fcAudioEnabled}
                                onclick={(e) => {
                                    e.stopPropagation();
                                    toggleFcAudio();
                                }}
                            >
                                <span class="material-symbols-outlined"
                                    >volume_up</span
                                >
                            </button>
                            <button
                                class="fc-icon-btn"
                                class:active={fcReverseMode}
                                onclick={(e) => {
                                    e.stopPropagation();
                                    toggleFcReverseMode();
                                }}
                                title="Переключить порядок: перевод сначала"
                            >
                                <span class="material-symbols-outlined"
                                    >flip</span
                                >
                            </button>
                            <button
                                class="fc-icon-btn"
                                class:active={fcUseContextMode}
                                onclick={(e) => {
                                    e.stopPropagation();
                                    toggleFcContextMode();
                                }}
                                title="Режим речень"
                            >
                                <span class="material-symbols-outlined"
                                    >description</span
                                >
                            </button>
                        </div>
                    {:else}
                        <div class="fc-ctrl-row">
                            <button
                                class="fc-icon-btn"
                                class:active={fcAudioEnabled}
                                onclick={(e) => {
                                    e.stopPropagation();
                                    toggleFcAudio();
                                }}
                            >
                                <span class="material-symbols-outlined"
                                    >volume_up</span
                                >
                            </button>
                            <button
                                class="fc-icon-btn"
                                class:active={fcReverseMode}
                                onclick={(e) => {
                                    e.stopPropagation();
                                    toggleFcReverseMode();
                                }}
                                title="Переключить порядок: перевод сначала"
                            >
                                <span class="material-symbols-outlined"
                                    >flip</span
                                >
                            </button>
                            <button
                                class="fc-icon-btn"
                                class:active={fcUseContextMode}
                                onclick={(e) => {
                                    e.stopPropagation();
                                    toggleFcContextMode();
                                }}
                                title="Режим речень"
                            >
                                <span class="material-symbols-outlined"
                                    >description</span
                                >
                            </button>
                        </div>
                    {/if}
                {:else if fcMode === "review" && fcReviewStarted && isFlipped}
                    <div class="fc-ctrl-row" style="gap: 20px;">
                        <button
                            class="fc-rate-btn hard"
                            onclick={() => rateCard("hard")}
                        >
                            <span class="material-symbols-outlined"
                                >sentiment_very_dissatisfied</span
                            >
                            {ui.fc_hard}
                            <span class="kb-hint">[1]</span>
                        </button>
                        <button
                            class="fc-rate-btn mid"
                            onclick={() => rateCard("medium")}
                        >
                            <span class="material-symbols-outlined"
                                >sentiment_neutral</span
                            >
                            {ui.fc_medium}
                            <span class="kb-hint">[2]</span>
                        </button>
                        <button
                            class="fc-rate-btn easy"
                            onclick={() => rateCard("easy")}
                        >
                            <span class="material-symbols-outlined"
                                >sentiment_very_satisfied</span
                            >
                            {ui.fc_easy}
                            <span class="kb-hint">[3]</span>
                        </button>
                    </div>
                {/if}
            </div>
        </div>
    </div>
{:else}
    {#if showSessionSplash}
        <div id="vocab-splash">
            <h2 style="margin-bottom: 30px;">{ui.fc_session_complete}</h2>

            {#if fcMode === "review"}
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
                                (sessionScore / 100) *
                                    434}; stroke: {sessionScore >= 80
                                ? '#4CAF50'
                                : sessionScore >= 50
                                  ? '#FFC107'
                                  : '#f44336'};"
                        ></circle>
                    </svg>
                    <span id="splash-score">{sessionScore.toFixed(0)}%</span>
                </div>
                <div
                    style="font-size: 1.2rem; margin-bottom: 40px; opacity: 0.8;"
                >
                    {ui.your_score}
                </div>
            {:else}
                <div
                    style="font-size: 1.2rem; margin-bottom: 40px; opacity: 0.8;"
                >
                    {ui.study_completed}
                </div>
            {/if}

            <div style="display: flex; gap: 20px;">
                <button
                    class="btn-contained"
                    style="background: white; color: black;"
                    onclick={closeSplash}>{ui.done_btn}</button
                >
                <button class="btn-contained" onclick={continueSplash}
                    >{ui.continue_btn}</button
                >
            </div>
        </div>
    {/if}

    <div class="vocab-wrapper {viewMode}">
        {#each items as w (w.id)}
            <div
                class="vocab-item lvl-strip-{w.level?.toLowerCase()}"
                class:grid-card={viewMode === "grid"}
                role="button"
                tabindex="0"
                onkeydown={(e) => {
                    if (
                        (e.key === "Enter" || e.key === " ") &&
                        viewMode === "grid" &&
                        !e.target.closest("button")
                    )
                        e.currentTarget.classList.toggle("flipped");
                }}
                onclick={(e) => {
                    if (viewMode === "grid" && !e.target.closest("button"))
                        e.currentTarget.classList.toggle("flipped");
                    if (viewMode === "list" && expandedContexts[w.id])
                        e.stopPropagation();
                }}
                onmouseleave={handleCardLeave}
                onmouseenter={handleCardEnter}
            >
                <div class="vocab-card-inner">
                    <div class="vocab-face vocab-front">
                        {#if viewMode === "grid"}
                            <span
                                class="level-badge lvl-{w.level?.toLowerCase()}"
                                style="position:absolute; top:12px; left:12px;"
                                >{w.level}</span
                            >
                        {/if}

                        <div class="item-content">
                            <div class="vocab-main-row">
                                <div class="vocab-word-group">
                                    <button
                                        class="btn-text list-audio-btn"
                                        onclick={(e) => {
                                            e.stopPropagation();
                                            playVocabPair(
                                                w.display,
                                                w.display_trans,
                                                w.audio_de_url,
                                                w.audio_trans_urls,
                                            );
                                        }}
                                    >
                                        <span class="material-symbols-outlined"
                                            >volume_up</span
                                        >
                                    </button>
                                    <div
                                        class="vocab-text-area"
                                        class:editing={editingId === w.id}
                                    >
                                        <div
                                            class="word-text"
                                            role="button"
                                            tabindex="0"
                                            onkeydown={(e) => {
                                                e.stopPropagation();
                                                if (
                                                    e.key === "Enter" ||
                                                    e.key === " "
                                                )
                                                    toggleContext(w.id);
                                            }}
                                            onclick={(e) => {
                                                e.stopPropagation();
                                                toggleContext(w.id);
                                            }}
                                        >
                                            {w.display}
                                        </div>
                                        {#if editingId === w.id}
                                            <input
                                                type="text"
                                                class="edit-input"
                                                bind:value={editValue}
                                                onclick={(e) =>
                                                    e.stopPropagation()}
                                                onkeydown={(e) => {
                                                    e.stopPropagation();
                                                    if (e.key === "Enter")
                                                        saveEdit(w.id);
                                                }}
                                            />
                                        {:else}
                                            <div class="trans-text">
                                                {w.display_trans}
                                            </div>
                                        {/if}
                                    </div>
                                </div>

                                {#if viewMode === "list"}
                                    <div
                                        class="list-tools"
                                        style="display:flex; align-items:center; gap: 8px;"
                                    >
                                        {#if editingId === w.id}
                                            <button
                                                class="btn-text"
                                                style="color:var(--primary); padding:0; min-width:32px;"
                                                onclick={(e) => {
                                                    e.stopPropagation();
                                                    saveEdit(w.id);
                                                }}
                                            >
                                                <span
                                                    class="material-symbols-outlined"
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
                                                <span
                                                    class="material-symbols-outlined"
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
                                                        w.id,
                                                        w.display_trans,
                                                    );
                                                }}
                                            >
                                                <span
                                                    class="material-symbols-outlined"
                                                    >edit</span
                                                >
                                            </button>
                                            <button
                                                class="btn-text delete-btn"
                                                onclick={(e) => {
                                                    e.stopPropagation();
                                                    deleteItem(w.id);
                                                }}
                                            >
                                                <span
                                                    class="material-symbols-outlined"
                                                    >delete</span
                                                >
                                            </button>
                                        {/if}
                                    </div>
                                {/if}

                                {#if viewMode === "list"}
                                    <div class="vocab-item-controls">
                                        <button
                                            class="vocab-ctrl-btn"
                                            onclick={(e) => {
                                                e.stopPropagation();
                                                playVocabPair(
                                                    w.display,
                                                    w.display_trans,
                                                    w.audio_de_url,
                                                    w.audio_trans_urls,
                                                );
                                            }}
                                        >
                                            <span
                                                class="material-symbols-outlined"
                                                >volume_up</span
                                            >
                                        </button>
                                        {#if editingId === w.id}
                                            <button
                                                class="vocab-ctrl-btn"
                                                style="color:var(--primary);"
                                                onclick={(e) => {
                                                    e.stopPropagation();
                                                    saveEdit(w.id);
                                                }}
                                            >
                                                <span
                                                    class="material-symbols-outlined"
                                                    >check</span
                                                >
                                            </button>
                                            <button
                                                class="vocab-ctrl-btn"
                                                onclick={(e) => {
                                                    e.stopPropagation();
                                                    cancelEdit();
                                                }}
                                            >
                                                <span
                                                    class="material-symbols-outlined"
                                                    >close</span
                                                >
                                            </button>
                                        {:else}
                                            <button
                                                class="vocab-ctrl-btn"
                                                style="color:var(--primary);"
                                                onclick={(e) => {
                                                    e.stopPropagation();
                                                    startEdit(
                                                        w.id,
                                                        w.display_trans,
                                                    );
                                                }}
                                            >
                                                <span
                                                    class="material-symbols-outlined"
                                                    >edit</span
                                                >
                                            </button>
                                            <button
                                                class="vocab-ctrl-btn delete-ctrl"
                                                onclick={(e) => {
                                                    e.stopPropagation();
                                                    deleteItem(w.id);
                                                }}
                                            >
                                                <span
                                                    class="material-symbols-outlined"
                                                    >delete</span
                                                >
                                            </button>
                                        {/if}
                                    </div>
                                {/if}
                            </div>

                            {#if viewMode === "list" && expandedContexts[w.id] && w.ctx}
                                <div class="ctx-block">
                                    <div class="ctx-label">{ui.context}</div>
                                    <div class="ctx-text">{w.ctx}</div>
                                    {#if w.display_ctx_trans}
                                        <div
                                            class="ctx-text-trans"
                                            style="opacity: 0.7; font-size: 0.85rem; margin-top: 4px; font-style: italic; color: var(--primary);"
                                        >
                                            {w.display_ctx_trans}
                                        </div>
                                    {/if}
                                    {#if w.text_id}
                                        <button
                                            type="button"
                                            class="ctx-link btn-text"
                                            style="padding:0; height:auto; text-transform:none;"
                                            onclick={() =>
                                                router.goto(
                                                    `/view/${w.text_id}#sent-${w.sentence_index}`,
                                                )}
                                        >
                                            <span
                                                class="material-symbols-outlined"
                                                style="font-size:14px;"
                                                >open_in_new</span
                                            >
                                            {ui.go_to_text}
                                        </button>
                                    {/if}
                                </div>
                            {/if}
                        </div>

                        {#if viewMode === "grid"}
                            <div class="grid-footer">
                                <button
                                    class="btn-text"
                                    onclick={(e) => {
                                        e.stopPropagation();
                                        playVocabPair(
                                            w.display,
                                            w.display_trans,
                                            w.audio_de_url,
                                            w.audio_trans_urls,
                                        );
                                    }}
                                >
                                    <span class="material-symbols-outlined"
                                        >volume_up</span
                                    >
                                </button>
                                {#if editingId === w.id}
                                    <button
                                        class="btn-text"
                                        style="color:var(--primary); opacity:1;"
                                        onclick={(e) => {
                                            e.stopPropagation();
                                            saveEdit(w.id);
                                        }}
                                    >
                                        <span class="material-symbols-outlined"
                                            >check</span
                                        >
                                    </button>
                                {:else}
                                    <button
                                        class="btn-text"
                                        style="color:var(--primary); opacity:0.7;"
                                        onclick={(e) => {
                                            e.stopPropagation();
                                            startEdit(w.id, w.display_trans);
                                        }}
                                    >
                                        <span class="material-symbols-outlined"
                                            >edit</span
                                        >
                                    </button>
                                {/if}
                                <button
                                    class="btn-text delete-btn"
                                    onclick={(e) => {
                                        e.stopPropagation();
                                        deleteItem(w.id);
                                    }}
                                >
                                    <span class="material-symbols-outlined"
                                        >delete</span
                                    >
                                </button>
                            </div>
                        {/if}
                    </div>

                    {#if viewMode === "grid"}
                        <div class="vocab-face vocab-back">
                            <div class="vocab-back-scroll">
                                <div class="ctx-text">{w.ctx}</div>
                                {#if w.display_ctx_trans}
                                    <div
                                        class="ctx-text-trans"
                                        style="opacity: 0.7; font-size: 0.9rem; margin-top: 8px; font-style: italic; color: var(--primary);"
                                    >
                                        {w.display_ctx_trans}
                                    </div>
                                {/if}
                            </div>
                            {#if w.text_id}
                                <button
                                    type="button"
                                    class="ctx-link btn-text"
                                    style="padding:0; height:auto; text-transform:none;"
                                    onclick={() =>
                                        router.goto(
                                            `/view/${w.text_id}#sent-${w.sentence_index}`,
                                        )}
                                >
                                    <span
                                        class="material-symbols-outlined"
                                        style="font-size:14px;"
                                        >open_in_new</span
                                    >
                                    {ui.go_to_text}
                                </button>
                            {/if}
                        </div>
                    {/if}
                </div>
            </div>
        {/each}
    </div>

    {#if totalPages > 1}
        <div class="pagination">
            <button
                class="page-btn nav-btn"
                disabled={page === 1}
                onclick={() => changePage(page - 1)}
            >
                <span class="material-symbols-outlined">chevron_left</span>
            </button>

            {#each paginationRange as p}
                {#if p === "..."}
                    <span class="page-dots">...</span>
                {:else}
                    <button
                        class="page-btn"
                        class:active={p === page}
                        onclick={() => changePage(p)}
                    >
                        {p}
                    </button>
                {/if}
            {/each}

            <button
                class="page-btn nav-btn"
                disabled={page === totalPages}
                onclick={() => changePage(page + 1)}
            >
                <span class="material-symbols-outlined">chevron_right</span>
            </button>
        </div>
    {/if}
{/if}

{#if showAddWordDialog}
    <div class="add-word-overlay" role="dialog" aria-modal="true">
        <div class="add-word-container">
            <button
                class="add-word-close-btn"
                onclick={closeAddWordDialog}
                aria-label="Close"
            >
                <span class="material-symbols-outlined">close</span>
            </button>
            <h2>{ui.add_custom_word_title}</h2>
            <p style="opacity: 0.7; margin-bottom: 20px;">
                {ui.add_custom_word_hint}
            </p>

            <div class="add-word-input-group">
                <input
                    type="text"
                    class="add-word-input"
                    placeholder={ui.add_custom_word_placeholder}
                    bind:value={customWordInput}
                    bind:this={customWordInputRef}
                    onkeydown={(e) => e.key === "Enter" && addCustomWord()}
                    disabled={addingWord}
                />
                <button
                    class="btn-contained"
                    onclick={addCustomWord}
                    disabled={addingWord || !customWordInput.trim()}
                >
                    {addingWord
                        ? ui.add_custom_word_adding
                        : ui.add_custom_word_btn}
                </button>
            </div>
        </div>
    </div>
{/if}

<style>
    /* Global focus outline reset */
    :global(*) {
        outline: none !important;
    }
    :global(*:focus),
    :global(*:focus-visible) {
        outline: none !important;
        box-shadow: none !important;
    }
    :global(button),
    :global(input),
    :global(textarea),
    :global(select) {
        outline: none !important;
    }
    :global(button:focus),
    :global(input:focus),
    :global(textarea:focus),
    :global(select:focus),
    :global(button:focus-visible),
    :global(input:focus-visible),
    :global(textarea:focus-visible),
    :global(select:focus-visible) {
        outline: none !important;
        box-shadow: none !important;
    }

    /* Controls */
    .vocab-header-controls {
        margin-bottom: 20px;
    }
    .mode-switch {
        display: flex;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 20px;
        padding: 4px;
        width: fit-content;
        margin: 0 auto 20px auto;
    }
    .mode-btn {
        padding: 8px 24px;
        border-radius: 16px;
        border: none;
        background: transparent;
        color: var(--on-surface);
        font-weight: 500;
        cursor: pointer;
        opacity: 0.6;
    }
    .mode-btn.active {
        background: var(--primary);
        color: var(--on-primary);
        opacity: 1;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }

    .search-input {
        padding: 8px 12px;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        background: var(--surface);
        color: var(--on-surface);
        font-size: 0.95rem;
        min-width: 200px;
    }
    .search-input::placeholder {
        opacity: 0.5;
    }

    .filters-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
    }
    .filters-right {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .practice-btn {
        background: var(--secondary);
        color: #000;
        height: 32px;
        font-size: 0.85rem;
    }
    .add-word-btn {
        background: #4caf50;
        color: white;
    }

    .level-filters {
        display: flex;
        gap: 4px;
        margin-left: auto;
    }
    .lvl-filter {
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        cursor: pointer;
        border: 1px solid var(--border);
        background: var(--surface);
        color: var(--on-surface);
        opacity: 0.6;
    }
    .lvl-filter.active {
        opacity: 1;
        color: white;
        border-color: transparent;
    }
    .lvl-filter.active[data-lvl="A1"] {
        background-color: #8bc34a;
    }
    .lvl-filter.active[data-lvl="A2"] {
        background-color: #4caf50;
    }
    .lvl-filter.active[data-lvl="B1"] {
        background-color: #29b6f6;
    }
    .lvl-filter.active[data-lvl="B2"] {
        background-color: #1976d2;
    }
    .lvl-filter.active[data-lvl="C1"] {
        background-color: #d32f2f;
    }
    .lvl-filter.active[data-lvl="C2"] {
        background-color: #311b92;
    }

    .view-toggles {
        display: flex;
        gap: 4px;
    }
    .view-btn {
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1px solid var(--border);
        background: transparent;
        border-radius: 6px;
        cursor: pointer;
        opacity: 0.6;
        color: var(--on-surface);
    }
    .view-btn.active {
        background: var(--primary);
        color: white;
        opacity: 1;
        border-color: var(--primary);
    }

    /* List View */
    .vocab-wrapper.list {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .vocab-item {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        box-shadow: var(--shadow);
        overflow: hidden;
        font-family: var(--font-text);
    }
    .vocab-main-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
    }
    .vocab-word-group {
        display: flex;
        align-items: stretch;
        gap: 12px;
        flex: 1;
        min-width: 0;
    }
    .word-text {
        font-weight: 500;
        color: var(--primary);
        font-size: 1.1rem;
        cursor: pointer;
        font-family: var(--font-text);
    }
    .trans-text {
        font-size: 0.9rem;
        opacity: 0.8;
        margin-top: 4px;
        font-family: var(--font-text);
    }
    .list-audio-btn {
        padding: 0;
        min-width: 32px;
        color: var(--primary);
    }
    .delete-btn {
        color: #d32f2f;
        min-width: 32px;
        padding: 0;
    }

    .ctx-block {
        padding: 0 16px 12px 56px;
        background: rgba(0, 0, 0, 0.02);
        font-size: 0.9rem;
        font-family: var(--font-text);
    }
    .ctx-label {
        font-size: 0.75rem;
        color: var(--primary);
        font-weight: 500;
        margin-bottom: 2px;
    }
    .ctx-text {
        font-style: italic;
        opacity: 0.9;
        margin-bottom: 6px;
        font-family: var(--font-text);
    }
    .ctx-link {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 0.8rem;
        color: var(--primary);
        text-decoration: none;
        cursor: pointer;
    }

    .vocab-text-area {
        flex: 1;
        min-width: 0;
        text-align: left;
        font-family: var(--font-text);
    }
    .edit-input {
        flex: 1;
        width: 100%;
        min-width: 0;
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
    .edit-textarea {
        width: 100%;
        height: 80px;
        border: 1px solid var(--primary);
        border-radius: 4px;
        padding: 8px;
        font-family: var(--font-text);
        resize: none;
    }

    /* Level Strips */
    .lvl-strip-a1 {
        border-left: 10px solid #8bc34a;
    }
    .lvl-strip-a2 {
        border-left: 10px solid #4caf50;
    }
    .lvl-strip-b1 {
        border-left: 10px solid #29b6f6;
    }
    .lvl-strip-b2 {
        border-left: 10px solid #1976d2;
    }
    .lvl-strip-c1 {
        border-left: 10px solid #d32f2f;
    }
    .lvl-strip-c2 {
        border-left: 10px solid #311b92;
    }

    /* Grid View */
    .vocab-wrapper.grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 20px;
    }
    .vocab-wrapper.grid .vocab-item {
        height: 200px;
        perspective: 1000px;
        background: transparent;
        border: none;
        box-shadow: none;
        overflow: visible;
        font-family: var(--font-text);
    }
    .vocab-wrapper.grid .vocab-card-inner {
        position: relative;
        width: 100%;
        height: 100%;
        text-align: center;
        transition: transform 0.6s;
        transform-style: preserve-3d;
    }
    .vocab-item.flipped .vocab-card-inner {
        transform: rotateY(180deg);
    }

    .vocab-wrapper.grid .vocab-face {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        backface-visibility: hidden;
        border-radius: var(--radius);
        box-shadow: var(--shadow);
        border: 1px solid var(--border);
        background: var(--surface);
        display: flex;
        flex-direction: column;
        overflow: hidden;
        box-sizing: border-box;
        font-family: var(--font-text);
    }
    .vocab-front {
        z-index: 2;
    }
    .vocab-back {
        transform: rotateY(180deg);
        padding: 24px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        font-family: var(--font-text);
    }

    .vocab-back-scroll {
        flex: 1;
        overflow-y: auto;
        width: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
        scrollbar-width: thin;
        font-family: var(--font-text);
    }
    .vocab-back-scroll::-webkit-scrollbar {
        width: 4px;
    }
    .vocab-back-scroll::-webkit-scrollbar-thumb {
        background: rgba(0, 0, 0, 0.2);
        border-radius: 4px;
    }

    .vocab-wrapper.grid .item-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: center;
        padding: 10px;
        font-family: var(--font-text);
    }
    .vocab-wrapper.grid .vocab-main-row {
        flex-direction: column;
        text-align: center;
    }
    .vocab-wrapper.grid .vocab-word-group {
        flex-direction: column;
        width: 100%;
    }
    .vocab-wrapper.grid .list-audio-btn {
        display: none;
    }
    .vocab-wrapper.grid .vocab-text-area {
        text-align: center;
        width: 100%;
        display: block;
        font-family: var(--font-text);
    }
    .vocab-wrapper.grid .vocab-text-area.editing {
        text-align: left;
    }
    .vocab-wrapper.grid .edit-input {
        text-align: left;
        width: 100%;
        display: block;
        box-sizing: border-box;
        font-family: var(--font-text);
    }
    .vocab-wrapper.grid .ctx-text {
        white-space: normal;
        word-wrap: break-word;
        font-family: var(--font-text);
    }
    .vocab-wrapper.grid .word-text {
        font-size: 1.2rem;
        margin-bottom: 8px;
        font-family: var(--font-text);
    }

    .grid-footer {
        height: 40px;
        border-top: 1px solid var(--border);
        background: rgba(0, 0, 0, 0.02);
        display: flex;
        justify-content: space-around;
        align-items: center;
    }

    /* Flashcard Styles */
    .session-overlay {
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
    }

    .fc-close-btn {
        position: absolute;
        top: 24px;
        right: 24px;
        z-index: 2005;
        background: none;
        border: none;
        color: var(--on-surface);
        cursor: pointer;
        padding: 8px;
    }

    .fc-container {
        width: 100%;
        max-width: 600px;
        height: 100%;
        display: flex;
        flex-direction: column;
        background: transparent;
        padding: 20px;
        box-sizing: border-box;
    }

    .fc-top-controls {
        padding: 20px;
        display: flex;
        justify-content: center;
    }
    .fc-mode-toggle {
        background: rgba(0, 0, 0, 0.05);
        border-radius: 20px;
        padding: 4px;
        display: flex;
    }
    .fc-mode-opt {
        padding: 8px 20px;
        border: none;
        background: transparent;
        border-radius: 16px;
        font-weight: 500;
        cursor: pointer;
        color: var(--on-surface);
        opacity: 0.6;
    }
    .fc-mode-opt.active {
        background: var(--surface);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        opacity: 1;
        color: var(--primary);
    }

    /* Progress Bar */
    .fc-progress-wrapper {
        padding: 0 24px;
        margin-bottom: 10px;
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

    /* Card Area */
    .fc-card-area {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        perspective: 1000px;
        position: relative;
        width: 100%;
    }

    .fc-card {
        width: 100%;
        height: 340px;
        position: relative;
        transform-style: preserve-3d;
        transition: transform 0.6s;
        cursor: pointer;
        background: transparent;
        box-sizing: border-box;
        outline: none;
        border: none;
    }

    .fc-card:focus {
        outline: none;
    }
    .fc-card:focus-visible {
        outline: none;
    }

    .fc-card.flipped {
        transform: rotateY(180deg);
    }

    .fc-face {
        position: absolute;
        width: 100%;
        height: 100%;
        backface-visibility: hidden;
        -webkit-backface-visibility: hidden;
        background: var(--surface);
        border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
        border: 1px solid var(--border);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 20px;
        text-align: center;
        box-sizing: border-box;
        overflow: hidden;
    }

    .fc-front {
        z-index: 2;
        transform: rotateY(0deg);
    }
    .fc-back {
        transform: rotateY(180deg);
    }

    .fc-word {
        font-size: 2.5rem;
        font-weight: 700;
        color: var(--on-surface);
        margin-bottom: 10px;
    }
    .fc-trans {
        font-size: 2rem;
        margin-bottom: 20px;
        color: var(--primary);
        font-weight: 600;
    }
    .fc-ctx {
        font-style: italic;
        opacity: 0.9;
        font-size: 1.3rem;
        line-height: 1.5;
        color: var(--on-surface);
    }
    .fc-hint {
        position: absolute;
        bottom: 20px;
        opacity: 0.4;
        font-size: 0.8rem;
    }

    /* Start Overlay for Review Mode */
    .fc-start-overlay {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        z-index: 10;
    }

    .fc-start-btn {
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

    .fc-start-btn:active {
        transform: scale(0.95);
    }
    .fc-start-btn span {
        font-size: 64px;
    }

    /* Hint Text */
    .fc-study-hint-text {
        margin-top: 40px;
        text-align: center;
        font-weight: 500;
        opacity: 0.7;
        font-size: 0.9rem;
        color: var(--on-surface);
    }

    .fc-review-hint-text {
        margin-top: 40px;
        text-align: center;
        font-weight: 500;
        opacity: 0.7;
        font-size: 0.9rem;
        color: var(--on-surface);
    }

    /* Bottom Controls */
    .fc-bottom-controls {
        padding: 24px;
        min-height: 160px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .fc-ctrl-row {
        display: flex;
        align-items: center;
        gap: 20px;
        width: 100%;
        justify-content: center;
    }

    .fc-icon-btn {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        border: 1px solid var(--border);
        background: var(--surface);
        color: var(--on-surface);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
    }

    .fc-icon-btn:active {
        transform: scale(0.95);
    }
    .fc-icon-btn.active {
        color: var(--primary);
        border-color: var(--primary);
        background: rgba(25, 118, 210, 0.05);
    }

    .fc-play-btn {
        min-width: 72px;
        height: 72px;
        border-radius: 50%;
        border: none;
        background: var(--primary);
        color: white;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 12px rgba(25, 118, 210, 0.3);
        transition: transform 0.1s;
    }

    .fc-play-btn:active {
        transform: scale(0.95);
    }
    .fc-play-btn span {
        font-size: 36px;
    }

    .fc-rate-btn {
        min-width: 100px;
        height: 100px;
        border-radius: 50%;
        border: none;
        font-weight: 600;
        cursor: pointer;
        font-size: 0.9rem;
        transition: transform 0.1s;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 4px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
    }

    .fc-rate-btn:active {
        transform: scale(0.95);
    }
    .fc-rate-btn.hard {
        background: #ff5252;
        color: white;
    }
    .fc-rate-btn.mid {
        background: #ffc107;
        color: #333;
    }
    .fc-rate-btn.easy {
        background: #4caf50;
        color: white;
    }

    .kb-hint {
        font-size: 0.7rem;
        opacity: 0.6;
        margin-top: 4px;
        font-weight: normal;
    }

    .fc-study-hint-text {
        text-align: center;
        margin-top: 10px;
        font-weight: 500;
        opacity: 0.7;
        font-size: 0.9rem;
        color: var(--on-surface);
    }

    .fc-stats-grid {
        display: flex;
        gap: 30px;
        justify-content: center;
        margin: 30px 0;
    }
    .stat-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        font-size: 1.2rem;
        font-weight: bold;
    }
    .fc-start-overlay {
        position: absolute;
        z-index: 10;
    }

    .fc-close-btn {
        position: absolute;
        top: 24px;
        right: 24px;
        z-index: 2005;
        background: none;
        border: none;
        color: var(--on-surface);
        cursor: pointer;
        padding: 8px;
    }

    /* Top Toggle */
    .fc-top-controls {
        padding: 30px;
        display: flex;
        justify-content: center;
    }
    .fc-mode-toggle {
        background: rgba(0, 0, 0, 0.05);
        border-radius: 20px;
        padding: 4px;
        display: flex;
    }
    .fc-mode-opt {
        padding: 8px 20px;
        border: none;
        background: transparent;
        border-radius: 16px;
        font-weight: 500;
        cursor: pointer;
        color: var(--on-surface);
        opacity: 0.6;
    }
    .fc-mode-opt.active {
        background: var(--surface);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        opacity: 1;
        color: var(--primary);
    }

    /* Progress Bar */
    .fc-progress-wrapper {
        padding: 0 24px;
        margin-bottom: 10px;
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

    /* Bottom Controls */
    .fc-bottom-controls {
        padding: 24px;
        min-height: 160px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .fc-ctrl-row {
        display: flex;
        align-items: center;
        gap: 20px;
        width: 100%;
        justify-content: center;
    }

    .fc-icon-btn {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        border: 1px solid var(--border);
        background: var(--surface);
        color: var(--on-surface);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
    }
    .fc-icon-btn:active {
        transform: scale(0.95);
    }
    .fc-icon-btn.active {
        color: var(--primary);
        border-color: var(--primary);
        background: rgba(25, 118, 210, 0.05);
    }

    .fc-study-hint-text {
        text-align: center;
        margin-top: 10px;
        font-weight: 500;
        opacity: 0.7;
        font-size: 0.9rem;
        color: var(--on-surface);
    }

    .btn-audio {
        background: none;
        border: 1px solid var(--border);
        border-radius: 50%;
        width: 40px;
        height: 40px;
        color: var(--primary);
    }

    .pagination {
        display: flex;
        justify-content: center;
        gap: 8px;
        margin-top: 30px;
        align-items: center;
        flex-wrap: wrap;
    }
    .page-btn {
        min-width: 38px;
        height: 38px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--surface);
        color: var(--on-surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        cursor: pointer;
        font-weight: 500;
        transition: all 0.2s;
        padding: 0 8px;
        font-size: 0.95rem;
    }
    .page-btn:hover:not(:disabled) {
        border-color: var(--primary);
        color: var(--primary);
        background: rgba(0, 0, 0, 0.02);
    }
    .page-btn.active {
        background: var(--primary);
        color: white;
        border-color: var(--primary);
        box-shadow: 0 2px 8px rgba(25, 118, 210, 0.3);
    }
    .page-btn:disabled {
        opacity: 0.3;
        cursor: default;
    }
    .page-btn.nav-btn {
        border-color: transparent;
        background: transparent;
    }
    .page-btn.nav-btn:hover:not(:disabled) {
        background: rgba(0, 0, 0, 0.05);
    }
    .page-dots {
        width: 32px;
        text-align: center;
        opacity: 0.5;
        font-weight: bold;
    }

    /* Player Styles (Removed) */

    .fc-study-hint-text {
        text-align: center;
        margin-top: 40px;
        font-weight: 500;
        opacity: 0.7;
        font-size: 0.9rem;
        color: var(--on-surface);
    }

    /* Session Splash Screen */
    #vocab-splash {
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

    .score-circle {
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
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
        stroke-dasharray: 434;
        transition: stroke-dashoffset 1.5s ease-out;
    }
    #splash-score {
        font-size: 2.5rem;
        font-weight: 700;
        position: absolute;
        color: white;
    }

    /* Confetti Animation */
    :global(.vocab-confetti) {
        position: fixed;
        width: 10px;
        height: 10px;
        z-index: 10001;
        pointer-events: none;
        top: -20px;
    }
    @keyframes fall {
        to {
            transform: translateY(100vh) rotateZ(360deg);
            opacity: 0;
        }
    }

    /* Add Word Dialog */
    .add-word-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.7);
        backdrop-filter: blur(4px);
        z-index: 5000;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }

    .add-word-container {
        background: var(--surface);
        border-radius: 16px;
        padding: 32px;
        max-width: 500px;
        width: 90%;
        position: relative;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
    }

    .add-word-close-btn {
        position: absolute;
        top: 16px;
        right: 16px;
        background: none;
        border: none;
        cursor: pointer;
        color: var(--on-surface);
        padding: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .add-word-container h2 {
        margin: 0 0 16px 0;
        color: var(--on-surface);
        text-align: center;
    }

    .add-word-input-group {
        display: flex;
        gap: 10px;
        align-items: center;
    }

    .add-word-input {
        flex: 1;
        padding: 12px;
        border: 1px solid var(--border);
        border-radius: 8px;
        background: var(--bg);
        color: var(--on-surface);
        font-size: 1rem;
        outline: none;
    }

    .add-word-input:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }

    .add-word-input::placeholder {
        opacity: 0.5;
    }

    /* Search Input with Clear Button */
    .search-input-wrapper {
        position: relative;
        display: flex;
        align-items: center;
    }

    .clear-search-btn {
        position: absolute;
        right: 8px;
        background: none;
        border: none;
        color: var(--on-surface);
        opacity: 0.6;
        cursor: pointer;
        padding: 4px;
        display: flex;
    }

    /* Header restructure */
    .practice-row {
        display: flex;
        gap: 10px;
        margin-bottom: 12px;
    }
    .practice-btn-label {
        margin-left: 4px;
    }

    .filters-row {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .search-wrap {
        position: relative;
        display: flex;
        align-items: center;
    }
    .search-icon {
        display: none; /* hidden on desktop */
    }
    .filters-right {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-left: auto;
    }

    /* Bottom controls row (hidden on desktop) */
    .vocab-item-controls {
        display: none;
    }

    /* Mobile ≤1023px */
    @media (max-width: 1023px) {
        /* Practice buttons: icon-only, equal width */
        .practice-row {
            gap: 8px;
            margin-bottom: 10px;
        }
        .practice-btn {
            flex: 1;
            height: 42px;
            padding: 0 6px !important;
            gap: 0;
        }
        .practice-btn-label {
            display: none;
        }

        /* Search row - Library pattern */
        .filters-row {
            flex-wrap: nowrap;
            gap: 8px;
            --row-h: 40px;
        }

        .search-wrap {
            flex: 0 0 var(--row-h);
            height: var(--row-h);
            transition: flex-basis 0.15s ease;
            overflow: hidden;
        }
        .filters-row.search-active .search-wrap {
            flex: 1 1 auto;
        }

        .search-input {
            width: 100%;
            height: var(--row-h);
            min-width: 0;
            padding: 0;
            text-align: center;
            box-sizing: border-box;
            border-radius: 6px;
        }
        .filters-row.search-active .search-input {
            padding: 0 32px 0 10px;
            text-align: left;
        }
        .search-input::placeholder {
            color: transparent;
        }
        .filters-row.search-active .search-input::placeholder {
            color: inherit;
            opacity: 0.5;
        }

        .search-icon {
            display: flex;
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            pointer-events: none;
            font-size: 20px;
            opacity: 0.6;
        }
        .filters-row.search-active .search-icon {
            display: none;
        }

        .clear-search-btn {
            right: 4px;
        }

        /* Filters right */
        .filters-right {
            margin-left: 0;
            gap: 6px;
            flex-shrink: 0;
        }
        .filters-row.search-active .filters-right {
            display: none;
        }

        .lvl-filter {
            width: var(--row-h);
            height: var(--row-h);
            font-size: 0.78rem;
        }

        /* Hide view toggles on mobile */
        .view-toggles {
            display: none;
        }

        /* Vocab item: text area with truncation */
        .vocab-main-row {
            padding: 10px 12px 6px 12px;
            /* align-items: flex-start; */
            display: flex;
            flex-direction: column;
            align-items: stretch;
        }
        .vocab-word-group {
            flex-direction: column;
            gap: 2px;
            min-width: 0;
        }
        .list-audio-btn {
            display: none;
        }
        .word-text {
            font-size: 1rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 100%;
            -webkit-mask-image: linear-gradient(
                to right,
                black 85%,
                transparent 100%
            );
            mask-image: linear-gradient(to right, black 85%, transparent 100%);
        }
        .trans-text {
            font-size: 0.92rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 100%;
            -webkit-mask-image: linear-gradient(
                to right,
                black 85%,
                transparent 100%
            );
            mask-image: linear-gradient(to right, black 85%, transparent 100%);
        }
        /* Hide desktop-side tools */
        .list-tools {
            display: none !important;
        }

        /* Bottom controls: 3 equal-width icon buttons, no borders */
        .vocab-item-controls {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            border-top: 1px solid var(--border);
            margin-top: 8px;
        }
        .vocab-ctrl-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 40px;
            background: none;
            border: none;
            color: var(--on-surface);
            opacity: 0.65;
            cursor: pointer;
            font-size: 20px;
        }
        .vocab-ctrl-btn:active {
            opacity: 1;
        }
        .delete-ctrl {
            color: #d32f2f !important;
            opacity: 0.75;
        }
    }
</style>
