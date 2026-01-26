<script>
  import { user } from "../stores/auth";
  import api from "../lib/api";
  import { addToast } from "../stores/toast";
  import { getUI } from "../lib/ui";

  let lang = $user?.interface_language || 'ukr';
  let vocabSize = $user?.vocab_session_size || 20;
  let loading = false;

  $: ui = getUI($user?.interface_language || 'ukr');

  async function save() {
    loading = true;
    try {
      await api.post("/auth/settings", {
        interface_language: lang,
        vocab_session_size: vocabSize
      });
      
      // Оновлюємо локальний стан користувача миттєво
      user.update(u => ({ ...u, interface_language: lang, vocab_session_size: vocabSize }));
      addToast(ui.settings_saved || "Settings saved", "success");
    } catch (e) {
      console.error(e);
      addToast("Error saving settings", "error");
    } finally {
      loading = false;
    }
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
    <input id="vss" type="number" class="form-control" bind:value={vocabSize} min="5" max="100">
  </div>

  <button class="btn-contained" onclick={save} disabled={loading}>
    {ui.save_settings}
  </button>
</div>

<style>
  .settings-container { max-width: 500px; margin: 40px auto; padding: 30px; }
</style>