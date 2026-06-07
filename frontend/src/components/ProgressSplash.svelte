<script>
/* eslint-disable */
  import { onMount } from "svelte";

  export let isVisible = false;
  export let userLanguage = "ukr"; // 'ukr' або 'eng'
  export let apiArrived = false;
  export let textId = null;
  export let userLevel = "B1";

  let progress = 0;
  let currentMessageIndex = 0;
  let startTime = 0;
  let apiArrivalTime = null;

  const getMessages = (level) => ({
    ukr: [
      "Аналізую обрану тему...",
      "Визначаю рівень тексту...",
      "Готую якісний переклад...",
      "Створюю цікавий квіз...",
      "Озвучую німецьку вимову...",
      "Майже готово! Приємного навчання!"
    ],
    eng: [
      "Analyzing the text...",
      "Determining text level...",
      "Preparing quality translation...",
      "Creating an interesting quiz...",
      "Recording German pronunciation...",
      "Almost ready! Enjoy learning!"
    ]
  });

  let messages = getMessages(userLevel);

  $: messages = getMessages(userLevel);

  // Easing функції для плавних переходів
  function easeOutQuad(t) { return t * (2 - t); }
  function easeInQuad(t) { return t * t; }
  function easeInOutQuad(t) { return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; }

  // 7 етапів анімації прогресу
  const stages = [
    { name: 'Ривок', startTime: 0, endTime: 2, startProgress: 0, endProgress: 25, easing: easeOutQuad },
    { name: 'Гальмування', startTime: 2, endTime: 5, startProgress: 25, endProgress: 35, easing: easeInQuad },
    { name: 'Другий ривок', startTime: 5, endTime: 8, startProgress: 35, endProgress: 60, easing: easeOutQuad },
    { name: 'Велика пауза', startTime: 8, endTime: 18, startProgress: 60, endProgress: 80, easing: easeInOutQuad },
    { name: 'Мікро-кроки', startTime: 18, endTime: 22, startProgress: 80, endProgress: 90, easing: easeInQuad },
    { name: 'Передфініш', startTime: 22, endTime: 24, startProgress: 90, endProgress: 98, easing: easeOutQuad },
    { name: 'Завмирання', startTime: 24, endTime: 25, startProgress: 98, endProgress: 100, easing: easeInOutQuad }
  ];

  function calculateProgress(elapsed) {
    if (elapsed >= 25) return 100;
    
    // Знаходимо поточний етап
    for (let stage of stages) {
      if (elapsed >= stage.startTime && elapsed <= stage.endTime) {
        const stageDuration = stage.endTime - stage.startTime;
        const stageElapsed = elapsed - stage.startTime;
        const stageProgress = stageElapsed / stageDuration;
        
        // Застосовуємо easing функцію
        const easedProgress = stage.easing(stageProgress);
        const progressDelta = stage.endProgress - stage.startProgress;
        
        return stage.startProgress + (easedProgress * progressDelta);
      }
    }
    
    return 0;
  }

  function updateProgress() {
    if (!isVisible) return;

    const elapsed = (Date.now() - startTime) / 1000;

    if (apiArrived && !apiArrivalTime) {
      apiArrivalTime = elapsed;
    }

    let effectiveElapsed = elapsed;

    // Якщо API прийшла, негайно прискорюємо до 100%
    if (apiArrivalTime !== null) {
      // Показуємо прогрес на 1 сек після приходу API, потім швидко до 100%
      const timeSinceApi = elapsed - apiArrivalTime;
      if (timeSinceApi < 1) {
        // Перші 1 сек після API: показуємо останнє повідомлення
        effectiveElapsed = 24 + timeSinceApi;
      } else {
        // Після 1 сек: швидко прискорюємо до 100%
        effectiveElapsed = 25 + (timeSinceApi - 1) * 5; // 5x прискорення
      }
    }

    progress = Math.min(100, calculateProgress(effectiveElapsed));

    // Вибираємо повідомлення на основі effectiveElapsed
    const messageMessages = messages[userLanguage];
    const totalMessages = messageMessages.length;
    
    // Розподіляємо 6 повідомлень на 25 секунд рівномірно
    const messageProgress = (effectiveElapsed / 25) * totalMessages;
    currentMessageIndex = Math.min(
      Math.floor(messageProgress),
      totalMessages - 1
    );

    if (progress < 100) {
      requestAnimationFrame(updateProgress);
    } else if (textId) {
      // Перенаправляємо на сторінку тексту
      window.location.href = `/view/${textId}`;
    }
  }

  onMount(() => {
    if (isVisible) {
      startTime = Date.now();
      updateProgress();
    }
  });

  $: if (isVisible && startTime === 0) {
    startTime = Date.now();
    updateProgress();
  }

  // Перенаправляємо як тільки API повернув результат
  $: if (apiArrived && textId) {
    window.location.href = `/view/${textId}`;
  }
</script>

{#if isVisible}
  <div class="splash-overlay">
    <h2 class="splash-title">
      {userLanguage === 'ukr' ? 'Генеруємо урок...' : 'Generating lesson...'}
    </h2>

    <div class="progress-wrapper">
      <div class="progress-container">
        <div class="progress-fill" style="width: {progress}%;"></div>
      </div>
      <div class="progress-text">{Math.round(progress)}%</div>
    </div>
    
    <div class="status-message">
      {messages[userLanguage][currentMessageIndex]}
    </div>
  </div>
{/if}

<style>
  .splash-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.85);
    backdrop-filter: blur(8px);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    color: white;
    gap: 30px;
  }

  .splash-title {
    font-size: 28px;
    font-weight: 600;
    margin: 0;
    color: white;
  }

  .status-message {
    font-size: 18px;
    color: rgba(255, 255, 255, 0.9);
    min-height: 28px;
    transition: opacity 0.3s ease;
    font-weight: 500;
    margin-top: 15px;
  }

  .progress-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 20px;
  }

  .progress-container {
    width: 900px;
    height: 70px;
    background: rgba(255, 255, 255, 0.1);
    overflow: hidden;
    position: relative;
    border: none;
    border-radius: var(--radius);
  }

  .progress-fill {
    height: 100%;
    background: var(--primary);
    position: relative;
    width: 0%;
    transition: width 0.05s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  }

  @keyframes shimmer {
    0% {
      background-position: -200% 0;
    }
    100% {
      background-position: 200% 0;
    }
  }

  .progress-text {
    font-size: 20px;
    font-weight: 600;
    color: white;
    min-width: 60px;
    text-align: right;
  }

  @media (max-width: 1000px) {
    .progress-container {
      width: calc(100% - 40px);
      max-width: 700px;
    }

    .splash-title {
      font-size: 22px;
    }

    .status-message {
      font-size: 16px;
    }
  }

  @media (max-width: 600px) {
    .progress-container {
      width: calc(100% - 30px);
      height: 50px;
    }

    .progress-wrapper {
      flex-direction: column;
      gap: 15px;
    }

    .progress-text {
      font-size: 16px;
    }
  }
</style>
