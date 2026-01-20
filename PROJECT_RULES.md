Ось повний оновлений текст файлу `PROJECT_RULES.md`. Збережи його в корені проекту.

```markdown
# 🏗 PROJECT ARCHITECTURE & RULES (German AI Tutor) v2.0

## 🎯 Core Philosophy
This is a **Hybrid Mobile App** built with **Flask + HTMX**, wrapped in **Capacitor**.
- **SPA Experience:** The user must NEVER experience a full page reload. Use `hx-boost="true"` in `base.html`.
- **Server-Driven UI:** Logic resides in Python, state is reflected via HTML Partials.
- **Mobile-First:** All click targets must be touch-friendly (min 44px).

## 🤖 AI Model Strategy (CRITICAL)
We use a **Hybrid Routing** strategy to balance speed vs intelligence:
1.  **TEXT Tasks (Lessons, Vocab, Translation):** Use `gemini-2.5-flash-lite`. (Better JSON adherence, instant for text).
2.  **AUDIO Tasks (Speaking Evaluation):** Use `gemini-2.0-flash`. (Must be <2s latency. Do NOT use 2.5-lite for audio).

## 🚫 STRICT PROHIBITIONS (Do Not Do)
1.  **NO `window.location.href`:** Never use JS redirects. Use `HX-Redirect` header or HTMX swapping.
2.  **NO `onclick` for Data Mutation:** Do not use `fetch()` inside `onclick` to delete/update data. Use `hx-post`, `hx-delete`.
    * *Exception:* You MAY use vanilla JS `onclick` for **Audio Playback (TTS)** and **UI Modals/Toasts**.
3.  **NO Logic in Templates:** Do not put complex logic in Jinja2. Pre-calculate in `app.py`.
4.  **NO jQuery:** Use Vanilla JS only.

## 📂 File Structure Rules
-   **`app.py`:** Must distinguish between full page loads and HTMX requests.
    -   IF `HX-Request` header exists -> Return `render_template('partials/...')`
    -   ELSE -> Return `render_template('full_page.html', ...)`
-   **`templates/partials/`:** All dynamic content (lists, cards, results) MUST live here.
-   **`static/js/`:** Only for native APIs (AudioContext, MediaRecorder, ToastService).

## 🛠 Coding Patterns

### 1. Navigation (SPA Mode)
Use standard links. `hx-boost` in `base.html` handles the rest.
GOOD: `<a href="/vocab">Vocabulary</a>`

### 2. Deleting/Updating Items
BAD: `onclick="deleteItem(id)"`
GOOD: 
```html
<button hx-post="/api/delete_item" 
        hx-vals='{"id": "123"}' 
        hx-target="closest .card" 
        hx-swap="outerHTML">
    Delete
</button>

```

### 3. Audio & TTS (JS Exception)

For TTS, use the global `playAudio()` function in JS, not HTMX (to avoid re-rendering DOM during playback).
GOOD: `<button onclick="playAudio('Hello', this)">Play</button>`

### 4. Feedback (Toasts)

Use the global `window.toast` service.

* **Client-side:** `window.toast.show('Done', 'success')`
* **Server-side (HTMX):** Return header `HX-Trigger: {"showMessage": "Saved"}` (Handle in main.js).

```

```