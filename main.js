const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require("fs");
const dotenv = require("dotenv");





//require('electron-reloader')(module);

let pythonProcess = null;
let inPreview = false;
let activeCollectionMode = null;
let collectionOutputActive = false;
let collectionBuffer = '';

ipcMain.on('menu-option', (event, option) => {

    if (!pythonProcess) {
        console.log("Python process is null!");
        return;
    }

    console.log("Sending option:", option);
   
    pythonProcess.stdin.write(option + '\n');

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

    

    const backendDir = app.isPackaged
        ? path.join(process.resourcesPath, "backend")
        : path.join(__dirname, "releases", "main");

    const isWindows = process.platform === "win32";
    const executableName = isWindows ? "main.exe" : "main";
    const exePath = path.join(backendDir, executableName);

    const outputDir = app.isPackaged
        ? app.getPath("userData")
        : backendDir;

    console.log("Backend directory:", backendDir);
    console.log("Output directory:", outputDir);

    const exeExists = fs.existsSync(exePath);

    if (exeExists) {
        console.log("Launching packaged executable:", exePath);

        pythonProcess = spawn(exePath, [outputDir], {
            cwd: backendDir
        });
    } else {
        console.log("Executable not found, falling back to Python script");

        const pythonPath = isWindows
            ? path.join(__dirname, ".venv", "Scripts", "python.exe")
            : "python3";

        const scriptPath = path.join(__dirname, "main.py");

        pythonProcess = spawn(
            pythonPath,
            ["-u", scriptPath, outputDir],
            {
                cwd: __dirname,
                env: {
                    ...process.env,
                    PYTHONUNBUFFERED: "1"
                }
            }
        );
    }

    pythonProcess.on("error", (err) => {
        console.error("Failed to start backend:", err);
    });

    pythonProcess.on("close", (code) => {
        console.log("Backend exited with code:", code);
    });

    // Debug logging
    pythonProcess.stdout.on("data", (data) => {
        console.log("STDOUT:");
        console.log(data.toString());
    });

    pythonProcess.stderr.on("data", (data) => {
        console.error("STDERR:");
        console.error(data.toString());
    });

    pythonProcess.on("error", (err) => {
        console.error("Failed to start Python:");
        console.error(err);
    });

    pythonProcess.on("close", (code) => {
        console.log("Python exited with code:", code);
    });


    //this code below is used to point to main.js
    /*const os = require("os");

    const pythonPath =
        os.platform() === "win32"
            ? path.join(__dirname, ".venv", "Scripts", "python.exe")
            : path.join(__dirname, ".venv", "bin", "python");

    const scriptPath = path.join(__dirname, "main.py");

    pythonProcess = spawn(
        pythonPath,
        [scriptPath],
        {
            cwd: __dirname,
            env: {
                ...process.env,
                PYTHONUNBUFFERED: "1"
            }
        }
    );*/

   


    pythonProcess.stdout.on('data', (data) => {

        let output = data.toString();

        output = output.replace(
            /\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g,
            ''
        );
        output = output.replace(/\x00|\u0000/g, '');

        // Error page
        if (
            output.includes("--- ERROR LOG ---") ||
            output.includes("[ERROR")
        ) {
            console.log("Sending error-output:");
            console.log(output);

            win.webContents.send("error-output", output);
            return;
        }

        if (output.includes('PREVIEWING:')) {
            inPreview = true;
        }

        if (inPreview) {
            const channel = activeCollectionMode === 'source'
                ? 'source-selection-output'
                : 'summary-selection-output';

            win.webContents.send(channel, output);

            if (
                output.includes('Press Enter') ||
                output.includes('Select an option') ||
                output.includes('Select a number to preview')
            ) {
                inPreview = false;
                activeCollectionMode = null;
            }

            return;
        }

        if (collectionOutputActive) {
            collectionBuffer += output;

            const hasListItems = /^\s*\d+\.\s+/m.test(collectionBuffer);
            const hasSelectionPrompt = /Select a number to preview|Select an option|Press Enter/i.test(collectionBuffer);

            if (hasListItems || hasSelectionPrompt) {
                const channel = activeCollectionMode === 'source'
                    ? 'source-output'
                    : 'summary-output';

                win.webContents.send(channel, collectionBuffer);
                collectionBuffer = '';
                collectionOutputActive = false;
            }

            return;
        }

        if (output.includes('Available Summary Collections')) {
            activeCollectionMode = 'summary';
            collectionOutputActive = true;
            collectionBuffer = output;
            return;
        }

        if (output.includes('Available Code Collections')) {
            activeCollectionMode = 'source';
            collectionOutputActive = true;
            collectionBuffer = output;
            return;
        }

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