
// ============================================
// Backend State
// ============================================


let pathSubmitted = false;

let ranFullPipeline = false;

let summariesMade = false;
let sourcesMade = false;
let errorsMade = false;


// Currently selected codebase
let selectedCodebasePath = "";


// Selections
let selectedRules = [];

// Backend response buffer
let backendOutputBuffer = "";

//loadingscreen 
let activeCommand = null;
let pipelineMode = false;

let totalSteps = 1;
let currentStep = 0;

let currentStepProgress = 0;


let selectedValidatedRule = null;

//output
let pendingLine = '';
let lastLine = '';
let summaryPendingLine = '';

// Checks if the API key has been set
const envPath = ".env";

let hasAPI = false; // Flag to track if the API key has been set

//start of the code to check if the API key has been set and determineif the API button should be active or not
//activates the API button if the API key has not been set, otherwise it will be disabled -- also changes attributes within that page and enables the anaylsis button

window.electronAPI.hasAPIKey()
    .then((apiKeyExists) => {
        hasAPI = apiKeyExists;

        if (hasAPI) {

            const apiBtnEl = document.getElementById("apiBtn");
            if (apiBtnEl) apiBtnEl.classList.add("unusable-btn");

            const analysisBtnEl = document.getElementById("analysisBtn");
            if (analysisBtnEl) analysisBtnEl.classList.remove("unusable-btn");

            const apiKeyMsgEl = document.getElementById("apiKeyMsg");
            if (apiKeyMsgEl) apiKeyMsgEl.classList.remove("hidden");

            const replaceApiKeyBtnEl = document.getElementById("replaceApiKeyBtn");
            if (replaceApiKeyBtnEl) replaceApiKeyBtnEl.classList.remove("hidden");

            const keepApiKeyBtnEl = document.getElementById("keepApiKeyBtn");
            if (keepApiKeyBtnEl) keepApiKeyBtnEl.classList.remove("hidden");

            const submitApiKeyBtnEl = document.getElementById("submitApiKeyBtn");
            if (submitApiKeyBtnEl) submitApiKeyBtnEl.classList.add("hidden");

            const apiKeyInputEl = document.getElementById("apiKeyInput");
            if (apiKeyInputEl) apiKeyInputEl.classList.add("hidden");

            const apiBackBtnEl = document.getElementById("apiBackBtn");
            if (apiBackBtnEl) apiBackBtnEl.classList.add("hidden");
        }

    });

// ============================================
// Backend Communication Helpers
// ============================================

function showLoading(title, message) {


    const overlay =
        document.getElementById("loadingOverlay");

    if (!overlay) return;

    overlay.classList.remove("hidden");

    document.getElementById("loadingTitle").textContent = title;
    document.getElementById("loadingStepMessage").textContent = message;

    // show spinner & loading bar
    document.getElementById("loadingSpinner").classList.remove("hidden");
    document.getElementById("stepProgressContainer").classList.remove("hidden");

    // Hide pipeline progress by default
    document.getElementById("pipelineProgressContainer").classList.add("hidden");


    //hide ok button
    document.getElementById("loadingOkBtn").classList.add("hidden");

   
}


function updateStepLoading(message) {

    const messageElement =
        document.getElementById("loadingStepMessage");

    if (!messageElement) return;

    message = message.replace(
        /^\s*\[\s*progress\s*\]\s*/i,
        ""
    );

    messageElement.textContent = message;
}

function updatePipelineLoading(message) {

    const messageElement =
        document.getElementById("loadingPipelineMessage");

    if (!messageElement) return;

    message = message.replace(
        /^\s*\[\s*progress\s*\]\s*/i,
        ""
    );

    messageElement.textContent = message;
}



