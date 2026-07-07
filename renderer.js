
// ============================================
// Backend State
// ============================================

let ranFullPipeline = false;

let summariesMade = false;
let sourcesMade = false;
let errorsMade = false;


// Currently selected codebase
let selectedCodebasePath = "";


// Collection preview state
let viewingSummaryPreview = false;
let viewingSourcePreview = false;


// Preview text buffers
let summaryPreviewText = "";
let sourcePreviewText = "";


// Backend response buffer
let backendOutputBuffer = "";

// Checks if the API key has been set
const envPath = ".env";

let hasAPI = false; // Flag to track if the API key has been set

//start of the code to check if the API key has been set and determineif the API button should be active or not
//activates the API button if the API key has not been set, otherwise it will be disabled -- also changes attributes within that page and enables the anaylsis button
window.electronAPI.hasAPIKey()
    .then((apiKeyExists) => {
        hasAPI = apiKeyExists;

        if (hasAPI) {

            const apiBtnEl =
                document.getElementById("apiBtn");

            if (apiBtnEl)
                apiBtnEl.classList.add("unusable-btn");


            const analysisBtnEl =
                document.getElementById("analysisBtn");

            if (analysisBtnEl)
                analysisBtnEl.classList.remove("unusable-btn");


            const apiKeyMsgEl =
                document.getElementById("apiKeyMsg");

            if (apiKeyMsgEl)
                apiKeyMsgEl.classList.remove("hidden");


            const replaceApiKeyBtnEl =
                document.getElementById("replaceApiKeyBtn");

            if (replaceApiKeyBtnEl)
                replaceApiKeyBtnEl.classList.remove("hidden");


            const keepApiKeyBtnEl =
                document.getElementById("keepApiKeyBtn");

            if (keepApiKeyBtnEl)
                keepApiKeyBtnEl.classList.remove("hidden");

            const submitApiKeyBtnEl =
                document.getElementById("submitApiKeyBtn");

            if (submitApiKeyBtnEl)
                submitApiKeyBtnEl.classList.add("hidden");

            const apiKeyInputEl =
                document.getElementById("apiKeyInput");

            if (apiKeyInputEl)
                apiKeyInputEl.classList.add("hidden");

            const apiBackBtnEl =
                document.getElementById("apiBackBtn");

            if (apiBackBtnEl)
                apiBackBtnEl.classList.add("hidden");
        }

    });

// ============================================
// Backend Communication Helpers
// ============================================


async function runBackendCommand(
    command,
    args = {}
){

    console.log(
        "Command:",
        command,
        args
    );


    return await window.electronAPI.executeCommand(
        command,
        args
    );

}



async function runPreviewCommand(
    action,
    args = {}
){

    console.log(
        "Preview:",
        action,
        args
    );


    return await window.electronAPI.previewCommand(
        action,
        args
    );

}

function showPage(pageId) {

    document.querySelectorAll('.page').forEach(page => {
        page.classList.add('hidden');
    });

    document.getElementById(pageId).classList.remove('hidden');
}



// clears oput anything from the screen that does not need to be there
function clearOutput() {

    const outputBox =
        document.getElementById('analysisOutputBox');

    if (outputBox) {
        outputBox.textContent = '';
    }

    const errorOutput =
        document.getElementById('errorOutput');

    if (errorOutput) {
        errorOutput.textContent = '';
    }

    const sourceOutput =
        document.getElementById('sourceOutput');

    if (sourceOutput) {
        sourceOutput.querySelectorAll('.source-file-btn, .source-preview-text')
            .forEach((element) => {
                element.remove();
            });
    }

    const sourceOutputBox =
        document.getElementById('sourceOutputBox');

    if (sourceOutputBox) {
        sourceOutputBox.textContent = '';
    }

    const summaryOutputBox =
        document.getElementById('summaryOutputBox');

    if (summaryOutputBox) {
        summaryOutputBox.textContent = '';
    }

    const summaryOutputContainer =
        document.getElementById('summaryOutput');

    if (summaryOutputContainer) {
        summaryOutputContainer.querySelectorAll('.summary-file-btn, .summary-preview-text')
        .forEach((element) => {
    
            element.remove();
        });

        summaryPreviewText = "";
        viewingSummaryPreview = false;
        sourcePreviewText = "";
        viewingSourcePreview = false;
    }

    summaryPendingLine = '';
}

// MENU BUTTONS
document.getElementById('analysisBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('analysisPage');


    
    });

document.getElementById('apiBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('apiPage');

        if (hasAPI) {
            
            overwriteApiUi();

        } else {

            newApiUi();

        }


    
    });

document.getElementById('summaryBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('summaryPage');

        // Reset the page
        const summaryOutputEl =
            document.getElementById('summaryOutput');

        const noVecSumEl =
            document.getElementById('noVectorStoresMsgSum');

        const summariesSubheaderEl =
            document.getElementById('summariesSubheader');


        if (summaryOutputEl)
            summaryOutputEl.classList.remove('hidden');

        if (noVecSumEl)
            noVecSumEl.classList.add('hidden');

        if (summariesSubheaderEl)
            summariesSubheaderEl.classList.remove('hidden');


        runPreviewCommand(
        "list",
        {
         db_type:"summary"
        });
    });

