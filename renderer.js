const { ipcRenderer } = require('electron');

function showPage(pageId) {

    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });

    document.getElementById(pageId).classList.add('active');
}

document.getElementById('analysisBtn')
    .addEventListener('click', () => {

        showPage('analysisPage');

        ipcRenderer.send('menu-option', '1');
    });

document.getElementById('summaryBtn')
    .addEventListener('click', () => {

        showPage('summaryPage');

        ipcRenderer.send('menu-option', '2');
    });

document.getElementById('sourceBtn')
    .addEventListener('click', () => {

        showPage('sourcePage');

        ipcRenderer.send('menu-option', '3');
    });

document.getElementById('errorBtn')
    .addEventListener('click', () => {

        showPage('errorPage');

        ipcRenderer.send('menu-option', '4');
    });

document.getElementById('exitBtn').addEventListener('click', () => {

    ipcRenderer.send('menu-option', '5');

    setTimeout(() => {
        ipcRenderer.send('exit-app');
    }, 500);

});

/*document.getElementById('run').addEventListener('click', () => {
    ipcRenderer.send('menu-option', '1');

    ipcRenderer.send('run-app');
});*/

document.getElementById('analysisBtn')
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
});

ipcRenderer.on('python-output', (event, text) => {

    document.getElementById('analysisOutput').innerHTML +=
        `<pre>${text}</pre>`;
});