function finishLoading(message = "Process completed successfully!") {

    document.getElementById("loadingTitle").textContent = "Complete";

    document.getElementById("loadingMessage").textContent = message;

    // hide spinner & loading bar
    document.getElementById("loadingSpinner").classList.add("hidden");
    document.getElementById("stepProgressContainer").classList.add("hidden");
    document.getElementById("pipelineProgressContainer").classList.add("hidden");
    document.getElementById("stepProgressTitle").classList.add("hidden");


    // show OK button
    document.getElementById("loadingOkBtn").classList.remove("hidden");
}

function hideLoading() {

    const overlay =
        document.getElementById("loadingOverlay");

    if (!overlay) return;

    overlay.classList.add("hidden");
}

function updatePipleineProgressBar(percent){

    document.getElementById("pipelineProgressContainer").classList.remove("hidden");
    document.getElementById("stepProgressTitle").classList.remove("hidden");

    const bar =
        document.getElementById("loadingPipelineProgressBar");

    const text =
        document.getElementById("loadingPipelineProgressText");


    if(bar)
        bar.style.width = `${percent}%`;

    if(text)
        text.textContent = `${Math.round(percent)}%`;
}

function updateStepProgressBar(percent){

    const bar =
        document.getElementById("loadingStepProgressBar");

    const text =
        document.getElementById("loadingStepProgressText");


    if(bar)
        bar.style.width = `${percent}%`;

    if(text)
        text.textContent = `${Math.round(percent)}%`;
}


async function runBackendCommand(command,args={}){


    activeCommand = command;


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

    const response = await window.electronAPI.previewCommand(
        action,
        args
    );

    console.log("Preview response:", response);

    if (!response) {
        console.error("No preview response returned");
        return response;
    }

    if (!response.success) {
        console.error("Preview command failed:", response.error);
        return response;
    }

    if (response.files) {
        console.log("Rendering file buttons", response.files);
        renderViewFileButtons(response.files);
    }

    return response;
}


function renderViewSummaryButtons(collections) {

    const container =
        document.getElementById("viewSummariesBtns");

    container.innerHTML = "";

    container.classList.remove("hidden");

    collections.forEach(collection => {

        const button =
            document.createElement("button");

        button.className =
            "btn-secondary";

        button.textContent =
            collection;

        button.addEventListener("click", () => {

            const codebaseName = selectedCodebasePath
                .split(/[\\/]/)
                .pop();

            const summaryPath = [
                "agent",
                "file_summary_agent_output",
                codebaseName,
                `${collection}.json`
            ].join("/");

            runPreviewCommand(
                "open_file",
                {
                    path: summaryPath
                }
            );

        });

        container.appendChild(button);

    });

}

//this function will display the buttons when the files btn is clicked
function renderViewFileButtons(files)
{
    const container =
        document.getElementById("viewFilesBtns");

    container.innerHTML = "";

    container.classList.remove("hidden");

    files.forEach(file => {

        const button =
            document.createElement("button");

        button.className = "btn-secondary";

        button.textContent = file.name;

        button.addEventListener("click", () => {

            if(file.isDirectory){

                runPreviewCommand(
                    "files",
                    {
                        path:file.path
                    }
                );

            }
            else{

                runPreviewCommand(
                    "open_file",
                    {
                        path:file.path
                    }
                );

            }

        });

        container.appendChild(button);

    });

}

function renderViewOutput(entries) {

    const output =
        document.getElementById("viewDisplayOutputBox");

    output.textContent = "";

    entries.forEach(entry => {

        output.textContent +=
            JSON.stringify(entry, null, 2) + "\n\n";
    });
}

