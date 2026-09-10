const fs = require('node:fs')
const path = require('node:path')
const { app, screen } = require('electron')

const STATE_FILE = path.join(app.getPath('userData'), 'window-state.json')
const DEFAULTS = { width: 1440, height: 900 }

function load() {
  try {
    const saved = JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'))
    // Discard bounds that no longer fit any connected display (e.g. monitor unplugged).
    const onScreen = screen.getAllDisplays().some(({ workArea }) =>
      saved.x >= workArea.x &&
      saved.y >= workArea.y &&
      saved.x + saved.width <= workArea.x + workArea.width &&
      saved.y + saved.height <= workArea.y + workArea.height
    )
    return onScreen ? saved : { ...DEFAULTS }
  } catch {
    return { ...DEFAULTS }
  }
}

function track(win) {
  const persist = () => {
    if (win.isDestroyed()) return
    const bounds = win.isMaximized() ? win.getNormalBounds() : win.getBounds()
    fs.writeFileSync(STATE_FILE, JSON.stringify({ ...bounds, maximized: win.isMaximized() }))
  }
  win.on('resize', persist)
  win.on('move', persist)
  win.on('close', persist)
}

module.exports = { load, track }
