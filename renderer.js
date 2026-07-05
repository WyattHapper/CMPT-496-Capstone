
// Variables top determine if a step has been completed or not -- will help with prompting text without having to pull from the output
let ranFullPipline = false; // Flag to track if the full pipeline has been run

let summariesMade = false; // Flag to track if summaries have been made
let sourcesMade = false; // Flag to track if source collections have been made
let errorsMade = false; // flag totrack if source collections have been made

let viewingSummaryPreview = false; // Flag to track if the user is viewing a summary preview
let viewingSourcePreview = false; // Flag to track if the user is viewing a source preview


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


        window.electronAPI.sendMenuOption('1');
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


        window.electronAPI.sendMenuOption('2');
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


        // Ask Python for summary collections
        window.electronAPI.sendMenuOption('3');
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
       
        window.electronAPI.sendMenuOption('4');
    });

document.getElementById('errorBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('errorPage');
        if (!errorsMade) { 
            const noErrorsMsgEl = document.getElementById('noErrorsMsg');
            if (noErrorsMsgEl) noErrorsMsgEl.classList.remove('hidden');

            const errorOutputEl = document.getElementById('errorOutput');
            if (errorOutputEl) errorOutputEl.classList.add('hidden');

            const errorSubheaderEl = document.getElementById('errorSubheader');
            if (errorSubheaderEl) errorSubheaderEl.classList.add('hidden');
        }

        window.electronAPI.sendMenuOption('5');
    });

document.getElementById('exitBtn').addEventListener('click', () => {

    window.electronAPI.sendMenuOption('6');

    setTimeout(() => {
        window.electronAPI.exitApp();
    }, 500);

});
//======================================================
//options for the analysis page
//======================================================
document.getElementById('codebaseAnalysisPipelineBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        window.electronAPI.sendMenuOption('1');
    });

document.getElementById('createCodeDatabaseOnlyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        window.electronAPI.sendMenuOption('2');
    });

document.getElementById('createJSONSummariesOnlyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        window.electronAPI.sendMenuOption('3');
    });

document.getElementById('createSummaryDatabasefromJSONOnlyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        window.electronAPI.sendMenuOption('4');
    });

document.getElementById('createDirectorySummariesOnlyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        window.electronAPI.sendMenuOption('5');
    });

document.getElementById('runBusinessRuleValidationOnlyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        window.electronAPI.sendMenuOption('6');
    });

document.getElementById('runUnitTestGenerationOnlyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        window.electronAPI.sendMenuOption('7');
    });

document.getElementById('runUMLGenerationOnly')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        window.electronAPI.sendMenuOption('8');
    });

document.getElementById('analysisBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');

        window.electronAPI.sendMenuOption('9');
    });
//======================================================
//API PAGE BUTTONS
//======================================================

document.getElementById('apiBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');

        window.electronAPI.sendMenuOption('1');
    });

document.getElementById('submitApiKeyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');

        document.getElementById('apiBtn').classList.add('unusable-btn');
        document.getElementById('analysisBtn').classList.remove('unusable-btn');

        const apiKey =
            document.getElementById('apiKeyInput').value;

        window.electronAPI.sendAPIKey(apiKey);
        window.electronAPI.sendEnter();

    });

document.getElementById('replaceApiKeyBtn')
    .addEventListener('click', () => {

        console.log("Replace API Key button clicked");
        clearOutput();

        window.electronAPI.sendMenuOption('1');

        newApiUi();
        document.getElementById('apiBackBtn').classList.add('hidden');

    });
    
document.getElementById('keepApiKeyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');


        window.electronAPI.sendMenuOption('2');
    });

        

//======================================================
//summary page buttons
//======================================================
document.getElementById('summaryBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');

         if (viewingSummaryPreview || viewingSourcePreview) {
            window.electronAPI.sendEnter();
        } else {
            window.electronAPI.sendMenuOption('b');
        }
    });

//Source code collections buttons
document.getElementById('sourceBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');

        if (viewingSummaryPreview || viewingSourcePreview) {
            window.electronAPI.sendEnter();
        } else {
            window.electronAPI.sendMenuOption('b');
        }
    });
//======================================================
//view errors buttons
//======================================================
document.getElementById('errorBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');

        window.electronAPI.sendMenuOption('1');
    });

//======================================================
//back buttons
//======================================================
document.getElementById('codebaseBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('analysisPage');

        window.electronAPI.sendMenuOption('1');
    });

document.getElementById('outputBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('analysisPage');

        window.electronAPI.sendMenuOption('1');
    });

