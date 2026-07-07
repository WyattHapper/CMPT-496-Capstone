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



    pythonProcess.stderr.on(
    "data",
    (data)=>{

        console.log(
            "Python Log:",
            data.toString()
        );
    

        if(mainWindow){

            mainWindow.webContents.send(
                "backend-response",
                {
                    success:false,
                    error:error
                }
            );
        }
    }
);



    pythonProcess.on(
        "close",
        (code)=>{

            console.log(
                "Python exited:",
                code
            );

            pythonProcess=null;

        }
    );

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


        if(pythonProcess){

            pythonProcess.kill();

        }


        if(process.platform !== "darwin"){

            app.quit();

        }

    }
);

app.on(
    "before-quit",
    ()=>{

        if(pythonProcess){

            pythonProcess.kill();

        }

    }
);