function renderSummaryPreview(text) {

    const output = document.getElementById("viewDisplayOutputBox");

    output.innerHTML = "";

    const card = document.createElement("div");
    card.className = "summary-card";


    const sections = text.split("===");


    sections.forEach(section => {

        section = section.trim();

        if (!section)
            return;


        const lines = section.split("\n");


        const title = lines[0].trim();


        // These are your real headers
        const headers = [
            "Summary",
            "Dependencies",
            "Functions",
            "Classes",
            "Business Rules"
        ];


        if (headers.includes(title)) {

            const header = document.createElement("h2");
            header.textContent = title;
            header.className = "summary-header";
            const specificClassName = title.toLowerCase().replace("business ", "")
            header.classList.add(`${specificClassName}-header`);



            const body = document.createElement("pre");
            body.className = "summary-section-body";
            body.textContent = lines.slice(1).join("\n").trim();


            card.appendChild(header);
            card.appendChild(body);

        }

        else {

            // File name + path section
            const body = document.createElement("pre");
            body.className = "summary-section-body";
            body.textContent = section;


            card.appendChild(body);

        }

    });


    output.appendChild(card);

}

function renderSourcePreview(text){

    const output =
        document.getElementById("viewDisplayOutputBox");

    output.innerHTML = "";

    const card = document.createElement("div");
    card.className = "directory-card";


    const sections = text.split("===");


    sections.forEach(section => {

        section = section.trim();

        if (!section)
            return;


        const lines = section.split("\n");

        const title = lines[0].trim();


        const headers = [
            "Directory Name",
            "Directory Path",
            "Purpose",
            "Responsibilities"
        ];


        if (headers.includes(title)) {

            const header = document.createElement("h3");
            header.textContent = title;
            header.className = "directory-header";


            const body = document.createElement("pre");
            body.className = "directory-section-body";

            body.textContent =
                lines.slice(1)
                .join("\n")
                .trim();


            card.appendChild(header);
            card.appendChild(body);

        }
        else {

            const body = document.createElement("pre");

            body.className =
                "directory-section-body directory-title";

            body.textContent =
                section;


            card.appendChild(body);

        }

    });


    output.appendChild(card);

}

function renderBusinessRulesPreview(text) {

    const output = document.getElementById("viewDisplayOutputBox");

    output.innerHTML = "";

    const card = document.createElement("div");
    card.className = "business-rule-card";


    const sections = text.split("===");


    sections.forEach(section => {

        section = section.trim();

        if (!section)
            return;


        const lines = section.split("\n");

        const title = lines[0].trim();


        // Rule headers
        if (title.startsWith("Business Rule")) {

            const header = document.createElement("h2");
            header.textContent = title;
            header.className = "business-rule-header";


            const body = document.createElement("pre");
            body.className = "business-rule-section-body";

            body.textContent =
                lines.slice(1)
                .join("\n")
                .trim();


            card.appendChild(header);
            card.appendChild(body);

        }

        else {

            // Main "# Business Rules" title
            const body = document.createElement("pre");

            body.className =
                "business-rule-section-body business-rule-title";

            body.textContent =
                section;


            card.appendChild(body);

        }

    });


    output.appendChild(card);

}

function renderErrorPreview(text){
    
}

function renderTextPreview(text) {

    const output =
        document.getElementById("viewDisplayOutputBox");

    if (!output) {
        console.error("viewDisplayOutputBox not found");
        return;
    }

    output.innerHTML = "";

    const pre = document.createElement("pre");

    pre.className = "file-preview-text";

    pre.textContent = text;

    output.appendChild(pre);
}

function showPage(pageId) {

    document.querySelectorAll('.page').forEach(page => {
        page.classList.add('hidden');
    });

    document.getElementById(pageId).classList.remove('hidden');
}

function showButtons(buttonId) {

    document.querySelectorAll('.viewBtnContainer').forEach(buttonContainer => {
        if (buttonContainer.id !== "mainViewBtns") {

            buttonContainer.classList.add('hidden');
        }
    });

    document.getElementById(buttonId).classList.remove('hidden');
}



function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

