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

    const envPaths = [
        path.join(__dirname, ".env"),
        path.join(__dirname, "releases", "main", ".env")
    ];
    for (const envPath of envPaths) {

        if (!fs.existsSync(envPath))
            continue;
        const env = dotenv.parse(
            fs.readFileSync(envPath)
        );
        if (
            env.GOOGLE_API_KEY && env.GOOGLE_API_KEY.trim() !== "") {
            return true;
        }
    }
    return false;
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

ipcMain.handle(
    "get-validated-rules",
    async (event, request) => {

        try {
            const codebasePath = request?.codebasePath;

            if (!codebasePath) {
                return {
                    success:false,
                    error:"No codebase path provided"
                };
            }

            const codebaseName = path.basename(codebasePath);
            const rulesPath = path.join(__dirname, "agent", "BR_agent_output", codebaseName, "validated_rules.json");

            let rulesFile = null;
            if (fs.existsSync(rulesPath)) {
                rulesFile = rulesPath;
            }

            if (!rulesFile) {
                return {
                    success:false,
                    error:"No validated business rules file found for this codebase"
                };
            }

            const rawContent = fs.readFileSync(rulesFile, "utf8");
            const rawData = JSON.parse(rawContent);
            const rules = [];

            if (Array.isArray(rawData)) {
                rawData.forEach((rule, index) => {
                    const text = rule?.rule || "";
                    if (text) {
                        rules.push({
                            id: String(rule?.id),
                            text,
                            source: rule?.source_directory || "Generated rule"
                        });
                    }
                });
            } else if (rawData && typeof rawData === "object") {
                Object.entries(rawData).forEach(([sourcePath, entries]) => {
                    if (!Array.isArray(entries)) return;
                    entries.forEach((rule, index) => {
                        const text = rule?.rule || "";
                        if (text) {
                            rules.push({
                                id: String(rule?.id),
                                text,
                                source: sourcePath
                            });
                        }
                    });
                });
            }

            return {
                success:true,
                rules
            };

        } catch (error) {
            return {
                success:false,
                error:error.message
            };
        }
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


    const isWindows =
        process.platform === "win32";


    const isMac =
        process.platform === "darwin";



    const pythonPath =
        isWindows

            ? path.join(
                __dirname,
                ".venv",
                "Scripts",
                "python.exe"
            )

            : "python3";



    pythonProcess = spawn(

        pythonPath,

        [
            path.join(
                __dirname,
                "main.py"
            )
        ],

        {

            cwd:__dirname,

            env:{
                ...process.env,
                PYTHONUNBUFFERED:"1"
            }

        }

    );



    pythonProcess.stdout.on(
        "data",
        (data)=>{


            const lines =
                data
                .toString()
                .split("\n");



            for (const line of lines) {


                if (!line.trim())
                    continue;

                try {


                    const response =
                        JSON.parse(line);

                    mainWindow.webContents.send(
                        "backend-response",
                        response
                    );
                }
                catch(error) {
                    console.log(
                        "Python:",
                        line
                    );


                }

            }

        }
    );

    pythonProcess.stderr.on("data", (data) => {

        console.error(
            "Python stderr:",
            data.toString()
        );

    });


    pythonProcess.on("close", (code) => {

        console.log(
            "Python exited:",
            code
        );

        if (code !== 0 && mainWindow) {

            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send(
                    "backend-response",
                    {
                        success: false,
                        error: `Python backend exited unexpectedly (code ${code}).`
                    }
                );
            }

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