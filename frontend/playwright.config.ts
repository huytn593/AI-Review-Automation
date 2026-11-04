import {defineConfig} from '@playwright/test'
import {existsSync,mkdtempSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {join,resolve} from 'node:path'

const venvPython=resolve(__dirname,'..','.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python')
const python=process.env.STUDIO_PYTHON||(existsSync(venvPython)?venvPython:'python')

export default defineConfig({
  timeout:120000,
  use:{baseURL:'http://127.0.0.1:8012',reducedMotion:'reduce',channel:process.env.STUDIO_CHROMIUM?undefined:process.env.STUDIO_CHANNEL||(process.platform==='win32'?'chrome':undefined),headless:process.env.STUDIO_HEADED!=='1',trace:'retain-on-failure',screenshot:'only-on-failure',launchOptions:{executablePath:process.env.STUDIO_CHROMIUM}},
  webServer:{
    command:`npm --prefix frontend run build && "${python}" -m uvicorn factory.app:app --host 127.0.0.1 --port 8012`,
    cwd:'..',
    url:'http://127.0.0.1:8012/health',
    env:{VITE_MOTION_DEBUG:'1',FACTORY_DATA:mkdtempSync(join(tmpdir(),'review-studio-')),FACTORY_VOICE:'mock',OLLAMA_MODEL:''},
  },
})
