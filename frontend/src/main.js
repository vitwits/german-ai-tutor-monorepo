import { mount } from 'svelte'
import './app.css'
import App from './App.svelte'
import { registerSW } from 'virtual:pwa-register'

// Load saved fonts from localStorage and apply them immediately
function initializeSavedFonts() {
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
  
  const savedInterfaceFont = localStorage.getItem('interfaceFont');
  const savedTextFont = localStorage.getItem('textFont');
  
  if (savedInterfaceFont) {
    const actualFont = fontMap[savedInterfaceFont] || savedInterfaceFont;
    document.documentElement.style.setProperty('--font-interface', `'${actualFont}'`);
  }
  
  if (savedTextFont) {
    const actualFont = fontMap[savedTextFont] || savedTextFont;
    document.documentElement.style.setProperty('--font-text', `'${actualFont}'`);
  }
}

// Initialize fonts before mounting the app
initializeSavedFonts();

registerSW({
  immediate: true
})

const app = mount(App, {
  target: document.getElementById('app'),
})

export default app
