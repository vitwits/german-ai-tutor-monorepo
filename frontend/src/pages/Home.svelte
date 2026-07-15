<script>
    /* eslint-disable */
    import { user } from "../stores/auth";
    import { confirmModal } from "../stores/confirm";
    import api from "../lib/api";
    import { router } from "tinro";
    import { getUI } from "../lib/ui";
    import ProgressSplash from "../components/ProgressSplash.svelte";

    let topic = "";
    let customText = "";
    let mode = "topic"; // 'topic' або 'text'
    let style = "neutral";
    let size = "M";
    let loading = false;
    let showSplash = false;
    let generatedTextId = null;
    let apiArrived = false;

    $: ui = getUI($user?.interface_language || "ukr");

    // Функція для нормалізації тексту - видалення переносів, абзаців, зайвих пробілів
    function normalizeText(text) {
        return text
            .replace(/[\n\r]+/g, " ") // Замінюємо переноси та абзаци на пробіл
            .replace(/\s+/g, " ") // Замінюємо кілька пробілів на один
            .trim(); // Видалемо пробіли на початку і в кінці
    }

    // Функція для очищення тексту від невалідних символів перед відправкою
    function cleanText(text) {
        // Видалити символи, що не є німецькими, англійськими, цифрами, пунктуацією або пробілами
        // Дозволяємо: a-z, A-Z, 0-9, німецькі умлаути (äöüÄÖÜß), пунктуацію, пробіли
        const regex = new RegExp(
            '[^\\w\\säöüÄÖÜß.,!?;:„"«»‚\'„"()\\[\\]{}/\\\\&@#*+=-]',
            "g",
        );
        return text
            .replace(regex, "")
            .replace(/\s+/g, " ") // Стискаємо множинні пробіли
            .trim();
    }

    // Функція для обрізки тексту на 15000 символів на межі речення
    function trimToSentence(text) {
        if (text.length <= 15000) return text;

        // Беремо перші 15000 символів
        let trimmed = text.substring(0, 15000);

        // Шукаємо останню пунктуацію (. ! ? ;) у обрізаному тексті
        const lastPunctIndex = Math.max(
            trimmed.lastIndexOf("."),
            trimmed.lastIndexOf("!"),
            trimmed.lastIndexOf("?"),
            trimmed.lastIndexOf(";"),
        );

        if (lastPunctIndex > -1) {
            return trimmed.substring(0, lastPunctIndex + 1);
        }

        return trimmed;
    }

    async function handleSubmit() {
        if (!$user) {
            router.goto("/login");
            return;
        }

        // Validate input
        if (
            mode === "text" &&
            (!customText || customText.trim().length === 0)
        ) {
            alert(ui.error_empty_text || "Text is required");
            return;
        }

        if (mode === "topic" && (!topic || topic.trim().length === 0)) {
            alert("Topic is required");
            return;
        }

        loading = true;
        showSplash = true;
        apiArrived = false;
        generatedTextId = null;

        try {
            let endpoint, payload;

            if (mode === "text") {
                // Normalize and clean the text ONLY when submitting
                // This prevents interference with user typing (especially with spaces)
                let normalized = normalizeText(customText);
                // Remove non-German/non-standard characters
                normalized = cleanText(normalized);
                const trimmed = trimToSentence(normalized);

                endpoint = "create_own_text";
                payload = {
                    text: trimmed,
                };
            } else {
                // Use standard generate endpoint for topic-based generation
                endpoint = "generate";
                payload = {
                    topic: topic,
                    level: $user.level,
                    style,
                    size,
                };
            }

            const res = await api.post(endpoint, payload);

            if (res.data.id) {
                generatedTextId = res.data.id;
                apiArrived = true;
                // Splash екран автоматично перенаправить на /view/{id}
            }
        } catch (e) {
            console.error("Error:", e);
            console.error("Response data:", e.response?.data);
            showSplash = false;
            loading = false;

            // Handle validation errors
            const errorData = e.response?.data;
            const errorKey =
                errorData?.detail?.error_key || errorData?.error_key;

            if (errorKey && ui[errorKey]) {
                confirmModal.ask(
                    ui.validation_error_title || "Error",
                    ui[errorKey],
                    ui.validation_error_close || "Close",
                    null,
                );
            } else {
                confirmModal.ask(
                    "Error",
                    "Error: " + (errorData?.detail || e.message),
                    ui.validation_error_close || "Close",
                    null, // Без Cancel кнопки
                );
            }
        }
    }