async function loadValidatedRulesSelection() {
    const statusEl = document.getElementById('validatedRuleSelectionStatus');
    const listEl = document.getElementById('validatedRuleList');
    const detailsEl = document.getElementById('selectedValidatedRuleDetails');

    if (!statusEl || !listEl || !detailsEl) return;

    statusEl.textContent = 'Loading validated rules...';
    listEl.innerHTML = '';
    detailsEl.classList.add('hidden');
    detailsEl.innerHTML = '';

    if (!selectedCodebasePath) {
        statusEl.textContent = 'Select a codebase from the pipeline page first.';
        return;
    }

    try {
        const response = await window.electronAPI.getValidatedRules(selectedCodebasePath);

        if (!response?.success) {
            statusEl.textContent = response?.error || 'No validated rules were found.';
            return;
        }

        const rules = response.rules || [];

        if (!rules.length) {
            statusEl.textContent = 'No validated rules were found for this codebase.';
            return;
        }

        statusEl.textContent = `Showing ${rules.length} validated rule${rules.length === 1 ? '' : 's'}.`;

        const fragment = document.createDocumentFragment();

        rules.forEach((rule, index) => {
            const id = parseInt(rule.id)
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'selection-item-btn';
            button.innerHTML = `
                <span class="selection-item-title">${escapeHtml(index + 1)}: ${escapeHtml(rule.text)}</span>
            `;
            if (selectedRules.includes(id)) {
                button.classList.add('selected')
            }
            button.addEventListener('click', () => {
                if (button.classList.contains('selected')) {
                    selectedRules = selectedRules.filter(item => item !== id);
                    button.classList.remove('selected');
                } else {
                    selectedRules.push(id);
                    button.classList.add('selected')
                }
            });

            fragment.appendChild(button);
        });

        listEl.appendChild(fragment);

    } catch (error) {
        console.error(error);
        statusEl.textContent = 'Unable to load validated rules.';
    }
}


//loading complete button
document.getElementById("loadingOkBtn").addEventListener("click", () => {

    hideLoading();

    document.getElementById("loadingOkBtn").classList.add("hidden");

});

// MENU BUTTONS
document.getElementById('analysisBtn')
    .addEventListener('click', () => {

        


        if (!pathSubmitted) {
            showPage('codebasePipelinePage');
        } else {
            showPage('analysisPage');
        }

    
    });

document.getElementById('apiBtn')
    .addEventListener('click', () => {

        

        showPage('apiPage');

        if (hasAPI) {
            
            overwriteApiUi();

        } else {

            newApiUi();

        }


    
    });


// ---------------------------------------------
// ViewPageButtons
// ---------------------------------------------
document.getElementById('mainViewBtn')
    .addEventListener('click', () => {

        
        showPage('mainViewPage');

    });

document.getElementById("viewDisplaySourcesBtn")
.addEventListener("click", () => {

    showButtons("viewSourcesBtns");

    const codebaseName = selectedCodebasePath.split("/").pop();

    runPreviewCommand(
        "files",
        {
            path:`agent/directory_agent_output/${codebaseName}`
        }
    );

});

document.getElementById("viewDisplaySummariesBtn")
    .addEventListener("click", () => {

        showButtons("viewSummariesBtns");

        const codebaseName = selectedCodebasePath.split("/").pop();

        runPreviewCommand("files", {
            path: `agent/file_summary_agent_output/${codebaseName}`
        });

    });

document.getElementById("viewDisplayFilesBtn").addEventListener("click", () => {

    showButtons("viewFilesBtns");

    runPreviewCommand(
        "files",
        {
            path: "agent"
        }
    );

});

document.getElementById("viewDisplayBusinessRulesBtn").addEventListener("click", () => {

    showButtons("viewBusinessRulesBtns");


    

});

//Hardcoded to see if outputs work
document.getElementById("validatedBusinessRulesBtn").addEventListener("click", () => {

    runPreviewCommand(
        "open_file",
        {
            path: `agent/BR_agent_output/ConsoleTables-main/validated_rules.json`
        }
    );


});

//hoardcoded to see if outputs work
document.getElementById("discardedBusinessRulesBtn").addEventListener("click", () => {

    runPreviewCommand(
        "open_file",
        {
            path: `agent/BR_agent_output/ConsoleTables-main/discarded_rules.json`
        }
    );

});

