

const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

//require('electron-reloader')(module);

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

ipcMain.on('codebase-path', (event, path) => {

    console.log("Path received:", path);

    if (!pythonProcess) {
        console.log("Python process is null!");
        return;
    }

    console.log("Sending path to Python");

    pythonProcess.stdin.write(path + '\n');

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

    

    const os = require('os');
    const path = require('path');

    // Dynamically picks the correct folder structure for Mac vs Windows
    const pythonPath = os.platform() === 'win32' 
    ? path.join(__dirname, '.venv', 'Scripts', 'python.exe')
    : path.join(__dirname, '.venv', 'bin', 'python');

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

    //add code for outputs to be shown

    pythonProcess.stdout.on('data', (data) => {

        const output = data.toString();

        console.log(output);

        if (
            output.includes('CODEBASE ANALYSIS SYSTEM') ||
            output.includes('Run Analysis Tools') ||
            output.includes('View Summary Collections') ||
            output.includes('View Source Code Collections') ||
            output.includes('View Errors') ||
            output.includes('Select an option')
        ) {
            return;
        }

        win.webContents.send(
            'python-output',
            output
        );
    });

    pythonProcess.stderr.on('data', (data) => {

        const text = data.toString();

        win.webContents.send(
            'python-output',
            text
        );

    });

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