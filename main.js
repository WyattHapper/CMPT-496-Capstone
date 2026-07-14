const { app, BrowserWindow, ipcMain, shell } = require('electron');
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




function detectFileType(json) {

    // Summary files have these fields
    if (
        json.summary ||
        json.functions ||
        json.dependencies ||
        json.types
    ) {
        return "summary";
    }


    // Source collection example
    if (
        json.directory_name ||
        json.directory_path ||
        json.purpose ||
        json.responsibilities
        

    ) {
        return "source";
    }


    return "unknown";
}
// ----------------------------------------------------
// SUMMARY FORMATTING
// ----------------------------------------------------

function formatSummary(json) {

    const lines = [];

    // File
    lines.push(`# ${path.basename(json.path)}`);
    lines.push("");
    lines.push(`File: ${json.path}`);
    lines.push("");

    // Summary
    if (json.summary) {
        lines.push("=== Summary ===");
        lines.push(json.summary);
        lines.push("");
    }

    // Dependencies
    if (json.dependencies?.length) {
        lines.push("=== Dependencies ===");

        json.dependencies.forEach(dep => {
            lines.push(`• ${dep}`);
        });

        lines.push("");
    }

    // Standalone functions
    if (json.functions?.length) {
        lines.push("=== Functions ===");

        json.functions.forEach(func => {

            lines.push(`${func.name}()`);

            if (func.description)
                lines.push(`   ${func.description}`);

            if (func.return_type)
                lines.push(`   Returns: ${func.return_type}`);

            lines.push("");

        });
    }

    // Classes / Types
    if (json.types?.length) {

        lines.push("=== Classes ===");

        json.types.forEach(type => {

            lines.push("");
            lines.push(`${type.kind.toUpperCase()}: ${type.name}`);

            if (type.description)
                lines.push(type.description);

            // Properties
            if (type.properties?.length) {

                lines.push("");
                lines.push("Properties:");

                type.properties.forEach(prop => {

                    lines.push(
                        `  • ${prop.name} : ${prop.type}`
                    );

                });
            }

            // Methods
            if (type.methods?.length) {

                lines.push("");
                lines.push("Methods:");

                type.methods.forEach(method => {

                    lines.push(
                        `  • ${method.name}()`
                    );

                    if (method.description)
                        lines.push(
                            `      ${method.description}`
                        );

                });
            }

            lines.push("");

        });
    }

    // Business Rules
    if (json.business_rules?.length) {

        lines.push("=== Business Rules ===");

        json.business_rules.forEach((rule, i) => {

            lines.push(`${i + 1}. ${rule.rule}`);

        });

        lines.push("");

    }

    return lines.join("\n");

}

function formatSource(json) {

    const lines = [];


    lines.push(`# ${json.directory_name || "Unknown Directory"}`);
    lines.push("");


    if (json.directory_name) {

        lines.push("=== Directory Name ===");
        lines.push(json.directory_name);
        lines.push("");

    }


    if (json.directory_path) {

        lines.push("=== Directory Path ===");
        lines.push(json.directory_path);
        lines.push("");

    }


    if (json.purpose) {

        lines.push("=== Purpose ===");
        lines.push(json.purpose);
        lines.push("");

    }


    if (json.responsibilities?.length) {

        lines.push("=== Responsibilities ===");

        json.responsibilities.forEach(item => {
            lines.push(`• ${item}`);
        });

        lines.push("");

    }


    return lines.join("\n");

}

// ----------------------------------------------------
// ICP HANDLERS
// ----------------------------------------------------

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

        const action = request?.action;
        const args = request?.args || {};

        if (action === "files") {
            const rawPath = args.path || "agent";
            const targetPath = path.isAbsolute(rawPath)
                ? rawPath
                : path.join(__dirname, rawPath);

            if (!fs.existsSync(targetPath)) {
                return {
                    success: false,
                    error: `Path not found: ${targetPath}`
                };
            }

            const stats = fs.statSync(targetPath);
            if (!stats.isDirectory()) {
                return {
                    success: false,
                    error: `Path is not a directory: ${targetPath}`
                };
            }

            const dirents = fs.readdirSync(targetPath, {
                withFileTypes: true
            });

            const entries = dirents
                .map((dirent) => ({
                    name: dirent.name,
                    path: path.join(targetPath, dirent.name),
                    isDirectory: dirent.isDirectory()
                }))
                .sort((a, b) => {
                    if (a.isDirectory !== b.isDirectory) {
                        return a.isDirectory ? -1 : 1;
                    }
                    return a.name.localeCompare(b.name, undefined, {
                        sensitivity: 'base'
                    });
                });

            const result = {
                success: true,
                type: "files",
                path: targetPath,
                files: entries
            };

            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send("backend-response", result);
            }

            return result;
        }


        if (action === "open_file") {
            const rawPath = args.path;
            if (!rawPath) {
                const result = {
                    success: false,
                    error: "No file path provided"
                };

                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.webContents.send("backend-response", result);
                }

                return result;
            }

            const targetPath = path.isAbsolute(rawPath)
                ? rawPath
                : path.join(__dirname, rawPath);

            if (!fs.existsSync(targetPath)) {
                const result = {
                    success: false,
                    error: `File not found: ${targetPath}`
                };

                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.webContents.send("backend-response", result);
                }

                return result;
            }

            const stats = fs.statSync(targetPath);
            if (!stats.isFile()) {
                const result = {
                    success: false,
                    error: `Path is not a file: ${targetPath}`
                };

                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.webContents.send("backend-response", result);
                }

                return result;
            }

            const content = fs.readFileSync(targetPath, "utf8");

            let preview;

            try {

                const json = JSON.parse(content);
                const type = detectFileType(json);

                if (type === "summary") {

                    preview = {
                        type: "summary",
                        content: formatSummary(json)
                    };

                } else if (type === "source") {

                    preview = {
                        type: "source",
                        content: formatSource(json)
                    };

                } else {

                    preview = {
                        type: "unknown",
                        content: content
                    };

                }

            } catch {

                preview = {
                    type: "text",
                    content
                };

            }


            const result = {
                success:true,
                type:"file-preview",
                path:targetPath,
                preview
            };

            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send("backend-response", result);
            }

            return result;
        }

        if (!pythonProcess) {
            return {
                success:false,
                error:"Python backend is not running"
            };
        }


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

    let pythonBuffer = "";

    pythonProcess.stdout.on("data", (data) => {

        pythonBuffer += data.toString();


        let lines = pythonBuffer.split("\n");

        pythonBuffer = lines.pop();


        for (const line of lines) {

            if (!line.trim())
                continue;


            try {

                const parsed = JSON.parse(line);

                mainWindow.webContents.send(
                    "backend-response",
                    parsed
                );


            }
            catch(error) {

                console.log(
                    "Backend parse error:",
                    error.message
                );

                console.log(line);

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