document.getElementById('mainViewBackBtn')
    .addEventListener('click', () => {

        

        showPage('homePage');
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
        showLoading(
            "Running Full Pipeline",
            "Preparing..."
        );


        setTimeout(() => {

            runBackendCommand(
                "full_pipeline",
                {
                    codebase:selectedCodebasePath
                }
            );

        }, 100);

});

document.getElementById('createCodeDatabaseOnlyBtn')
    .addEventListener('click', () => {

        showLoading(
            "Source Code Database Creation",
            "Preparing..."
        );

        runBackendCommand(
            "build_database",
        {
            codebase:selectedCodebasePath
        });
    });

document.getElementById('createJSONSummariesOnlyBtn')
    .addEventListener('click', () => {

        showLoading(
            "Summary Database Creation",
            "Preparing..."
        );

        runBackendCommand(
            "file_summary",
        {
            codebase:selectedCodebasePath
        });
    });

document.getElementById('createSummaryDatabasefromJSONOnlyBtn')
    .addEventListener('click', () => {

        showLoading(
            "Summary Database Creation from JSON Only",
            "Preparing..."
        );

        runBackendCommand(
        "build_summary_database",
        {
            codebase:selectedCodebasePath
        });
    });

document.getElementById('createDirectorySummariesOnlyBtn')
    .addEventListener('click', () => {

        showLoading(
            "Directory Summaries Creation",
            "Preparing..."
        );

        runBackendCommand(
            "directory_summary",
            {
                codebase:selectedCodebasePath
            }
        );
    });

document.getElementById('runBusinessRuleValidationOnlyBtn')
    .addEventListener('click', () => {
        
        

        showPage('businessRulePage');

    });


document.getElementById('allBusinessRuleBtn')
    .addEventListener('click', () => {
        
        showLoading(
            "Business Rule Validation",
            "Preparing..."
        );

        runBackendCommand(
            "validate_business_rules",
            {
                codebase:selectedCodebasePath
            }
        );
    });



document.getElementById('individualBusinessRuleBtn')
    .addEventListener('click', () => {
        
        

        showPage('chooseBusinessRulePage');
        loadBusinessRulesSelection();
    });

document.getElementById('businessRuleBackBtn')
    .addEventListener('click', () => {

        

        showPage('analysisPage');

    });

document.getElementById('chooseBusinessRuleBackBtn')
    .addEventListener('click', () => {

        

        showPage('businessRulePage');

    });

document.getElementById('runUnitTestGenerationOnlyBtn')
    .addEventListener('click', () => {
        
        

        showPage('unitTestPage');
    });

document.getElementById('allValidatedRulesBtn')
    .addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        showLoading(
            "Unit Test Generation",
            "Preparing..."
        );

        runBackendCommand(
            "generate_unit_tests",
            {
                codebase:selectedCodebasePath,
                selected_rules: []
            }
        );
    })

document.getElementById('individualValidatedRulesBtn')
    .addEventListener('click', () => {
        
        

        showPage('chooseUnitTestPage');
        loadValidatedRulesSelection();
    });

document.getElementById('unitTestPageBackBtn')
    .addEventListener('click', () => {

        

        showPage('analysisPage');

    });

document.getElementById('chooseUnitTestPageSelectBtn')
    .addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        showLoading(
            "Unit Test Generation",
            "Preparing..."
        );

        runBackendCommand(
            "generate_unit_tests",
            {
                codebase:selectedCodebasePath,
                selected_rules: selectedRules
            }
        );
    });

document.getElementById('chooseUnitTestPageBackBtn')
    .addEventListener('click', () => {

        

        showPage('unitTestPage');

    });

document.getElementById('runUnitTestValidationOnlyBtn')
    .addEventListener('click', () => {
        
        
        
        showPage('unitTestPage');
        
    });

// FILLER FOR WHEN VALIDATION GETS ADDED ONTO THIS BRANCH, FOR NOW IT WILL NOT DO ANYTHING WHEN CLICKED

