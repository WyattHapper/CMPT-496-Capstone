const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require("fs");
const dotenv = require("dotenv");


let pythonProcess = null;
let mainWindow = null;
// ----------------------------------------------------
// API KEY CHECK
// ----------------------------------------------------

function hasAPIKey() {
    const isWindows = process.platform === "win32";

    const backendDir = app.isPackaged
        ? path.join(process.resourcesPath, "backend")
        : path.join(__dirname, "releases", "main");

    const executableName = isWindows ? "main.exe" : "main";
    const exePath = path.join(backendDir, executableName);

    // If exe exists, .env should be next to it
    // If not, .env should be next to main.py
    const envDir = fs.existsSync(exePath) ? backendDir : path.join(__dirname, "releases", "main");
    const envPath = path.join(envDir, ".env");

    if (!fs.existsSync(envPath))
        return false;

    const env = dotenv.parse(fs.readFileSync(envPath));
    return env.GOOGLE_API_KEY && env.GOOGLE_API_KEY.trim() !== "";
}

ipcMain.handle(
    "has-api-key",
    () => {
        return hasAPIKey();
    }
);

ipcMain.handle(
    "exit-app",
    () => {
        if (pythonProcess) {
            pythonProcess.kill();
        }

        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.close();
        }

        app.quit();
        return true;
    }
);


// ----------------------------------------------------
// SEND COMMAND TO PYTHON BACKEND
// ----------------------------------------------------

ipcMain.handle(
    "execute-command",
    async (event, request) => {


        if (!pythonProcess) {

            return {
                success:false,
                error:"Python backend is not running"
            };

        }


        const payload =
            JSON.stringify({

                type:"command",

                command:
                    request.command,

                args:
                    request.args || {}

            });



        pythonProcess.stdin.write(
            payload + "\n"
        );


        return {
            success:true
        };

    }
);

// ----------------------------------------------------
// SEND PREVIEW COMMANDS
// ----------------------------------------------------

ipcMain.handle(
    "preview-command",
    async (event, request) => {


        if (!pythonProcess) {

            return {
                success:false,
                error:"Python backend is not running"
            };

        }


        const payload = JSON.stringify({

            type:"preview",

            action:
                request.action,

            args:
                request.args || {}

        });


        pythonProcess.stdin.write(
            payload + "\n"
        );


        return {
            success:true
        };

    }
);



// ----------------------------------------------------
// CREATE WINDOW
// ----------------------------------------------------

function createWindow() {


    mainWindow = new BrowserWindow({

        width:1200,

        height:800,


        webPreferences: {

            preload:
                path.join(
                    __dirname,
                    "preload.js"
                ),

            nodeIntegration:false,

            contextIsolation:true

        }

    });



    mainWindow.loadFile(
        "index.html"
    );



    startPythonBackend();

}



// ----------------------------------------------------
// START PYTHON BACKEND
// ----------------------------------------------------

function startPythonBackend() {

    const isWindows = process.platform === "win32";

    const backendDir = app.isPackaged
        ? path.join(process.resourcesPath, "backend")
        : path.join(__dirname, "releases", "main");

    const executableName = isWindows ? "main.exe" : "main";
    const exePath = path.join(backendDir, executableName);

    const outputDir = app.isPackaged
        ? app.getPath("userData")
        : backendDir;

    console.log("Backend directory:", backendDir);
    console.log("Output directory:", outputDir);

    if (fs.existsSync(exePath)) {

        console.log("Launching packaged executable:", exePath);

        pythonProcess = spawn(
            exePath,
            [],
            {
                cwd: backendDir
            }
        );

    } else {

        console.log("Executable not found, falling back to Python script");

        const pythonPath = isWindows
            ? path.join(__dirname, ".venv", "Scripts", "python.exe")
            : "python3";

        const scriptPath = path.join(__dirname, "main.py");

        pythonProcess = spawn(
            pythonPath,
            [
                "-u",
                scriptPath,
                outputDir
            ],
            {
                cwd: __dirname,
                env: {
                    ...process.env,
                    PYTHONUNBUFFERED: "1"
                }
            }
        );

    }

    pythonProcess.stdout.on("data", (data) => {

        const lines = data.toString().split("\n");

        for (const line of lines) {

            if (!line.trim())
                continue;

            try {

                const response = JSON.parse(line);

                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.webContents.send(
                        "backend-response",
                        response
                    );
                }

            } catch {

                console.log("Backend:", line);

            }

        }

    });

    pythonProcess.stderr.on("data", (data) => {

        console.error("Backend stderr:");
        console.error(data.toString());

    });

    pythonProcess.on("error", (err) => {

        console.error("Failed to start backend:");
        console.error(err);

    });

    pythonProcess.on("close", (code) => {

        console.log("Backend exited:", code);

        if (code !== 0 && mainWindow && !mainWindow.isDestroyed()) {

            mainWindow.webContents.send(
                "backend-response",
                {
                    success: false,
                    error: `Backend exited unexpectedly (code ${code}).`
                }
            );

        }

        pythonProcess = null;

    });

}



// ----------------------------------------------------
// APP EVENTS
// ----------------------------------------------------

app.whenReady()
.then(
    createWindow
);



app.on(
    "window-all-closed",
    ()=>{


        if(pythonProcess && !pythonProcess.killed && !pythonProcess.exitCode && !pythonProcess.signalCode){
            try {
                pythonProcess.kill();
            } catch (error) {
                console.warn("Failed to stop Python process:", error);
            }
        }


        if(process.platform !== "darwin"){

            app.quit();

        }

    }
);

app.on(
    "before-quit",
    ()=>{

        if(pythonProcess && !pythonProcess.killed && !pythonProcess.exitCode && !pythonProcess.signalCode){
            try {
                pythonProcess.kill();
            } catch (error) {
                console.warn("Failed to stop Python process:", error);
            }
        }

    }
);