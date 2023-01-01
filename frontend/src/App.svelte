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

  $: ui = getUI($user?.interface_language || "ukr");

  // ЗАХИСТ РОУТІВ: Перенаправляє на /login, якщо користувач не в системі
  // і намагається зайти на захищену сторінку.
  $: {
    if (typeof window !== "undefined") {
      const publicPages = ["/login", "/register"];
      const isPublicPage = publicPages.includes($router.path);

      if (!$isAuthenticated && !isPublicPage) {
        router.goto("/login");
      }
    }
  }
</script>

<Toast />
<ConfirmDialog />

<!-- Landscape mode restriction overlay for mobile -->
<div id="landscape-overlay">
  <span class="material-symbols-outlined">screen_rotation</span>
  <!-- <p>
    {$user
      ? $user.interface_language === "ukr"
        ? "Будь ласка, поверніть пристрій у вертикальне положення"
        : "Please rotate your device to portrait mode"
      : "Please rotate your device to portrait mode"}
  </p> -->
</div>

<div id="app">
  <Navbar />

  <div class="content-wrapper">
    {#if $isAuthenticated}
      <div class="nav-mobile">
        <div class="nav-logo">
          <button type="button" class="brand" onclick={() => router.goto("/")}>
            <span class="material-symbols-outlined">school</span>
            Gemini <span class="brand-de">DE</span>
          </button>
        </div>
        <button
          type="button"
          class="nav-item {$router.path === '/' ? 'active' : ''}"
          onclick={() => router.goto("/")}
        >
          <span class="material-symbols-outlined">home</span><span
            >{ui.main}</span
          >
        </button>
        <button
          type="button"
          class="nav-item {$router.path === '/library' ? 'active' : ''}"
          onclick={() => router.goto("/library")}
        >
          <span class="material-symbols-outlined">menu_book</span><span
            >{ui.library}</span
          >
        </button>
        <button
          type="button"
          class="nav-item {$router.path === '/speaking' ? 'active' : ''}"
          onclick={() => router.goto("/speaking")}
        >
          <span class="material-symbols-outlined">mic</span><span
            >{ui.voice}</span
          >
        </button>
        <button
          type="button"
          class="nav-item {$router.path === '/vocab' ? 'active' : ''}"
          onclick={() => router.goto("/vocab")}
        >
          <span class="material-symbols-outlined">style</span><span
            >{ui.vocab}</span
          >
        </button>
      </div>
    {/if}

    <main>
      <div class="container">
        <Route path="/"><Home /></Route>
        <Route path="/login"><Login /></Route>
        <Route path="/register"><Register /></Route>
        <Route path="/library"><Library /></Route>
        <Route path="/settings"><Settings /></Route>
        <Route path="/view/:id" let:meta><View id={meta.params.id} /></Route>
        <Route path="/vocab"><Vocab /></Route>
        <Route path="/speaking"><Speaking /></Route>
      </div>
    </main>
  </div>
</div>

<style>
</style>