// document.getElementById('allUnitTestsBtn')
//     .addEventListener('click', () => {
        
//         showLoading(
//             "Unit Test Generation",
//             "Preparing..."
//         );

//        runBackendCommand(
//             "generate_unit_tests",
//             {
//                 codebase:selectedCodebasePath
//             }
//         );
//     });



document.getElementById('runUMLGenerationOnly')
    .addEventListener('click', () => {

        showLoading(
            "UML Generation",
            "Preparing..."
        );

        runBackendCommand(
            "generate_uml",
            {
                codebase:selectedCodebasePath
            }
        );
    });

document.getElementById('analysisBackBtn')
    .addEventListener('click', () => {

        

        showPage('homePage');
    });
//======================================================
//API PAGE BUTTONS
//======================================================

document.getElementById('apiBackBtn')
    .addEventListener('click', () => {

        

        showPage('homePage');
    });

document.getElementById('submitApiKeyBtn')
    .addEventListener('click', () => {

        

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
        

        newApiUi();
        document.getElementById('apiBackBtn').classList.add('hidden');

    });
    
document.getElementById('keepApiKeyBtn')
    .addEventListener('click', () => {

        

        showPage('homePage');

    });

    

//======================================================
//back buttons
//======================================================
document.getElementById('codebaseBackBtn')
    .addEventListener('click', () => {

        

        showPage('analysisPage');
    });


//======================================================
// Analysis Page Buttons
//======================================================

document.getElementById('submitPathBtn')
.addEventListener('click', () => {


    


    showPage('analysisPage');


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


});






// ============================================
// Backend Response Handler
// ============================================

window.electronAPI.onBackendResponse((response) => {

    console.log("ACTIVE:", activeCommand);
    console.log("RESPONSE:", response);


    if (!response) {
        return;
    }

    

    // ----------------------------------------
    // Formatted file previews
    // Summaries, sources, normal text files
    // ----------------------------------------
    if (response.type === "file-preview") {


        if (response.preview.type === "summary") {

            renderSummaryPreview(
                response.preview.content
            );

        } else if (response.preview.type === "source") {

            renderSourcePreview(
                response.preview.content
            );

        } else if (response.preview.type === "business_rules") {

            renderBusinessRulesPreview(
                response.preview.content
            );

        } else {

            renderTextPreview(
                response.preview.content
            );

        }


        return;
    }



    // ----------------------------------------
    // Progress updates
    // ----------------------------------------
    if (response.type === "progress") {

        console.log(response);

        updateStepLoading(response.stage);

        if (response.progress !== undefined) {
            console.log("Progress:", response.progress);
            updateStepProgressBar(response.progress);
        }

        return;
    }

    if (response.type === "pipeline_progress") {

        console.log(response);

        updatePipelineLoading(response.stage);

        if (response.progress !== undefined) {
            console.log("Progress:", response.progress);
            updatePipleineProgressBar(response.progress);
        }

        return;
    }



    // ----------------------------------------
    // Errors
    // ----------------------------------------
    if (!response.success) {

        errorsMade = true;

        const errorBox =
            document.getElementById("errorOutput");


        if (errorBox && response.error) {

            errorBox.textContent +=
                response.error + "\n";

        }

        console.log("ERROR RESPONSE:", response);

        if (activeCommand) {

            hideLoading();
            activeCommand = null;

        }


        return;
    }



    // ----------------------------------------
    // Analysis output messages
    // ----------------------------------------
    if (response.message) {

        const outputBox =
            document.getElementById("analysisOutputBox");


        if (outputBox) {

            outputBox.textContent +=
                response.message + "\n";

        }

    }




    // ----------------------------------------
    // Command completion
    // ----------------------------------------
    if (
        response.success &&
        response.individualStep === true
    ) {

        finishLoading(
            response.result?.message ||
            `${response.command} completed`
        );

        activeCommand = null;

    }

});
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


// ===========================================
// Display Functions
// ==========================================


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