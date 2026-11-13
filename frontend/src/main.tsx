import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

// Apply the desktop-first default before React mounts so dark-mode surfaces
// never flash as white while persisted settings are loading.
document.documentElement.classList.add('dark')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
