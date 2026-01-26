<script>
  import { onMount } from "svelte";
  import { Route, router } from "tinro";
  import { fetchUser, isAuthenticated, user } from "./stores/auth";
  import { getUI } from "./lib/ui";
  import Home from "./pages/Home.svelte";
  import Login from "./pages/Login.svelte";
  import Register from "./pages/Register.svelte";
  import Library from "./pages/Library.svelte";
  import View from "./pages/View.svelte";
  import Vocab from "./pages/Vocab.svelte";
  import Speaking from "./pages/Speaking.svelte";
  import Settings from "./pages/Settings.svelte";
  import Navbar from "./components/Navbar.svelte";
  import Toast from "./components/Toast.svelte";
  import ConfirmDialog from "./components/ConfirmDialog.svelte";
  
  onMount(() => {
    fetchUser();
  });

  $: ui = getUI($user?.interface_language || 'ukr');

  // ЗАХИСТ РОУТІВ: Перенаправляє на /login, якщо користувач не в системі
  // і намагається зайти на захищену сторінку.
  $: {
    if (typeof window !== 'undefined') { 
      const publicPages = ['/login', '/register'];
      const isPublicPage = publicPages.includes($router.path);
      
      if (!$isAuthenticated && !isPublicPage) {
        router.goto('/login');
      }
    }
  }

</script>

<Navbar />
<Toast />
<ConfirmDialog />

<div class="container">
  <main>
    <Route path="/"><Home /></Route>
    <Route path="/login"><Login /></Route>
    <Route path="/register"><Register /></Route>
    <Route path="/library"><Library /></Route>
    <Route path="/settings"><Settings /></Route>
    <Route path="/view/:id" let:meta><View id={meta.params.id} /></Route>
    <Route path="/vocab"><Vocab /></Route>
    <Route path="/speaking"><Speaking /></Route>
  </main>
</div>

{#if $isAuthenticated}
<div class="nav-mobile">
  <button type="button" class="nav-item {$router.path === '/' ? 'active' : ''}" onclick={() => router.goto('/')}>
    <span class="material-symbols-outlined">home</span>{ui.main}
  </button>
  <button type="button" class="nav-item {$router.path === '/library' ? 'active' : ''}" onclick={() => router.goto('/library')}>
    <span class="material-symbols-outlined">menu_book</span>{ui.library}
  </button>
  <button type="button" class="nav-item {$router.path === '/speaking' ? 'active' : ''}" onclick={() => router.goto('/speaking')}>
    <span class="material-symbols-outlined">mic</span>{ui.voice}
  </button>
  <button type="button" class="nav-item {$router.path === '/vocab' ? 'active' : ''}" onclick={() => router.goto('/vocab')}>
    <span class="material-symbols-outlined">style</span>{ui.vocab}
  </button>
</div>
{/if}

<style>
  /* Mobile Nav Styles from base.html */
  .nav-mobile { 
    position: fixed; bottom: 0; left: 0; right: 0; 
    background: var(--surface); display: flex; justify-content: space-around; 
    padding: 8px 0; border-top: 1px solid var(--border); 
    box-shadow: 0 -2px 10px rgba(0,0,0,0.05); z-index: 1000; 
  }
  .nav-mobile .nav-item { 
    background: none; border: none; padding: 0; height: auto; width: 100%;
    text-decoration: none; color: var(--on-surface); 
    font-size: 10px; display: flex; flex-direction: column; 
    align-items: center; opacity: 0.7; cursor: pointer;
    outline: none;
    -webkit-tap-highlight-color: transparent;
  }
  .nav-mobile .nav-item.active { 
    color: var(--primary); opacity: 1; 
  }
</style>
