const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require("fs");
const dotenv = require("dotenv");




//require('electron-reloader')(module);

let pythonProcess = null;

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

    

   /* const exePath = path.join(__dirname, 'releases', 'main', 'main.exe');

    pythonProcess = spawn(
        "python3",
        ["main.py"],
        {
            cwd: __dirname,
            env: {
                ...process.env,
                PYTHONUNBUFFERED: '1'
            }
        }
    );*/

    //the above code is giving errors with chromadb, I am using the code below to run on the virtual environment
    const pythonPath = path.join(
        __dirname,
        ".venv",
        "Scripts",
        "python.exe"
    );

    pythonProcess = spawn(
        pythonPath,
        [path.join(__dirname, "main.py")],
        {
            cwd: __dirname,
            env: {
                ...process.env,
                PYTHONUNBUFFERED: "1"
            }
        }
    );

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

        // Remove terminal escape codes from Python CLI output
        output = output.replace(
            /\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g,
            ''
        );

        // Collection buttons (numbered list items)
        const matches =
            output.match(/^\s*\d+\.\s+.+$/gm);

        if (matches) {

            const collections = matches.map(line =>
                line.replace(/^\s*\d+\.\s+.+$/gm, '')
            );

            win.webContents.send(
                'summary-output',
                output
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