const { app, BrowserWindow, shell, ipcMain, net, Menu, dialog } = require('electron')
const path = require('node:path')
const { pathToFileURL } = require('node:url')
const windowState = require('./windowState')
const { buildMenu } = require('./menu')
const { createTray } = require('./tray')

app.setName('One-AI')

// URL of the running Next.js app (dev server today, production deployment once shipped).
const APP_URL = process.env.ELECTRON_APP_URL || 'http://localhost:3000'
// Desktop apps skip the marketing landing page and open straight into the product
// (like Claude Desktop / Slack) — /login bounces to the dashboard itself if a session
// cookie is already present, per the proxy.ts middleware.
const ENTRY_URL = new URL('/login', APP_URL).toString()
// file:// URLs need forward slashes and proper escaping — building this by hand with
// path.join's backslashes on Windows produces an invalid URL that fails silently.
const CONNECTING_PAGE = pathToFileURL(path.join(__dirname, 'connecting.html')).toString()
const MAX_RETRY_ATTEMPTS = 8
const RETRY_INTERVAL_MS = 1500

// Only one instance of the app should run at a time; a second launch just
// focuses the existing window instead of opening a duplicate.
const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
}

let mainWindow = null
let pollTimer = null
let attempts = 0

function isServerReachable(url) {
  return new Promise((resolve) => {
    const request = net.request({ method: 'HEAD', url })
    request.on('response', () => resolve(true))
    request.on('error', () => resolve(false))
    request.end()
  })
}

async function attemptConnect() {
  clearTimeout(pollTimer)
  attempts += 1

  const reachable = await isServerReachable(APP_URL)
  if (!mainWindow || mainWindow.isDestroyed()) return

  if (reachable) {
    attempts = 0
    mainWindow.loadURL(ENTRY_URL)
    return
  }

  if (attempts >= MAX_RETRY_ATTEMPTS) {
    mainWindow.webContents.send('connection-failed')
    return
  }

  pollTimer = setTimeout(attemptConnect, RETRY_INTERVAL_MS)
}

function createWindow() {
  const state = windowState.load()

  mainWindow = new BrowserWindow({
    ...state,
    title: 'One-AI',
    minWidth: 960,
    minHeight: 640,
    show: false,
    backgroundColor: '#0b0b0e',
    icon: path.join(__dirname, '..', 'build', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  if (state.maximized) mainWindow.maximize()
  windowState.track(mainWindow)

  mainWindow.once('ready-to-show', () => mainWindow.show())

  // Anything that isn't the app itself (OAuth popups, external links) opens in the OS browser instead of a new Electron window.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(APP_URL)) {
      shell.openExternal(url)
      return { action: 'deny' }
    }
    return { action: 'allow' }
  })

  // Security: keep the app window locked to its own origin. Any in-page attempt to
  // navigate elsewhere (a stray link, an OAuth hop) is sent to the system browser
  // instead of loading untrusted content inside the privileged app window.
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith(APP_URL) && !url.startsWith('file://')) {
      event.preventDefault()
      shell.openExternal(url)
    }
  })

  // Native right-click menu — Electron ships none by default, so without this
  // users can't copy/paste via the mouse. Only show actions valid for the target.
  mainWindow.webContents.on('context-menu', (_event, params) => {
    const template = []
    if (params.editFlags.canCut) template.push({ role: 'cut' })
    if (params.editFlags.canCopy) template.push({ role: 'copy' })
    if (params.editFlags.canPaste) template.push({ role: 'paste' })
    if (params.editFlags.canSelectAll) template.push({ role: 'selectAll' })
    if (params.linkURL) {
      if (template.length) template.push({ type: 'separator' })
      template.push({
        label: 'Copy Link Address',
        click: () => require('electron').clipboard.writeText(params.linkURL),
      })
    }
    if (template.length) Menu.buildFromTemplate(template).popup()
  })

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, _desc, validatedURL, isMainFrame) => {
    if (!isMainFrame || errorCode === -3 /* ERR_ABORTED, e.g. a deliberate redirect */) return
    if (validatedURL.startsWith('file://')) return // the connecting page itself failing isn't a server issue
    mainWindow.loadURL(CONNECTING_PAGE).then(() => attemptConnect())
  })

  // A renderer crash shouldn't just leave a blank/frozen window — offer to reload.
  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    if (details.reason === 'clean-exit') return
    dialog.showMessageBox(mainWindow, {
      type: 'error',
      title: 'One-AI has stopped responding',
      message: 'The app ran into a problem and needs to reload.',
      buttons: ['Reload'],
    }).then(() => mainWindow?.loadURL(ENTRY_URL))
  })

  // Closing the window minimizes to tray instead of quitting, like Slack/Discord;
  // the tray menu's Quit (or app.isQuitting from other paths) is the real exit.
  mainWindow.on('close', (event) => {
    if (app.isQuitting) return
    event.preventDefault()
    mainWindow.hide()
  })

  Menu.setApplicationMenu(buildMenu({ getWindow: () => mainWindow, appUrl: ENTRY_URL }))
  createTray(() => mainWindow)

  mainWindow.loadURL(ENTRY_URL)
}

app.on('before-quit', () => {
  app.isQuitting = true
})

ipcMain.on('retry-connection', () => {
  attempts = 0
  attemptConnect()
})

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore()
    if (!mainWindow.isVisible()) mainWindow.show()
    mainWindow.focus()
  }
})

if (gotLock) {
  app.whenReady().then(createWindow)
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})
