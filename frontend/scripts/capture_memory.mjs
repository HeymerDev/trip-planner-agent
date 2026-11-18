// Evidencia: un navegador LIMPIO (sin localStorage) recupera la conversacion desde la memoria del agente.
import path from 'node:path'
import puppeteer from 'puppeteer-core'
const { BASE_URL: BASE, DEMO_EMAIL: EMAIL, DEMO_PASSWORD: PASSWORD } = process.env
const OUT = path.resolve('..', 'docs', 'evidencias', 'capturas')
const browser = await puppeteer.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: 'new', args: ['--no-sandbox'] })
const page = await browser.newPage()
await page.setViewport({ width: 1280, height: 1100 })
await page.goto(BASE + '/login', { waitUntil: 'networkidle2' })
await page.type('#email', EMAIL)
await page.type('#password', PASSWORD)
await page.keyboard.press('Enter')
await page.waitForSelector('.hero-card', { timeout: 90000 })
console.log('localStorage de chats antes:', await page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith('tp-chats'))))
await page.goto(BASE + '/chat', { waitUntil: 'networkidle2' })
await page.waitForSelector('.msg.user', { timeout: 60000 })
await new Promise((r) => setTimeout(r, 2500))
const texts = await page.$$eval('.msg.user .bubble', (n) => n.map((x) => x.innerText))
const cards = await page.$$eval('.wcard, .card.soft', (n) => n.length)
console.log('mensajes de usuario recuperados:', texts, '| tarjetas:', cards)
await page.screenshot({ path: path.join(OUT, '13-chat-historial-desde-memoria.png') })
await browser.close()
