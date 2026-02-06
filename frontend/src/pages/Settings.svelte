<script>
  import { user } from "../stores/auth";
  import api from "../lib/api";
  import { addToast } from "../stores/toast";
  import { getUI } from "../lib/ui";

  let lang = 'ukr';
  let vocabSize = 20;
  let studyBatchSize = 50;
  let currentPassword = "";
  let newPassword = "";
  let loading = false;
  let interfaceFont = typeof window !== 'undefined' ? localStorage.getItem('interfaceFont') || 'Roboto (default)' : 'Roboto (default)';
  let textFont = typeof window !== 'undefined' ? localStorage.getItem('textFont') || 'Merriweather' : 'Merriweather';

  const fontOptions = [
    'Roboto (default)',
    'Inter',
    'Montserrat',
    'Roboto Flex',
    'Merriweather',
    'Fira Code',
    'JetBrains Mono',
    'Manrope',
    'PT Sans',
    'Exo 2',
    'Lora',
    'Intel One Mono',
    'Cascadia Code',
    'Ubuntu Mono'
  ];
  
  // Map display names to actual font values
  const fontMap = {
    'Roboto (default)': 'Roboto',
    'Inter': 'Inter',
    'Montserrat': 'Montserrat',
    'Roboto Flex': 'Roboto Flex',
    'Merriweather': 'Merriweather',
    'Fira Code': 'Fira Code',
    'JetBrains Mono': 'JetBrains Mono',
    'Manrope': 'Manrope',
    'PT Sans': 'PT Sans',
    'Exo 2': 'Exo 2',
    'Lora': 'Lora',
    'Intel One Mono': 'Intel One Mono',
    'Cascadia Code': 'Cascadia Code',
    'Ubuntu Mono': 'Ubuntu Mono'
  };

  $: ui = getUI($user?.interface_language || 'ukr');

  // Apply fonts to document when they change + save to localStorage
  $: if (interfaceFont) {
    const actualFont = fontMap[interfaceFont] || interfaceFont;
    document.documentElement.style.setProperty('--font-interface', `'${actualFont}'`);
    localStorage.setItem('interfaceFont', interfaceFont);
  }
  
  $: if (textFont) {
    const actualFont = fontMap[textFont] || textFont;
    document.documentElement.style.setProperty('--font-text', `'${actualFont}'`);
    localStorage.setItem('textFont', textFont);
  }

  // Reactive statement to initialize and update local state when user store changes
  $: if ($user) {
    lang = $user.interface_language || 'ukr';
    vocabSize = $user.vocab_session_size || 20;
    studyBatchSize = $user.study_batch_size || 20;
  }

  async function save() {
    loading = true;
    try {
      await api.post("/auth/settings", {
        interface_language: lang,
        vocab_session_size: vocabSize,
        study_batch_size: studyBatchSize
      });
      
      // Оновлюємо локальний стан користувача миттєво
      user.update(u => ({ ...u, interface_language: lang, vocab_session_size: vocabSize, study_batch_size: studyBatchSize }));
      addToast(ui.settings_saved || "Settings saved", "success");
      history.back();
    } catch (e) {
      console.error(e);
      addToast("Error saving settings", "error");
    } finally {
      loading = false;
    }
  }

  async function changePassword() {
    if (!currentPassword || !newPassword) return;
    loading = true;
    try {
      await api.post("/auth/change_password", {
        current_password: currentPassword,
        new_password: newPassword
      });
      addToast("Password changed successfully", "success");
      currentPassword = "";
      newPassword = "";
    } catch (e) {
      addToast(e.response?.data?.detail || "Error changing password", "error");
    } finally {
      loading = false;
    }
  }

  function cancel() {
    history.back();
  }
</script>

<div class="card settings-container">
  <h2>{ui.settings}</h2>
  
  <div class="form-group">
    <label class="form-label" for="lang">{ui.interface_lang}</label>
    <select id="lang" class="form-control" bind:value={lang}>
      <option value="ukr">Українська</option>
      <option value="eng">English</option>
    </select>
  </div>

  <div class="form-group">
    <label class="form-label" for="vss">{ui.vocab_session_size}</label>
    <select id="vss" class="form-control" bind:value={vocabSize}>
      <option value={20}>20</option>
      <option value={50}>50</option>
      <option value={100}>100</option>
    </select>
  </div>

  <div class="form-group">
    <label class="form-label" for="sbs">{ui.study_batch_size}</label>
    <select id="sbs" class="form-control" bind:value={studyBatchSize}>
      <option value={20}>20</option>
      <option value={50}>50</option>
      <option value={100}>100</option>
    </select>
  </div>

  <hr style="margin: 30px 0; border: 0; border-top: 1px solid var(--border);">

  <h3>Font Testing (Тестування шрифтів)</h3>
  
  <div class="form-group">
    <label class="form-label" for="interface-font">Interface & Headings Font</label>
    <select id="interface-font" class="form-control" bind:value={interfaceFont}>
      {#each fontOptions as font}
        <option value={font} selected={interfaceFont === font}>{font}</option>
      {/each}
    </select>
    <div style="margin-top: 8px; padding: 8px; background: rgba(0,0,0,0.02); border-radius: 4px; font-family: {fontMap[interfaceFont] || interfaceFont};">
      ✓ {interfaceFont} - The quick brown fox jumps
    </div>
  </div>

  <div class="form-group">
    <label class="form-label" for="text-font">Text & Words Font</label>
    <select id="text-font" class="form-control" bind:value={textFont}>
      {#each fontOptions as font}
        <option value={font} selected={textFont === font}>{font}</option>
      {/each}
    </select>
    <div style="margin-top: 8px; padding: 8px; background: rgba(0,0,0,0.02); border-radius: 4px; font-family: {fontMap[textFont] || textFont};">
      ✓ {textFont} - Der schnelle Fuchs springt
    </div>
  </div>

  <p style="font-size: 0.9rem; opacity: 0.7; margin-top: 16px;">
    <strong>Примітка:</strong> Вибрані шрифти зберігаються у браузері і застосовуються на всіх сторінках.
    Навіть якщо ви закриєте Settings або оновите сторінку, шрифти залишатимуться сохраненими.
  </p>

  <hr style="margin: 30px 0; border: 0; border-top: 1px solid var(--border);">
  
  <h3>Security</h3>
  <div class="form-group">
    <label class="form-label" for="curr-pass">Current Password</label>
    <input id="curr-pass" type="password" class="form-control" bind:value={currentPassword}>
  </div>
  <div class="form-group">
    <label class="form-label" for="new-pass">New Password</label>
    <input id="new-pass" type="password" class="form-control" bind:value={newPassword}>
  </div>
  <button class="btn-contained" style="background-color: #757575; width: 100%; margin-bottom: 20px;" on:click={changePassword} disabled={loading || !currentPassword || !newPassword}>
    Change Password
  </button>

  <div class="btn-group">
    <button class="btn-contained" on:click={save} disabled={loading}>
      {ui.save_settings}
    </button>
    <button class="btn-outlined" on:click={cancel} disabled={loading}>
      {ui.btn_cancel || 'Cancel'}
    </button>
  </div>
</div>

<style>
  .settings-container { max-width: 500px; margin: 40px auto; padding: 30px; }
  h2 { margin-top: 0; }
  .btn-group { display: flex; gap: 10px; margin-top: 20px; justify-content: flex-end; }
</style>