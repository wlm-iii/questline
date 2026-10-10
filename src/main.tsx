import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@dendelion/paper-ui/dist/index.css'
import './index.css'
import './styles/questline.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
