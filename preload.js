const { contextBridge, ipcRenderer } = require("electron");


contextBridge.exposeInMainWorld(
    "electronAPI",
    {


        // ==================================
        // Backend Commands
        // ==================================

        executeCommand: (
            command,
            args = {}
        ) => {

            return ipcRenderer.invoke(
                "execute-command",
                {
                    command,
                    args
                }
            );

        },



        // ==================================
        // Collection Preview Commands
        // ==================================

        previewCommand: (
            action,
            args = {}
        ) => {

            return ipcRenderer.invoke(
                "preview-command",
                {
                    action,
                    args
                }
            );

        },



        // ==================================
        // API Key
        // ==================================

        hasAPIKey: () => {

            return ipcRenderer.invoke(
                "has-api-key"
            );

        },

        getValidatedRules: (
            codebasePath
        ) => {
            return ipcRenderer.invoke(
                "get-validated-rules",
                {
                    codebasePath
                }
            );
        },

        setAPIKey: (
            key
        ) => {


            return ipcRenderer.invoke(
                "execute-command",
                {
                    command:"set_api_key",

                    args:{
                        api_key:key
                    }
                }
            );

        },



        // ==================================
        // Backend Response Listener
        // ==================================

        onBackendResponse: (
            callback
        ) => {


            ipcRenderer.on(
                "backend-response",
                (
                    event,
                    response
                )=>{


                    callback(response);


                }
            );

        },


        // Optional cleanup
        removeBackendListener: () => {

            ipcRenderer.removeAllListeners(
                "backend-response"
            );

        }


    }
);