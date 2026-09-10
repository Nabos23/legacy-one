const { Tray, Menu, app } = require('electron')
const path = require('node:path')

let tray = null

function createTray(getWindow) {
  tray = new Tray(path.join(__dirname, '..', 'build', 'tray-icon.png'))
  tray.setToolTip('One-AI')

  const showWindow = () => {
    const win = getWindow()
    if (!win) return
    if (win.isMinimized()) win.restore()
    win.show()
    win.focus()
  }

  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Open One-AI', click: showWindow },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.isQuitting = true
        app.quit()
      },
    },
  ]))

  tray.on('click', showWindow)
  return tray
}

module.exports = { createTray }