document.getElementById('submitPathBtn')
    .addEventListener('click', () => {

        clearOutput();

        //showPage('analysisPage');
        showPage('outputPage')

        const path =
            document.getElementById('codebasePath').value;

        window.electronAPI.sendCodebasePath(path);
        
        document.getElementById("analysisOutput").classList.remove("hidden");

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

window.electronAPI.onAnalysisPythonOutput((text) => {

    const outputBox =
        document.getElementById('analysisOutputBox');

    if (!outputBox) {
        return;
    }

    //split up the output by lines and take out all the random characters that are being outputted by the python script
    pendingLine += text.replace(/\r/g, '');

    const parts = pendingLine.split('\n');

    pendingLine = parts.pop();

    //once newline character is found print it in the box to let the user know it is getting used
    if (parts.length > 0) {
        lastLine = parts[parts.length - 1];
    }

    outputBox.textContent =
        pendingLine || lastLine;

});

//creates buttons on summary page
window.electronAPI.onSummaryPythonOutput((text) => {

    viewingSummaryPreview = false;

    const summaryOutputContainer =
        document.getElementById("summaryOutput");
        
    console.log("SUMMARY RECEIVED:");
    console.log(text);

    // Remove any existing buttons
    summaryOutputContainer
        .querySelectorAll(".output-file-btn")
        .forEach(btn => btn.remove());

    
    text.split("\n").forEach(line => {

        const cleanedLine = line.replace(/\x00|\u0000/g, '');
        const match = cleanedLine.match(/^\s*(\d+)\.\s*(.+)$/); // get rid of all those extra text

        if (!match) return;

        const optionNumber = match[1]; // number from the CLI to send to choose the button
        const filename = match[2];

        const button = document.createElement("button"); //create the buttons
        button.className = "output-file-btn btn-primary";
        button.textContent = filename;

        //when one of the buttons is clicked it will route you to the right page and clear the div out to fill with new text
        button.addEventListener("click", () => {
            viewingSummaryPreview = true;
            console.log("Selected:", filename);

            summaryPreviewText = "";
            summaryOutputContainer.innerHTML = "";

            window.electronAPI.sendMenuOption(optionNumber);
        });

        summaryOutputContainer.appendChild(button); //add the buttons to the output box
    });

    document
        .getElementById("noVectorStoresMsgSum")
        .classList.add("hidden");

    
});

let summaryPreviewText = "";

window.electronAPI.onSummarySelectionOutput((text) => {

    const container =
        document.getElementById("summaryOutput");

    let preview =
        container.querySelector(".summary-preview-text");

    if (!preview) {

        container.innerHTML = "";

        preview = document.createElement("pre");
        preview.className = "summary-preview-text";

        container.appendChild(preview);

        summaryPreviewText = "";
    }

    summaryPreviewText += text;
    preview.textContent = summaryPreviewText;
});

let sourcePreviewText = "";

window.electronAPI.onSourcePythonOutput((text) => {

    viewingSourcePreview = false;

    const sourceOutputContainer =
        document.getElementById("sourceOutput");

    
    console.log("SOURCE RECEIVED:");
    console.log(text);

    

    sourceOutputContainer
        .querySelectorAll(".output-file-btn")
        .forEach(btn => btn.remove());

    

    text.split("\n").forEach(line => {

        const cleanedLine = line.replace(/\x00|\u0000/g, '');
        const match = cleanedLine.match(/^\s*(\d+)\.\s*(.+)$/);

        if (!match) return;

        const optionNumber = match[1];
        const filename = match[2];

        const button = document.createElement("button");
        button.className = "output-file-btn btn-primary";
        button.textContent = filename;

        button.addEventListener("click", () => {
            viewingSourcePreview = true;
            console.log("Selected:", filename);

            sourcePreviewText = "";
            sourceOutputContainer.innerHTML = "";

           
            window.electronAPI.sendMenuOption(optionNumber);
        });

        sourceOutputContainer.appendChild(button);
    });

    document
        .getElementById("noVectorStoresMsgSum")
        .classList.add("hidden");


   
});

window.electronAPI.onSourceSelectionOutput((text) => {

    const sourceOutputContainer =
        document.getElementById("sourceOutput");

    let preview = 
    sourceOutputContainer.querySelector(".source-preview-text");

    if (!preview) {

        sourceOutputContainer.innerHTML = "";

        preview = document.createElement("pre");
        preview.className = "source-preview-text";

        sourceOutputContainer.appendChild(preview);

        sourcePreviewText = "";
    }

    sourcePreviewText += text;
    preview.textContent = sourcePreviewText;
});

// window.electronAPI.onCollectionPreview((text) => {

//         const previewBox =
//             document.getElementById(
//                 'sourceOutput'
//             );

//         previewBox.textContent += text;

//     }
// );

// //this is used for the source collections page to display different options
// window.electronAPI.onCollectionsList((collections) => {

//     const container =
//         document.getElementById('collectionsContainer');

//     container.innerHTML = '';

//     collections.forEach((name, index) => {

//         const btn = document.createElement('button');

//         btn.textContent = name;

//         btn.className = 'collectionBtn';

//         btn.addEventListener('click', () => {

//             window.electronAPI.sendMenuOption(String(index + 1));

//         });

//         container.appendChild(btn);

//     });

// });


/*document.getElementById('run').addEventListener('click', () => {
    ipcRenderer.send('menu-option', '1');

    ipcRenderer.send('run-app');
});*/

/*document.getElementById('analysisBtn')
    .addEventListener('click', () => {

        showPage('analysisPage');

        ipcRenderer.send('menu-option', '1');
    });

document.getElementById('summary').addEventListener('click', () => {
    ipcRenderer.send('menu-option', '2');
});

document.getElementById('source').addEventListener('click', () => {
    ipcRenderer.send('menu-option', '3');
});

document.getElementById('errors').addEventListener('click', () => {
    ipcRenderer.send('menu-option', '4');
});*/

/*ipcRenderer.on('python-output', (event, text) => {

    document.getElementById('analysisOutput').innerHTML +=
        `<pre>${text}</pre>`;
});*/


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