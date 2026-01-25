<script>
  import { register } from "../stores/auth";
  import { router } from "tinro";

  let email = "";
  let password = "";
  let error = "";

  async function handleSubmit() {
    error = "";
    const res = await register(email, password);
    if (res.ok) {
      router.goto('/login');
    } else {
      error = res.error;
    }
  }
</script>

<div class="card auth-container">
  <div class="auth-header">
    <span class="material-symbols-outlined auth-icon">person_add</span>
    <h2 style="margin: 0; color: var(--primary); font-weight: 500; letter-spacing: 1px;">REGISTER</h2>
  </div>

  {#if error}
    <div class="error-msg">{error}</div>
  {/if}

  <form on:submit|preventDefault={handleSubmit}>
    <div class="form-group">
      <label for="email">Email</label>
      <input type="email" id="email" bind:value={email} class="form-control" placeholder="name@example.com" required>
    </div>
    <div class="form-group">
      <label for="password">Password</label>
      <input type="password" id="password" bind:value={password} class="form-control" placeholder="••••••••" required>
    </div>
    <button type="submit" class="btn-contained" style="width: 100%; margin-top: 10px;">Register</button>
  </form>
  
  <p style="margin-top: 24px; font-size: 0.9rem; opacity: 0.8;">
    Already have an account? <a href="/login" on:click|preventDefault={() => router.goto('/login')} style="color: var(--primary);">Log In</a>
  </p>
</div>

<style>
  .auth-container { max-width: 400px; margin: 60px auto; padding: 40px; text-align: center; }
  .auth-header { margin-bottom: 30px; }
  .auth-icon { font-size: 48px; color: var(--primary); margin-bottom: 10px; }
  .form-group { margin-bottom: 20px; text-align: left; }
  .form-control { width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg); color: var(--on-surface); font-size: 16px; box-sizing: border-box; }
  .btn-contained { background: var(--primary); color: var(--on-primary); border: none; height: 48px; font-size: 1rem; font-weight: 500; text-transform: uppercase; border-radius: var(--radius); cursor: pointer; }
  .error-msg { background: #ffebee; color: #c62828; padding: 10px; border-radius: 4px; margin-bottom: 20px; font-size: 0.9rem; }
</style>