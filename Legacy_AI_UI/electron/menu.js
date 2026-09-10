const { app, Menu, shell, dialog } = require('electron')

const isMac = process.platform === 'darwin'

function showAbout() {
  dialog.showMessageBox({
    type: 'info',
    title: 'About One-AI',
    message: 'One-AI',
    detail: `Version ${app.getVersion()}\nElectron ${process.versions.electron}\nNode ${process.versions.node}`,
    buttons: ['OK'],
  })
}

function buildMenu({ getWindow, appUrl }) {
  const template = [
    ...(isMac ? [{
      label: app.name,
      submenu: [
        { label: 'About One-AI', click: showAbout },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' },
      ],
    }] : [{
      label: 'File',
      submenu: [
        { role: 'quit', label: 'Quit' },
      ],
    }]),
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' }, { role: 'redo' }, { type: 'separator' },
        { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' },
      ],
    },
    {
      label: 'View',
      submenu: [
        {
          label: 'Reload',
          accelerator: 'CmdOrCtrl+R',
          click: () => getWindow()?.loadURL(appUrl),
        },
        {
          label: 'Toggle Developer Tools',
          accelerator: isMac ? 'Cmd+Alt+I' : 'Ctrl+Shift+I',
          click: () => getWindow()?.webContents.toggleDevTools(),
        },
        { type: 'separator' },
        { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'zoom' },
        ...(isMac ? [{ type: 'separator' }, { role: 'front' }] : [{ role: 'close' }]),
      ],
    },
    {
      role: 'help',
      submenu: [
        ...(isMac ? [] : [{ label: 'About One-AI', click: showAbout }]),
        {
          label: 'Report an Issue',
          click: () => shell.openExternal('https://github.com/Allied-Intelligenza'),
        },
      ],
    },
  ]

  return Menu.buildFromTemplate(template)
}

module.exports = { buildMenu }
