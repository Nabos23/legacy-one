const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('desktop', {
  isElectron: true,
  retryConnection: () => ipcRenderer.send('retry-connection'),
  onConnectionFailed: (callback) => ipcRenderer.on('connection-failed', () => callback()),
})