document.getElementById('sourceBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('sourcePage');

        const sourceOutputEl = document.getElementById('sourceOutput');
        if (sourceOutputEl) sourceOutputEl.classList.remove('hidden');

        const sourceCollectionSubheaderEl = document.getElementById('sourceCollectionSubheader');
        if (sourceCollectionSubheaderEl) sourceCollectionSubheaderEl.classList.remove('hidden');

        const noVecSrcEl = document.getElementById('noVectorStoresMsgSrc');
        if (noVecSrcEl) noVecSrcEl.classList.add('hidden');
       
        runPreviewCommand(
        "list",
        {
         db_type:"source"
        });
    });

document.getElementById('errorBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('errorPage');
        if (!errorsMade) { 
            const noErrorsMsgEl = document.getElementById('noErrorsMsg');
            if (noErrorsMsgEl) noErrorsMsgEl.classList.remove('hidden');

            //const errorOutputEl = document.getElementById('errorOutput');
            //if (errorOutputEl) errorOutputEl.classList.add('hidden');

            const errorSubheaderEl = document.getElementById('errorSubheader');
            if (errorSubheaderEl) errorSubheaderEl.classList.add('hidden');
        }

    });

document.getElementById('exitBtn').addEventListener('click', () => {



    setTimeout(() => {
        window.electronAPI.exitApp();
    }, 500);

});
//======================================================
//options for the analysis page
//======================================================
document.getElementById('codebaseAnalysisPipelineBtn')
    .addEventListener('click', () => {

        runBackendCommand(
        "full_pipeline",
        {
            codebase:selectedCodebasePath
        });
    });

document.getElementById('createCodeDatabaseOnlyBtn')
    .addEventListener('click', () => {

        runBackendCommand(
            "build_database",
        {
            codebase:selectedCodebasePath
        });
    });

document.getElementById('createJSONSummariesOnlyBtn')
    .addEventListener('click', () => {

        runBackendCommand(
            "file_summary",
        {
            codebase:selectedCodebasePath
        });
    });

document.getElementById('createSummaryDatabasefromJSONOnlyBtn')
    .addEventListener('click', () => {

        runBackendCommand(
        "build_summary_database",
        {
            codebase:selectedCodebasePath
        });
    });

document.getElementById('createDirectorySummariesOnlyBtn')
    .addEventListener('click', () => {

        runBackendCommand(
            "directory_summary",
            {
                codebase:selectedCodebasePath
            }
        );
    });

document.getElementById('runBusinessRuleValidationOnlyBtn')
    .addEventListener('click', () => {

        runBackendCommand(
            "validate_business_rules",
            {
                codebase:selectedCodebasePath
            }
        );
    });

document.getElementById('runUnitTestGenerationOnlyBtn')
    .addEventListener('click', () => {

       runBackendCommand(
            "generate_unit_tests",
            {
                codebase:selectedCodebasePath
            }
        );
    });

document.getElementById('runUMLGenerationOnly')
    .addEventListener('click', () => {

        runBackendCommand(
            "generate_uml",
            {
                codebase:selectedCodebasePath
            }
        );
    });

document.getElementById('analysisBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');
    });
//======================================================
//API PAGE BUTTONS
//======================================================

document.getElementById('apiBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');
    });

document.getElementById('submitApiKeyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');

        document.getElementById('apiBtn').classList.add('unusable-btn');
        document.getElementById('analysisBtn').classList.remove('unusable-btn');

        const apiKey =
            document.getElementById('apiKeyInput').value;

        runBackendCommand(
        "set_api_key",
        {
            api_key: apiKey
        });

    });

document.getElementById('replaceApiKeyBtn')
    .addEventListener('click', () => {

        console.log("Replace API Key button clicked");
        clearOutput();

        newApiUi();
        document.getElementById('apiBackBtn').classList.add('hidden');

    });
    
document.getElementById('keepApiKeyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');

    });

        

//======================================================
//summary page buttons
//======================================================
document.getElementById('summaryBackBtn')
.addEventListener('click', () => {

    clearOutput();

    showPage('homePage');

    viewingSummaryPreview = false;

});

//======================================================
//Source code collections buttons
//======================================================
document.getElementById('sourceBackBtn')
.addEventListener('click', () => {

    clearOutput();

    showPage('homePage');

    viewingSourcePreview = false;

});
//======================================================
//view errors buttons
//======================================================
document.getElementById('errorBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');
    });

//======================================================
//back buttons
//======================================================
document.getElementById('codebaseBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('analysisPage');
    });

document.getElementById('outputBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('analysisPage');
    });