</script>

<form
    class="card form-container"
    onsubmit={(e) => {
        e.preventDefault();
        handleSubmit();
    }}
>
    <div class="header-section">
        <span class="material-symbols-outlined header-icon">auto_stories</span>
        <h2
            style="margin: 0; color: var(--primary); font-weight: 500; letter-spacing: 1px;"
        >
            {ui.generate_new}
        </h2>
    </div>

    <!-- Mode Toggle Switch -->
    <div class="mode-toggle">
        <button
            type="button"
            class="toggle-btn"
            class:active={mode === "topic"}
            onclick={() => (mode = "topic")}
            disabled={loading}
        >
            {ui.choose_topic}
        </button>
        <button
            type="button"
            class="toggle-btn"
            class:active={mode === "text"}
            onclick={() => (mode = "text")}
            disabled={loading}
        >
            {ui.your_text}
        </button>
    </div>

    <!-- Topic Mode -->
    {#if mode === "topic"}
        <div class="form-group">
            <label class="form-label" for="topic">{ui.topic}</label>
            <!-- svelte-ignore a11y-autofocus -->
            <input
                type="text"
                id="topic"
                bind:value={topic}
                class="form-control control-height"
                placeholder={ui.topic_placeholder}
                required
                autofocus
                disabled={loading}
            />
        </div>

        <div class="controls-row">
            <div class="form-group" style="flex: 1;">
                <label class="form-label" for="style">{ui.style_label}</label>
                <select
                    id="style"
                    bind:value={style}
                    class="form-control control-height"
                    disabled={loading}
                >
                    <option value="neutral">{ui.style_neutral}</option>
                    <option value="formal">{ui.style_formal}</option>
                    <option value="conversational"
                        >{ui.style_conversational}</option
                    >
                    <option value="dialogue_informal"
                        >{ui.style_dialogue_informal}</option
                    >
                    <option value="dialogue_formal"
                        >{ui.style_dialogue_formal}</option
                    >
                </select>
            </div>
            <div class="form-group">
                <span class="form-label">{ui.count}</span>
                <div class="size-selector">
                    {#each ["S", "M", "L"] as s}
                        <button
                            type="button"
                            class:active={size === s}
                            onclick={() => (size = s)}
                            disabled={loading}>{s}</button
                        >
                    {/each}
                </div>
            </div>
        </div>

        <button
            type="submit"
            class="btn-contained"
            style="width: 100%; height: 50px; justify-content: center; font-size: 1rem; margin-top: 20px;"
            disabled={loading}
        >
            {#if loading}
                <span class="material-symbols-outlined rotating">sync</span>
                {ui.generating}
            {:else}
                <span class="material-symbols-outlined">auto_awesome</span>
                {ui.generate_btn}
            {/if}
        </button>
    {/if}

    <!-- Text Mode -->
    {#if mode === "text"}
        <div class="form-group">
            <label class="form-label" for="customText"
                >{ui.your_german_text}</label
            >
            <p class="hint-text">
                💡 {ui.use_your_german_text}
            </p>
            <textarea
                id="customText"
                bind:value={customText}
                class="form-control text-input"
                placeholder={ui.use_your_german_text}
                disabled={loading}
                rows="10"
            ></textarea>
            <div class="char-count">
                {customText.length} / 15000
            </div>
        </div>

        <button
            type="submit"
            class="btn-contained"
            style="width: 100%; height: 50px; justify-content: center; font-size: 1rem; margin-top: 20px;"
            disabled={loading}
        >
            {#if loading}
                <span class="material-symbols-outlined rotating">sync</span>
                {ui.generating}
            {:else}
                <span class="material-symbols-outlined">check_circle</span>
                {ui.create_btn}
            {/if}
        </button>
    {/if}
</form>

<ProgressSplash
    isVisible={showSplash}
    userLanguage={$user?.interface_language || "ukr"}
    {apiArrived}
    textId={generatedTextId}
    userLevel={$user?.level || "B1"}
/>

<style>
    .form-container {
        max-width: 500px;
        margin: 40px auto;
        padding: 40px;
        text-align: center;
    }
    .header-section {
        margin-bottom: 30px;
    }
    .header-icon {
        font-size: 48px;
        color: var(--primary);
        margin-bottom: 10px;
    }

    /* Mode Toggle Styles */
    .mode-toggle {
        display: flex;
        gap: 0;
        margin-bottom: 30px;
        border-radius: var(--radius);
        overflow: hidden;
        border: 1px solid var(--border);
        height: 50px;
    }

    .toggle-btn {
        flex: 1;
        border: none;
        background: var(--bg);
        color: var(--on-surface);
        cursor: pointer;
        font-weight: 500;
        font-size: 0.95rem;
        transition: all 0.2s ease;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
    }

    .toggle-btn:first-child {
        border-radius: var(--radius) 0 0 var(--radius);
    }

    .toggle-btn:last-child {
        border-radius: 0 var(--radius) var(--radius) 0;
    }

    .toggle-btn.active {
        background: var(--primary);
        color: var(--on-primary);
    }

    .toggle-btn.active:hover:not(:disabled) {
        background: var(--primary);
        color: var(--on-primary);
    }

    .toggle-btn:not(.active):hover:not(:disabled) {
        background: var(--surface);
        color: var(--on-surface);
    }

    .toggle-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }

    .controls-row {
        display: flex;
        align-items: flex-end;
        gap: 20px;
    }

    /* Size Selector Styles matching original */
    .size-selector {
        display: flex;
        gap: 8px;
    }
    .size-selector button {
        width: 45px;
        height: 45px;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        background: var(--bg);
        color: var(--on-surface);
        cursor: pointer;
        font-weight: 500;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        transition: all 0.2s;
    }
    .size-selector button.active {
        background: var(--primary);
        color: white;
        border-color: var(--primary);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    .size-selector button:hover {
        border-color: var(--primary);
    }

    /* Textarea styles for custom text mode */
    .text-input {
        resize: vertical;
        min-height: 150px;
        font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        line-height: 1.5;
        padding: 12px !important;
    }

    .text-input:focus {
        min-height: 150px;
    }

    .char-count {
        text-align: right;
        font-size: 0.85rem;
        color: var(--on-surface-dim);
        margin-top: 8px;
        font-weight: 500;
    }

    .hint-text {
        font-size: 0.85rem;
        color: var(--on-surface-dim);
        margin-bottom: 10px;
    }

    .rotating {
        animation: rotate 1.5s linear infinite;
        margin-right: 8px;
    }
    @keyframes rotate {
        from {
            transform: rotate(0deg);
        }
        to {
            transform: rotate(-360deg);
        }
    }

    .btn-contained:disabled {
        opacity: 0.7;
        cursor: not-allowed;
    }

    /*
     * Mobile (< 1024px, minimum tested size iPhone X 375x812):
     * shrink the card padding/icon, keep the topic toggle on one line,
     * and stack the style select + sentence count so the select never
     * gets squeezed and truncated.
     */
    @media (max-width: 1023px) {
        .form-container {
            max-width: 100%;
            margin: 0 auto;
            padding: 20px 16px;
        }

        .header-icon {
            font-size: 40px;
            margin-bottom: 8px;
        }

        .header-section {
            margin-bottom: 20px;
        }

        .header-section h2 {
            font-size: 1.35rem !important;
        }

        .mode-toggle {
            margin-bottom: 20px;
            height: 50px;
        }

        .toggle-btn {
            font-size: 0.85rem;
            white-space: nowrap;
            padding: 0 4px;
        }

        .controls-row {
            flex-direction: column;
            align-items: stretch;
            gap: 16px;
        }

        .size-selector {
            justify-content: space-between;
        }

        .size-selector button {
            flex: 1;
            width: auto;
            height: 50px;
            font-size: 1.05rem;
        }

        .hint-text {
            font-size: 0.95rem;
        }

        .char-count {
            font-size: 0.9rem;
        }

        .text-input {
            font-size: 1rem;
        }

        button[type="submit"] {
            height: 54px !important;
            font-size: 1.05rem !important;
        }
    }
</style>
