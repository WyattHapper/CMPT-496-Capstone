const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {

    // API key check
    hasAPIKey: () => {
        return ipcRenderer.invoke("has-api-key");
    },


    // Send menu selections
    sendMenuOption: (option) => {
        ipcRenderer.send("menu-option", option);
    },


    // Send codebase path
    sendCodebasePath: (path) => {
        ipcRenderer.send("codebase-path", path);
    },


    // Press enter in python CLI
    sendEnter: () => {
        ipcRenderer.send("send-enter");
    },


    // Exit app
    exitApp: () => {
        ipcRenderer.send("exit-app");
    },


    // API key submission
    sendAPIKey: (key) => {
        ipcRenderer.send("api-key", key);
    },


    // Listen for Python output
    onAnalysisPythonOutput: (callback) => {
        ipcRenderer.on("python-output", (event, text) => {
            callback(text);
        });
    },

    // Listen for Python output
    onErrorOutput: (callback) => {
        ipcRenderer.on("error-output", (event, text) => {
            callback(text);
        });
    },

    // Listen for Summary Python output (numbered list items into buttons)
    onSummaryPythonOutput: (callback) => {
        ipcRenderer.on("summary-output", (event, text) => {
            callback(text);
        });
    },

    onSummarySelectionOutput: (callback) => {
        ipcRenderer.on("summary-selection-output", (event, text) => {
            callback(text);
        });
    },

    onSourcePythonOutput: (callback) => {
        ipcRenderer.on("source-output", (event, text) => {
            callback(text);
        });
    },

    onSourceSelectionOutput: (callback) => {
        ipcRenderer.on("source-selection-output", (event, text) => {
            callback(text);
        });
    },


    // onCollectionPreview: (callback) => {
    //     ipcRenderer.on("collection-preview", (event, text) => {
    //         callback(text);
    //     });
    // },


    // onCollectionsList: (callback) => {
    //     ipcRenderer.on("collections-list", (event, collections) => {
    //         callback(collections);
    //     });
    // }

});