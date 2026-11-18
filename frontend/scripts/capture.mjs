// Capturas de la aplicacion PUBLICADA para las evidencias (docs/evidencias/capturas).
// Uso: BASE_URL=https://dxxxx.cloudfront.net DEMO_EMAIL=... DEMO_PASSWORD=... node scripts/capture.mjs
// Requiere: npm i --no-save puppeteer-core  y Chrome/Edge instalado.
import fs from 'node:fs'
import path from 'node:path'
import puppeteer from 'puppeteer-core'

const BASE = process.env.BASE_URL
const EMAIL = process.env.DEMO_EMAIL
const PASSWORD = process.env.DEMO_PASSWORD
const OUT = process.env.OUT_DIR || path.resolve('..', 'docs', 'evidencias', 'capturas')
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'
if (!BASE || !EMAIL || !PASSWORD) throw new Error('Faltan BASE_URL, DEMO_EMAIL o DEMO_PASSWORD')
fs.mkdirSync(OUT, { recursive: true })

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--force-prefers-color-scheme=light'] })
const page = await browser.newPage()
await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }])
await page.setViewport({ width: 1280, height: 860, deviceScaleFactor: 1 })

const shot = async (name, opts = {}) => {
  await sleep(opts.wait ?? 800)
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: opts.full ?? true })
  console.log('captura', name)
}
const setValue = (selector, value) =>
  page.evaluate(
    (sel, val) => {
      const el = document.querySelector(sel)
      const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value').set
      setter.call(el, val)
      el.dispatchEvent(new Event('input', { bubbles: true }))
    },
    selector,
    value,
  )
const go = async (route, ready) => {
  await page.goto(BASE + route, { waitUntil: 'networkidle2' })
  if (ready) await page.waitForSelector(ready, { timeout: 60000 })
}
// Espera a que termine una respuesta en streaming del asistente
const chat = async (text) => {
  await page.type('textarea[aria-label="Escribe tu mensaje"]', text)
  await page.keyboard.press('Enter')
  await page.waitForSelector('button[aria-label="Detener"]', { timeout: 30000 })
  await page.waitForSelector('button[aria-label="Enviar"]', { timeout: 280000 })
  await sleep(1200)
}

// ---- Escritorio ----
await go('/login', '#email')
await shot('01-login', { full: false })
await page.type('#email', EMAIL)
await page.type('#password', PASSWORD)
await page.keyboard.press('Enter')
await page.waitForSelector('.hero-card', { timeout: 90000 })
await sleep(2500)
await shot('02-dashboard')

await go('/chat', '.composer')
await page.setViewport({ width: 1280, height: 1500, deviceScaleFactor: 1 })
await chat('¿Me conviene ir en bus o en avión de Medellín a Manizales?')
await shot('03-chat-bus-vs-avion', { full: false })
await page.click('button.btn.btn-sm') // Nueva conversación
await sleep(500)
await chat('Muéstrame mis viajes y mis reservas.')
await shot('04-chat-viajes-y-reservas', { full: false })
await page.setViewport({ width: 1280, height: 860, deviceScaleFactor: 1 })

await go('/trips', 'article.trip-card')
await shot('05-mis-viajes')

// Detalle del viaje que tiene itinerario y reservas
const ids = await page.$$eval('article.trip-card', (cards) => cards.map((c) => (c.innerText.match(/ID ([a-f0-9]{16})/) || [])[1]).filter(Boolean))
let detail = ids[0]
for (const id of ids) {
  await go(`/trips/${id}`, 'h1')
  await sleep(2500)
  if ((await page.$('.agenda-day')) && (await page.$('.res-row'))) { detail = id; break }
}
await go(`/trips/${detail}`, '.agenda-day')
await shot('06-detalle-viaje-itinerario-presupuesto', { wait: 2500 })

await go('/reservations', '.res-row')
await shot('07-reservas-estados')
await go('/wallet', '.wallet-hero')
await sleep(2500)
await shot('08-monedero')

await go('/hotels', '#hc')
await setValue('#hi', '2026-11-20')
await setValue('#ho', '2026-11-23')
await page.click('form button.btn-primary')
await page.waitForSelector('.hotel-card', { timeout: 240000 })
await shot('09-hoteles-tarjetas', { wait: 1500 })

await go('/weather', '#wc')
await setValue('#ws', '2026-11-20')
await setValue('#we', '2026-11-22')
await page.click('form button.btn-primary')
await page.waitForSelector('.wcard', { timeout: 240000 })
await shot('10-clima-tarjetas', { wait: 1500 })

await go('/flights', '#fo')
await shot('11-vuelos-formulario', { full: false })
await go('/preferences', '#pn')
await sleep(1500)
await shot('12-preferencias')

// ---- Movil ----
await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true })
await go('/', '.hero-card')
await sleep(2500)
await shot('m-01-dashboard')
await go('/trips', 'article.trip-card')
await shot('m-02-mis-viajes')
await go('/chat', '.composer')
await shot('m-03-asistente', { full: false })

await browser.close()
console.log('listo ->', OUT)
