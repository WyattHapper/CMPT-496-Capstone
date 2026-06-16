const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

let pythonProcess = null;

ipcMain.on('menu-option', (event, option) => {

    if (pythonProcess) {

        console.log(`Sending option ${option}`);

        pythonProcess.stdin.write(option + '\n');
    }

});

ipcMain.on('exit-app', () => {

    console.log("Exit requested");

    app.quit();

});

function createWindow() {

    const win = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    win.loadFile('index.html');

    const pythonPath = path.join(
        __dirname,
        '.venv',
        'Scripts',
        'python.exe'
    );

    const scriptPath = path.join(
        __dirname,
        'main.py'
    );

    pythonProcess = spawn(
        pythonPath,
        [scriptPath],
        {
            cwd: __dirname
        }
    );

    pythonProcess.stdout.on('data', (data) => {

        const output = data.toString();

        console.log(output); // <-- prints to PowerShell

        win.webContents.send('python-output', output);
    });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {

    if (pythonProcess) {
        pythonProcess.kill();
    }

    if (process.platform !== 'darwin') {
        app.quit();
    }
});