document.getElementById('submitPathBtn')
.addEventListener('click', () => {


    clearOutput();


    showPage('outputPage');


    selectedCodebasePath =
        document.getElementById(
            'codebasePath'
        ).value;



    runBackendCommand(
        "set_codebase",
        {
            path:selectedCodebasePath
        }
    );


    document
        .getElementById("analysisOutput")
        .classList
        .remove("hidden");

});

document.getElementById('individualStepsBtn')
    .addEventListener('click', () => {
        
        clearOutput();

        document.getElementById('individualStepsContainer').classList.toggle('hidden');
        document.getElementById('pipelineOptions').classList.toggle('hidden');
        document.getElementById('backToFullPipelineBtn').classList.toggle('hidden');
        document.getElementById('analysisBackBtn').classList.toggle('hidden');
    });

document.getElementById('backToFullPipelineBtn')
    .addEventListener('click', () => {
        
        clearOutput();

        document.getElementById('individualStepsContainer').classList.toggle('hidden');
        document.getElementById('pipelineOptions').classList.toggle('hidden');
        document.getElementById('backToFullPipelineBtn').classList.toggle('hidden');
        document.getElementById('analysisBackBtn').classList.toggle('hidden');
    });



//output
let pendingLine = '';
let lastLine = '';
let summaryPendingLine = '';

// ============================================
// Backend Response Handler
// ============================================


window.electronAPI.onBackendResponse(
    (response)=>{


        console.log(
            "Backend response:",
            response
        );

        if(!response){
            return;
        }
    
        // ERROR HANDLING
        if(!response.success){
            errorsMade = true;

            const errorBox =
                document.getElementById(
                    "errorOutput"
                );

            if(errorBox){

                errorBox.textContent +=
                    response.error + "\n";

            }
            return;
        }
        // NORMAL OUTPUT
        if(response.message){


            const outputBox =
                document.getElementById(
                    "analysisOutputBox"
                );

            if(outputBox){

                outputBox.textContent +=
                    response.message + "\n";
            }
        }

        // COLLECTION LIST RESPONSE
        if(response.collections){


            renderCollections(
                response.collections,
                response.db_type
            );
        }

        // COLLECTION PREVIEW RESPONSE
        if(response.preview){

            renderCollectionPreview(
                response.preview,
                response.db_type
            );

        }
    }
);

// ============================================
// Collection List Rendering
// ============================================


function renderCollections(
    collections,
    dbType
){


    console.log(
        "Collections:",
        collections
    );


    const container =
        dbType === "summary"
            ? document.getElementById(
                "summaryOutput"
            )
            :
            document.getElementById(
                "sourceOutput"
            );


    if(!container){
        return;
    }


    container.innerHTML = "";



    collections.forEach(
        (collection)=>{


            const button =
                document.createElement(
                    "button"
                );

            button.className =
                "output-file-btn btn-primary";

            button.textContent =
                collection;

            button.addEventListener(
                "click",
                ()=>{
                    if(dbType==="summary"){

                        viewingSummaryPreview=true;
                    }
                    else{

                        viewingSourcePreview=true;
                    }
                    runPreviewCommand(
                        "preview",
                        {
                            db_type:dbType,
                            collection:collection
                        }
                    );
                }
            );
            container.appendChild(
                button
            );
        }
    );
}

// ============================================
// Collection Preview Rendering
// ============================================


function renderCollectionPreview(
    preview,
    dbType
){
    let container;
    if(dbType==="summary"){

        container =
            document.getElementById(
                "summaryOutput"
            );
    }
    else{
        container =
            document.getElementById(
                "sourceOutput"
            );
    }
    if(!container){
        return;
    }

    container.innerHTML="";

    const pre =
        document.createElement(
            "pre"
        );

    pre.className =
        dbType==="summary"
            ?
            "summary-preview-text"
            :
            "source-preview-text";

    pre.textContent =
        preview;
    container.appendChild(
        pre
    );


}


function toggleTheme() {
  const newTheme =
    document.body.dataset.theme === "dark"
      ? "light"
      : "dark";

  document.body.dataset.theme = newTheme;

  localStorage.setItem("theme", newTheme);
}

function overwriteApiUi() {
    document.getElementById('apiKeyMsg').classList.remove("hidden");
    document.getElementById('apiKeyInput').classList.add("hidden");
    document.getElementById('submitApiKeyBtn').classList.add("hidden");
    document.getElementById('replaceApiKeyBtn').classList.remove("hidden");            
    document.getElementById('keepApiKeyBtn').classList.remove("hidden");
    document.getElementById('apiBackBtn').classList.add("hidden");
}

function newApiUi() {
    document.getElementById('apiKeyMsg').classList.add("hidden");
    document.getElementById('apiKeyInput').classList.remove("hidden");
    document.getElementById('submitApiKeyBtn').classList.remove("hidden");
    document.getElementById('replaceApiKeyBtn').classList.add("hidden");
    document.getElementById('keepApiKeyBtn').classList.add("hidden");
    document.getElementById('apiBackBtn').classList.remove("hidden");
}