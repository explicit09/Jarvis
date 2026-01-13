const { app, BrowserWindow, ipcMain, Menu, Tray, nativeImage } = require('electron')
const path = require('path')

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
try {
  if (require('electron-squirrel-startup')) {
    app.quit()
  }
} catch (e) {
  // electron-squirrel-startup not installed, ignore
}

let mainWindow = null
let tray = null

// Use dev server only if explicitly set and server is running
const isDev = process.env.ELECTRON_DEV === 'true'

function createWindow() {
  // Create the browser window with Iron Man JARVIS styling
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    frame: false, // Frameless for custom title bar
    transparent: true, // Enable transparency for glass effect
    vibrancy: 'dark', // macOS vibrancy effect
    visualEffectState: 'active',
    backgroundColor: '#00000000',
    titleBarStyle: 'hidden',
    trafficLightPosition: { x: 15, y: 15 },
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
    icon: path.join(__dirname, '../public/icons/icon.png'),
  })

  // Load the app
  if (isDev) {
    // In development, load from Vite dev server
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    // In production, load from built files
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  // Handle window close - minimize to tray instead
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault()
      mainWindow.hide()
    }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  // Window controls via IPC
  ipcMain.on('window-minimize', () => {
    mainWindow?.minimize()
  })

  ipcMain.on('window-maximize', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize()
    } else {
      mainWindow?.maximize()
    }
  })

  ipcMain.on('window-close', () => {
    mainWindow?.hide()
  })

  // Send maximize state changes to renderer
  mainWindow.on('maximize', () => {
    mainWindow?.webContents.send('window-maximized', true)
  })

  mainWindow.on('unmaximize', () => {
    mainWindow?.webContents.send('window-maximized', false)
  })
}

function createTray() {
  // Create tray icon
  const iconPath = path.join(__dirname, '../public/icons/tray-icon.png')
  let icon

  try {
    icon = nativeImage.createFromPath(iconPath)
    if (icon.isEmpty()) {
      // Fallback: create a simple colored icon
      icon = nativeImage.createEmpty()
    }
  } catch {
    icon = nativeImage.createEmpty()
  }

  tray = new Tray(icon.isEmpty() ? nativeImage.createEmpty() : icon)

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show JARVIS',
      click: () => {
        mainWindow?.show()
        mainWindow?.focus()
      },
    },
    {
      label: 'Start Listening',
      click: () => {
        mainWindow?.webContents.send('start-listening')
      },
    },
    { type: 'separator' },
    {
      label: 'Preferences...',
      click: () => {
        mainWindow?.webContents.send('open-preferences')
      },
    },
    { type: 'separator' },
    {
      label: 'Quit JARVIS',
      click: () => {
        app.isQuitting = true
        app.quit()
      },
    },
  ])

  tray.setToolTip('J.A.R.V.I.S')
  tray.setContextMenu(contextMenu)

  // Show window on tray click
  tray.on('click', () => {
    if (mainWindow?.isVisible()) {
      mainWindow.hide()
    } else {
      mainWindow?.show()
      mainWindow?.focus()
    }
  })
}

// Create application menu
function createMenu() {
  const template = [
    {
      label: 'JARVIS',
      submenu: [
        { label: 'About JARVIS', role: 'about' },
        { type: 'separator' },
        {
          label: 'Preferences...',
          accelerator: 'CmdOrCtrl+,',
          click: () => {
            mainWindow?.webContents.send('open-preferences')
          },
        },
        { type: 'separator' },
        { label: 'Hide JARVIS', accelerator: 'CmdOrCtrl+H', role: 'hide' },
        { label: 'Hide Others', accelerator: 'CmdOrCtrl+Shift+H', role: 'hideOthers' },
        { type: 'separator' },
        {
          label: 'Quit JARVIS',
          accelerator: 'CmdOrCtrl+Q',
          click: () => {
            app.isQuitting = true
            app.quit()
          },
        },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { label: 'Undo', accelerator: 'CmdOrCtrl+Z', role: 'undo' },
        { label: 'Redo', accelerator: 'CmdOrCtrl+Shift+Z', role: 'redo' },
        { type: 'separator' },
        { label: 'Cut', accelerator: 'CmdOrCtrl+X', role: 'cut' },
        { label: 'Copy', accelerator: 'CmdOrCtrl+C', role: 'copy' },
        { label: 'Paste', accelerator: 'CmdOrCtrl+V', role: 'paste' },
        { label: 'Select All', accelerator: 'CmdOrCtrl+A', role: 'selectAll' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { label: 'Reload', accelerator: 'CmdOrCtrl+R', role: 'reload' },
        { label: 'Force Reload', accelerator: 'CmdOrCtrl+Shift+R', role: 'forceReload' },
        { type: 'separator' },
        { label: 'Toggle Full Screen', accelerator: 'F11', role: 'togglefullscreen' },
        { type: 'separator' },
        { label: 'Developer Tools', accelerator: 'Alt+CmdOrCtrl+I', role: 'toggleDevTools' },
      ],
    },
    {
      label: 'Voice',
      submenu: [
        {
          label: 'Start Listening',
          accelerator: 'CmdOrCtrl+L',
          click: () => {
            mainWindow?.webContents.send('start-listening')
          },
        },
        {
          label: 'Stop Listening',
          accelerator: 'CmdOrCtrl+Shift+L',
          click: () => {
            mainWindow?.webContents.send('stop-listening')
          },
        },
        { type: 'separator' },
        {
          label: 'Clear Conversation',
          accelerator: 'CmdOrCtrl+K',
          click: () => {
            mainWindow?.webContents.send('clear-conversation')
          },
        },
      ],
    },
    {
      label: 'Window',
      submenu: [
        { label: 'Minimize', accelerator: 'CmdOrCtrl+M', role: 'minimize' },
        { label: 'Zoom', role: 'zoom' },
        { type: 'separator' },
        { label: 'Bring All to Front', role: 'front' },
      ],
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'JARVIS Documentation',
          click: () => {
            require('electron').shell.openExternal('https://github.com/yourname/jarvis')
          },
        },
      ],
    },
  ]

  const menu = Menu.buildFromTemplate(template)
  Menu.setApplicationMenu(menu)
}

// App lifecycle
app.whenReady().then(() => {
  createWindow()
  createTray()
  createMenu()

  app.on('activate', () => {
    // On macOS, re-create a window when dock icon is clicked and no windows exist
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    } else {
      mainWindow?.show()
    }
  })
})

// Quit when all windows are closed, except on macOS
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// Handle before quit
app.on('before-quit', () => {
  app.isQuitting = true
})

// Security: Prevent new window creation
app.on('web-contents-created', (event, contents) => {
  contents.on('new-window', (navigationEvent) => {
    navigationEvent.preventDefault()
  })
})

// IPC handlers for system info
ipcMain.handle('get-platform', () => process.platform)
ipcMain.handle('get-version', () => app.getVersion())
