const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require("fs");
const dotenv = require("dotenv");


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

ipcMain.on('send-enter', () => {
    if (!pythonProcess) {
        console.log("Python process is null!");
        return;
    }

    console.log("Sending Enter to Python");
    pythonProcess.stdin.write('\n');
});

ipcMain.on("api-key", (event, apiKey) => {

    if (!pythonProcess) {
        console.log("Python process is null!");
        return;
    }
    console.log("Received API key:", apiKey);
    pythonProcess.stdin.write(apiKey + '\n');


});

function hasAPIKey() {
    const envPaths = [
        path.join(__dirname, ".env"),
        path.join(__dirname, 'releases', 'main', ".env")
    ];

    for (const envPath of envPaths) {
        if (!fs.existsSync(envPath)) continue;

        const env = dotenv.parse(fs.readFileSync(envPath));

        if (
            typeof env.GOOGLE_API_KEY !== "undefined" &&
            env.GOOGLE_API_KEY.trim() !== ""
        ) {
            return true;
        }
    }

    return false;
}

ipcMain.handle("has-api-key", () => {
    return hasAPIKey();
});

function createWindow() {

    const win = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            preload: path.join(__dirname, "preload.js"), //added for the preload.js file to work
            nodeIntegration: false, 
            contextIsolation: true
        }
    });

    

    win.loadFile('index.html');

    

    const exePath = path.join(__dirname, 'releases', 'main', 'main.exe');

    pythonProcess = spawn(
        exePath,
        [],
        {
            cwd: __dirname,
            env: {
                ...process.env,
                PYTHONUNBUFFERED: '1'
            }
        }
    );

    //add code for outputs to be shown

    /*pythonProcess.stdout.on('data', (data) => {

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
    });*/

    /*pythonProcess.stdout.on('data', (data) => {

        let output = data.toString();

        output = output.replace(
            /={10,}[\s\S]*?Select an option.*?:/g,
            ''
        );

        if (output.trim()) {
            win.webContents.send(
                'python-output',
                output
            );
        }
    });

    pythonProcess.stdout.on('data', (data) => {

        const output = data.toString();

        if (output.includes('PREVIEWING:')) {

            win.webContents.send(
                'collection-preview',
                output
            );

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

        //win.webContents.send('python-output', output);
    });

    //this is used to extract the output from the source collections page and turn them into buttons
    pythonProcess.stdout.on('data', (data) => {

        const output = data.toString();

        const matches =
            output.match(/^\d+\.\s+.+$/gm);

        if (matches) {

            const collections = matches.map(line =>
                line.replace(/^\d+\.\s+/, '')
            );

            win.webContents.send(
                'collections-list',
                collections
            );

            return;
        }

        win.webContents.send(
            'python-output',
            output
        );

    });*/

    pythonProcess.stdout.on('data', (data) => {

       let output = data.toString();

        // Remove terminal escape codes from Python CLI output
        output = output.replace(
            /\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g,
            ''
        );

        // Collection buttons
        const matches =
            output.match(/^\d+\.\s+.+$/gm);

        if (matches) {

            const collections = matches.map(line =>
                line.replace(/^\d+\.\s+/, '')
            );

            win.webContents.send(
                'collections-list',
                collections
            );

            return;
        }

        // Collection preview
        if (output.includes('PREVIEWING:')) {

            win.webContents.send(
                'collection-preview',
                output
            );

            return;
        }

        // Ignore menu text
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

        // Normal output
        win.webContents.send(
            'python-output',
            output
        );

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