
// Variables top determine if a step has been completed or not -- will help with prompting text without having to pull from the output
let ranFullPipline = false; // Flag to track if the full pipeline has been run

let summariesMade = false; // Flag to track if summaries have been made
let sourcesMade = false; // Flag to track if source collections have been made
let errorsMade = false; // flag totrack if source collections have been made


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
        sourceOutput.textContent = '';
    }

    const summaryOutputBox =
        document.getElementById('summaryOutputBox');

    if (summaryOutputBox) {
        summaryOutputBox.textContent = '';
    }

    const summaryOutputContainer =
        document.getElementById('summaryOutput');

    if (summaryOutputContainer) {
        summaryOutputContainer.querySelectorAll('.summary-file-btn').forEach((button) => {
            button.remove();
        });
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
        if (!summariesMade) { 
            const noVecSumEl = document.getElementById('noVectorStoresMsgSum');
            if (noVecSumEl) noVecSumEl.classList.remove('hidden');

            const summaryOutputEl = document.getElementById('summaryOutput');
            if (summaryOutputEl) summaryOutputEl.classList.add('hidden');

            const summariesSubheaderEl = document.getElementById('summariesSubheader');
            if (summariesSubheaderEl) summariesSubheaderEl.classList.add('hidden');
        }

        window.electronAPI.sendMenuOption('3');
    });

document.getElementById('sourceBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('sourcePage');
        if (!sourcesMade) { 
            const noVecSrcEl = document.getElementById('noVectorStoresMsgSrc');
            if (noVecSrcEl) noVecSrcEl.classList.remove('hidden');

            const sourceOutputEl = document.getElementById('sourceOutput');
            if (sourceOutputEl) sourceOutputEl.classList.add('hidden');

            const sourceCollectionSubheaderEl = document.getElementById('sourceCollectionSubheader');
            if (sourceCollectionSubheaderEl) sourceCollectionSubheaderEl.classList.add('hidden');
        }
       
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

        window.electronAPI.sendMenuOption('1');
    });

//Source code collections buttons
document.getElementById('sourceBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');

        if (!ranFullPipline && !ranJSONSummaries && !ranSummaryDB) {
            window.electronAPI.sendEnter();
        } else{
            window.electronAPI.sendMenuOption('1');
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

//NO idea if this works at all yet, this is supposed to faciliate buttons being made for the summary page
//working on function or if statemnt tocheck if this operation yields any button so we can display "There is no summary text" otherwise
window.electronAPI.onSummaryPythonOutput((text) => {

    // declarations
    const summaryOutputBox =
        document.getElementById('summaryOutputBox');
    const summaryOutputContainer =
        document.getElementById('summaryOutput');

    if (!summaryOutputBox || !summaryOutputContainer) {
        return;
    }

    //take out stray characters from the output and add it to the summary output box
    summaryPendingLine += text.replace(/\r/g, '');

    //split the output into lines and process each line
    const parts = summaryPendingLine.split('\n');
    summaryPendingLine = parts.pop();

    parts.forEach((line) => {
        summaryOutputBox.textContent += line + '\n';
        
        //button creation by line
        const match = line.match(/^\s*(\d+)\.\s*(.+)$/);
        if (match) {
            const button = document.createElement('button');
            button.className = 'summary-file-btn btn-primary';
            button.textContent = `${match[1]}. ${match[2]}`;

            button.addEventListener('click', () => {
                summaryOutputBox.textContent = `${match[1]}. ${match[2]}`;
            });

            summaryOutputContainer.appendChild(button);
        }
    });

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