const { ipcRenderer } = require('electron');

function showPage(pageId) {

    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });

    document.getElementById(pageId).classList.add('active');
}
function clearOutput() {
    document.getElementById('outputBox').textContent = '';
}

document.getElementById('analysisBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('analysisPage');

        ipcRenderer.send('menu-option', '1');
    });

document.getElementById('summaryBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('summaryPage');

        ipcRenderer.send('menu-option', '2');
    });

document.getElementById('sourceBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('sourcePage');

        ipcRenderer.send('menu-option', '3');
    });

document.getElementById('errorBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('errorPage');

        ipcRenderer.send('menu-option', '4');
    });

document.getElementById('exitBtn').addEventListener('click', () => {

    ipcRenderer.send('menu-option', '5');

    setTimeout(() => {
        ipcRenderer.send('exit-app');
    }, 500);

});

//options for the analysis page

document.getElementById('codebaseAnalysisPipelineBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        ipcRenderer.send('menu-option', '1');
    });

document.getElementById('createCodeDatabaseOnlyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        ipcRenderer.send('menu-option', '2');
    });

document.getElementById('createJSONSummariesOnlyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        ipcRenderer.send('menu-option', '3');
    });

document.getElementById('createSummaryDatabasefromJSONOnlyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        ipcRenderer.send('menu-option', '4');
    });

document.getElementById('createDirectorySummariesOnlyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        ipcRenderer.send('menu-option', '5');
    });

document.getElementById('runBusinessRuleValidationOnlyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        ipcRenderer.send('menu-option', '6');
    });

document.getElementById('runUnitTestGenerationOnlyBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        ipcRenderer.send('menu-option', '7');
    });

document.getElementById('runUMLGenerationOnly')
    .addEventListener('click', () => {

        clearOutput();

        showPage('codebasePipelinePage');

        ipcRenderer.send('menu-option', '8');
    });

document.getElementById('analysisBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');

        ipcRenderer.send('menu-option', '9');
    });

//summary page buttons
document.getElementById('summaryBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');

        ipcRenderer.send('menu-option', '1');
    });

//Source code collections buttons
document.getElementById('sourceBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');

        ipcRenderer.send('menu-option', '1');
    });

//view errors buttons
document.getElementById('errorBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('homePage');

        ipcRenderer.send('menu-option', '1');
    });

//back buttons
document.getElementById('codebaseBackBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('analysisPage');

        ipcRenderer.send('menu-option', '1');
    });

document.getElementById('submitPathBtn')
    .addEventListener('click', () => {

        clearOutput();

        showPage('analysisPage');

        const path =
            document.getElementById('codebasePath').value;

        ipcRenderer.send(
            'codebase-path',
            path
        );

    });

//output
ipcRenderer.on('python-output', (event, text) => {

    const outputBox =
        document.getElementById('outputBox');

    outputBox.textContent += text;

});


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