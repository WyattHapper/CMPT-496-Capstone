
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

let activeFileListView = {
    includePdfs: false,
    onlyPdfs: false,
    recursivePdfs: false
};

let insightFolderHistory = [];
let currentInsightFolderPath = null;
let insightRootPath = null;
let insightParentPath = null;
let suppressAutoEnterOnce = false;

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

            showApiKeyPresent();

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

    // hide any report left over from a previous estimate
    const previousEstimate =
        document.getElementById("estimateOutput");

    if (previousEstimate) {
        previousEstimate.classList.add("hidden");
        previousEstimate.textContent = "";
    }

    resetTokenMeter();

   
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





// ============================================
// Live token meter
// ============================================

function resetTokenMeter() {

    const meter =
        document.getElementById("tokenMeter");

    if (!meter) return;

    meter.classList.add("hidden");

    document.getElementById("tokenMeterValue")
        .textContent = "0";

    document.getElementById("tokenMeterStages")
        .textContent = "";

    showLoadingWarning(null);

}


// Shown on the Complete screen when a command finished but had to leave
// something out, e.g. UML diagrams skipped because the AI's diagram text was
// invalid. Without it a missing diagram looks like a program mistake.
function showLoadingWarning(text) {

    const warning =
        document.getElementById("loadingWarning");

    if (!warning) return;

    warning.textContent = text || "";
    warning.classList.toggle("hidden", !text);

}


function updateTokenMeter(response) {

    const meter =
        document.getElementById("tokenMeter");

    if (!meter) return;

    meter.classList.remove("hidden");

    const total = response.total_tokens ?? 0;

    document.getElementById("tokenMeterValue")
        .textContent = total.toLocaleString();

}


function addTokenMeterStage(response) {

    const meter =
        document.getElementById("tokenMeter");

    const list =
        document.getElementById("tokenMeterStages");

    if (!meter || !list) return;

    meter.classList.remove("hidden");

    const used =
        (response.input_tokens ?? 0) + (response.output_tokens ?? 0);

    // The pipeline records itself as well as its stages, so showing its row
    // alongside them would look like double counting. Its figure is already
    // the running total above.
    if (response.stage === "full_pipeline") {

        document.getElementById("tokenMeterValue")
            .textContent = used.toLocaleString();

        return;
    }

    const row = document.createElement("div");
    row.className = "stage-row";

    const name = document.createElement("span");
    name.textContent = response.stage;

    const amount = document.createElement("span");
    amount.textContent =
        `${used.toLocaleString()} (${response.calls} calls)`;

    row.appendChild(name);
    row.appendChild(amount);
    list.appendChild(row);

}


function finishLoading(message = "Process completed successfully!") {

    document.getElementById("loadingTitle").textContent = "Complete";


    const stepMessage = document.getElementById("loadingStepMessage");

    if(stepMessage){
        stepMessage.textContent = message;
    }


    // hide spinner and progress bars
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
        renderViewFileButtons(response.files, activeFileListView, response.path);
    }

    if (response.type === "file-preview") {
        const preview = response.preview || {};

        // Clear existing output
        const outputBox = document.getElementById("viewDisplayOutputBox");
        if (outputBox) outputBox.innerHTML = "";

        if (preview.type === "pdf") {
            renderPdfPreview(preview.content);
        } else if (preview.type === "summary") {
            renderSummaryPreview(preview.content);
        } else if (preview.type === "source") {
            renderSourcePreview(preview.content);
        } else if (preview.type === "business_rules") {
            renderBusinessRulesPreview(preview.content);
        } else if (preview.type === "integration_tests") {
            renderIntegrationTestsPreview(preview.content);
        } else {
            // Unknown or plain text — try to pretty-print JSON when possible
            renderJsonPreview(preview.content);
        }
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

            const codebaseName = getSelectedCodebaseName();

            if (!codebaseName) {
                renderTextPreview("Select a codebase first from the pipeline page.");
                return;
            }

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
function setActiveFileListView(options = {}) {
    activeFileListView = {
        includePdfs: Boolean(options.includePdfs),
        onlyPdfs: Boolean(options.onlyPdfs),
        recursivePdfs: Boolean(options.recursivePdfs)
    };
}

function resetInsightFolderNavigation(rootPath) {
    // Clear history and wait for the renderer response to provide
    // the canonical (absolute) path. We avoid storing the raw
    // incoming rootPath because it may be relative.
    insightFolderHistory = [];
    currentInsightFolderPath = null;
    insightRootPath = null;
    insightParentPath = null;
}

function normalizePath(p) {
    if (!p) return p;
    return p.replace(/\\/g, "/").replace(/\/+$|\\+$/g, "").toLowerCase();
}

function getSelectedCodebaseName() {
    if (!selectedCodebasePath) return null;
    const parts = selectedCodebasePath.split(/[\\/]/).filter(Boolean);
    return parts.length ? parts[parts.length - 1] : null;
}

function enterInsightFolder(targetPath) {

    const normTarget = normalizePath(targetPath);
    const normCurrent = normalizePath(currentInsightFolderPath);

    console.log("enterInsightFolder() target:", targetPath);
    console.log("  normTarget:", normTarget, "normCurrent:", normCurrent);

    if (normCurrent && normTarget && normCurrent !== normTarget) {
        insightFolderHistory.push(currentInsightFolderPath);
    }

    currentInsightFolderPath = targetPath;

    runPreviewCommand("files", {
        path: targetPath,
        recursivePdfs: activeFileListView.recursivePdfs
    });
}

function goBackOneInsightFolder() {
    console.log("goBackOneInsightFolder() history:", insightFolderHistory, "root:", insightRootPath, "current:", currentInsightFolderPath);
    if (insightFolderHistory.length > 0) {
        currentInsightFolderPath = insightFolderHistory.pop();

        // When navigating back, avoid immediately auto-entering
        // a single-child directory. The next render will honor
        // `suppressAutoEnterOnce` and not auto-enter.
        suppressAutoEnterOnce = true;

        runPreviewCommand("files", {
            path: currentInsightFolderPath,
            recursivePdfs: activeFileListView.recursivePdfs
        });
        return;
    }

    // If there is no history, and we have a canonical root, show it.
    if (insightRootPath) {
        currentInsightFolderPath = insightRootPath;
        console.log("goBackOneInsightFolder(): no history, returning to root:", insightRootPath);
        runPreviewCommand("files", {
            path: insightRootPath,
            recursivePdfs: activeFileListView.recursivePdfs
        });
    }
}

function toFileUrl(filePath) {
    const normalizedPath = filePath.replace(/\\/g, "/");
    return normalizedPath.startsWith("/")
        ? `file://${normalizedPath}`
        : `file:///${normalizedPath}`;
}

function renderViewFileButtons(files, options = {}, currentPath = null)
{
    const container =
        document.getElementById("viewFilesBtns");

    container.innerHTML = "";

    container.classList.remove("hidden");

    const activeOptions = {
        includePdfs: Boolean(options.includePdfs),
        onlyPdfs: Boolean(options.onlyPdfs),
        recursivePdfs: Boolean(options.recursivePdfs)
    };

    /*if (currentPath) {
        if (!insightRootPath || currentPath === insightRootPath) {
            resetInsightFolderNavigation(currentPath);
        } else if (!currentInsightFolderPath) {
            currentInsightFolderPath = currentPath;
        }
    }*/

    if (currentPath) {
        // Ensure we use the canonical path returned by the backend
        // as the root so absolute/relative mismatches don't occur.
        if (!insightRootPath) {
            console.log("renderViewFileButtons(): setting root to", currentPath);
            insightRootPath = currentPath;
            currentInsightFolderPath = currentPath;
            insightFolderHistory = [];
        } else if (currentPath !== currentInsightFolderPath) {
            // If the renderer is showing a different path than we
            // currently have, set it without pushing into history.
            console.log("renderViewFileButtons(): updating currentInsightFolderPath to", currentPath);
            currentInsightFolderPath = currentPath;
        }
    }

    const filteredFiles = files.filter(file => {
        const name = file.name.toLowerCase();
        const isPdf = name.endsWith('.pdf');
        const isPy = name.endsWith('.py');
        const isTxt = name.endsWith('.txt');
        const isPycache = file.isDirectory && name === '__pycache__';
        const isBusinessRulesFolder = file.isDirectory && name === 'business_rules';

        if (isBusinessRulesFolder || isPycache) {
            return false;
        }

        if (isPy || isTxt) {
            return false;
        }

        if (activeOptions.onlyPdfs) {
            return isPdf;
        }

        if (!activeOptions.includePdfs && isPdf) {
            return false;
        }

        return true;
    });

    // If there's only one directory, automatically navigate into it
    // unless the render was triggered by a Back action. In that
    // case `suppressAutoEnterOnce` will prevent re-entering so the
    // UI actually stays at the parent folder.
    if (filteredFiles.length === 1 && filteredFiles[0].isDirectory) {
        console.log("renderViewFileButtons(): single directory detected ->", filteredFiles[0].path, "suppressAutoEnterOnce:", suppressAutoEnterOnce);

        if (suppressAutoEnterOnce) {
            // consume the suppression and show the parent contents
            suppressAutoEnterOnce = false;
        } else {
            enterInsightFolder(filteredFiles[0].path);
            return;
        }
    }

    filteredFiles.forEach(file => {

        const button =
            document.createElement("button");

        button.className = file.isDirectory ? "btn-folder" : "btn-secondary";

        button.textContent = file.name;

        button.addEventListener("click", () => {

            if(file.isDirectory){

                enterInsightFolder(file.path);

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

    if (insightFolderHistory.length > 0) {
        console.log("renderViewFileButtons(): showing back button, history:", insightFolderHistory);
        const backButton = document.createElement("button");
        backButton.className = "back-btn";
        backButton.textContent = "⬅ Back";
        backButton.addEventListener("click", goBackOneInsightFolder);
        container.appendChild(backButton);
    }

}

function renderPdfPreview(filePath) {
    const output = document.getElementById("viewDisplayOutputBox");

    if (!output) {
        console.error("viewDisplayOutputBox not found");
        return;
    }

    output.innerHTML = "";

    const card = document.createElement("div");
    card.className = "pdf-preview-card";

    const title = document.createElement("h2");
    title.className = "pdf-preview-title";
    title.textContent = filePath.split(/[\\/]/).pop() || "PDF Preview";

    const frame = document.createElement("iframe");
    frame.className = "pdf-preview-frame";
    frame.title = "PDF Preview";
    frame.src = toFileUrl(filePath);
    frame.setAttribute("type", "application/pdf");

    card.appendChild(title);
    card.appendChild(frame);
    output.appendChild(card);
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

function renderErrorPreview(errors) {


    console.log("renderErrorPreview called");
    console.log(errors);

    const errorList = Array.isArray(errors)
        ? errors
        : errors
            ? [errors]
            : [];

    const output =
        document.getElementById("viewDisplayOutputBox");

    output.innerHTML = "";

    if (errorList.length === 0) {

        output.textContent =
            "No errors have been recorded.";

        return;
    }

    // Entries are {time, command, code, message}; older ones may be strings.
    const rows = errorList.map(error => (
        typeof error === "string"
            ? ["—", "—", "—", error]
            : [
                formatStamp(error.time),
                error.code ?? "—",
                error.command || "—",
                error.message || "—",
            ]
    ));

    const card = document.createElement("div");
    card.className = "summary-card usage-card";

    card.appendChild(usageHeader("Errors"));

    card.appendChild(usageTable(["Time", "Code", "Step", "Message"], rows))
        .classList.add("error-table");

    const note = document.createElement("p");
    note.className = "usage-note";
    note.textContent =
        "Errors since the last full pipeline started. " +
        "They are kept when the app is closed.";
    card.appendChild(note);

    output.appendChild(card);
}

// ============================================
// AI Usage (last_run_log.json)
// ============================================

function formatSeconds(seconds) {

    if (seconds === null || seconds === undefined) return "—";

    if (seconds < 60) return `${seconds.toFixed(1)} s`;

    const minutes = Math.floor(seconds / 60);
    const rest = Math.round(seconds % 60);

    return `${minutes} min ${rest} s`;
}

function formatCount(value) {

    return (value ?? 0).toLocaleString();
}

function formatStamp(stamp) {

    return stamp ? new Date(stamp).toLocaleString() : "—";
}

function usageStatus(status) {

    const badge = document.createElement("span");
    badge.className = `usage-status ${status}`;
    badge.textContent = status;

    return badge;
}

// rows: array of arrays of cells; a cell is text or a DOM node.
// headers may be null for a plain label/value table.
function usageTable(headers, rows, footer) {

    const table = document.createElement("table");
    table.className = "usage-table";

    if (headers) {

        const head = table.createTHead().insertRow();

        headers.forEach(text => {
            const th = document.createElement("th");
            th.textContent = text;
            head.appendChild(th);
        });
    }

    const body = table.createTBody();

    const addRow = (cells, target) => {
        const row = target.insertRow();
        cells.forEach(cell => {
            const td = row.insertCell();
            if (cell instanceof Node) td.appendChild(cell);
            else td.textContent = cell;
        });
    };

    rows.forEach(cells => addRow(cells, body));

    if (footer) addRow(footer, table.createTFoot());

    return table;
}

function usageHeader(text) {

    const header = document.createElement("h2");
    header.className = "summary-header";
    header.textContent = text;

    return header;
}

function renderRunUsage(run) {

    const output =
        document.getElementById("viewDisplayOutputBox");

    output.innerHTML = "";

    if (!run) {
        renderTextPreview(
            "No run recorded yet.\n\n" +
            "Run the full pipeline, or any step that uses the AI, " +
            "and its token usage and timings will show here."
        );
        return;
    }

    const card = document.createElement("div");
    card.className = "summary-card usage-card";

    card.appendChild(usageHeader("AI Usage — Last Run"));

    const totals = run.totals || {};

    const failedNote = totals.failed_calls
        ? ` (${totals.failed_calls} failed)`
        : "";

    const overview = [
        ["Codebase", run.codebase || "—"],
        ["Status", usageStatus(run.status)],
        ["Started", formatStamp(run.started_at)],
        ["Duration", formatSeconds(run.elapsed_seconds)],
        ["AI calls", formatCount(totals.calls) + failedNote],
        ["Input tokens", formatCount(totals.input_tokens)],
        ["Output tokens", formatCount(totals.output_tokens)],
        ["Total tokens", formatCount(totals.total_tokens)],
        ["Run ID", run.run_id || "—"],
    ];

    // Only when Google made us wait, so a slow run reads as throttled,
    // not stuck.
    if (totals.waits) {
        overview.splice(4, 0, [
            "Waited for Google",
            `${totals.waits} time${totals.waits === 1 ? "" : "s"}, ` +
            formatSeconds(totals.waited_seconds),
        ]);
    }

    card.appendChild(usageTable(null, overview))
        .classList.add("usage-overview");

    if (run.error) {
        const error = document.createElement("pre");
        error.className = "summary-section-body usage-error";
        error.textContent = run.error_code
            ? `Error ${run.error_code}: ${run.error}`
            : run.error;
        card.appendChild(error);
    }

    const stages = run.stages || [];

    if (stages.length) {

        card.appendChild(usageHeader("By Step"));

        card.appendChild(usageTable(
            ["Step", "Status", "Time", "Calls", "Input", "Output", "Total"],
            stages.map(stage => [
                stage.stage,
                usageStatus(stage.status),
                formatSeconds(stage.elapsed_seconds),
                formatCount(stage.calls),
                formatCount(stage.input_tokens),
                formatCount(stage.output_tokens),
                formatCount(stage.total_tokens),
            ]),
            [
                "Total", "", formatSeconds(run.elapsed_seconds),
                formatCount(totals.calls),
                formatCount(totals.input_tokens),
                formatCount(totals.output_tokens),
                formatCount(totals.total_tokens),
            ]
        ));
    }

    const calls = run.calls || [];

    if (calls.length) {

        card.appendChild(usageHeader("Slowest AI Calls"));

        const slowest = [...calls]
            .sort((a, b) => (b.duration_seconds ?? 0) - (a.duration_seconds ?? 0))
            .slice(0, 5);

        card.appendChild(usageTable(
            ["Step", "Time", "Input", "Output", "Status"],
            slowest.map(call => [
                call.stage,
                formatSeconds(call.duration_seconds),
                formatCount(call.input_tokens),
                formatCount(call.output_tokens),
                usageStatus(call.status),
            ])
        ));
    }

    const failed = calls.filter(call => call.status === "failed");

    if (failed.length) {

        card.appendChild(usageHeader("Failed AI Calls"));

        card.appendChild(usageTable(
            ["Step", "Code", "Error"],
            failed.map(call => [
                call.stage,
                call.error_code ?? "—",
                call.error || "—",
            ])
        )).classList.add("error-table");
    }

    const waits = run.waits || [];

    if (waits.length) {

        card.appendChild(usageHeader("Waits for Google"));

        const reasonText = reason => reason === "429"
            ? "429 rate limit"
            : `${reason} Google busy`;

        card.appendChild(usageTable(
            ["Step", "Reason", "Waited"],
            waits.map(wait => [
                wait.stage,
                reasonText(wait.reason),
                formatSeconds(wait.seconds),
            ])
        ));
    }

    const note = document.createElement("p");
    note.className = "usage-note";
    note.textContent =
        "Shows the most recent run that used the AI. " +
        "Output tokens include the model's thinking tokens.";
    card.appendChild(note);

    output.appendChild(card);
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

function setFAQSupportActive(activeButton) {

    const supportBtn = document.getElementById("supportBtn");
    const faqBtn = document.getElementById("faqBtn");


    supportBtn.classList.remove("btn-inverted");
    faqBtn.classList.remove("btn-inverted");


    if (activeButton === "support") {

        supportBtn.classList.add("btn-inverted");

    } else {

        
        faqBtn.classList.add("btn-inverted");

    }
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
    showPage('homePage');

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


document.getElementById('faqAndSupportBtn')
    .addEventListener('click', () => {

        showPage('faqAndSupportPage')
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

    const codebaseName = getSelectedCodebaseName();
    if (!codebaseName) {
        renderTextPreview("Select a codebase first from the pipeline page.");
        return;
    }
    try {
        const rootPath = `agent/directory_agent_output/${codebaseName}`;
        resetInsightFolderNavigation(rootPath);

        runPreviewCommand(
            "files",
            {
                path: rootPath
            }
        );
    } catch (error) {
        const rootPath = `backend/agent/directory_agent_output/${codebaseName}`;
        resetInsightFolderNavigation(rootPath);

        runPreviewCommand(
            "files",
            {
                path: rootPath
            }
        );
    }

    runPreviewCommand(
        "files",
        {
            path: rootPath
        }
    );

});

document.getElementById("viewDisplayErrorsBtn")
.addEventListener("click", async () => {

    showButtons("viewErrorsBtns");

    await runBackendCommand("get_errors");

});

document.getElementById("viewUsageBtn")
.addEventListener("click", async () => {

    showButtons("viewUsageBtns");

    await runBackendCommand("get_run_usage");

});

document.getElementById("viewDisplaySummariesBtn")
    .addEventListener("click", () => {

        showButtons("viewFilesBtns");
        setActiveFileListView({ includePdfs: false, onlyPdfs: false, recursivePdfs: false });

        const codebaseName = getSelectedCodebaseName();
        if (!codebaseName) {
            renderTextPreview("Select a codebase first from the pipeline page.");
            return;
        }
        try{
            const rootPath = `agent/file_summary_agent_output/${codebaseName}`;

            resetInsightFolderNavigation(rootPath);

            runPreviewCommand("files", {
                path: rootPath
            });
        }catch(error){
            const rootPath = `backend/agent/file_summary_agent_output/${codebaseName}`;

            resetInsightFolderNavigation(rootPath);

            runPreviewCommand("files", {
                path: rootPath
            });
        }
    });

document.getElementById("viewDisplayFilesBtn").addEventListener("click", () => {

    showButtons("viewFilesBtns");
    setActiveFileListView({ includePdfs: true, onlyPdfs: false, recursivePdfs: false });

    try{
        resetInsightFolderNavigation("agent");

        runPreviewCommand(
            "files",
            {
                path: "agent"
            }
        );
    } catch (error) {
        resetInsightFolderNavigation("backend/agent");

        runPreviewCommand(
            "files",
            {
                path: "backend/agent"
            }
        );
    }

});

document.getElementById("viewDisplayBusinessRulesBtn").addEventListener("click", () => {

    showButtons("viewBusinessRulesBtns");


    

});

document.getElementById("viewUnitTestsBtn")
    .addEventListener("click", () => {

        showButtons("viewFilesBtns");
        setActiveFileListView({ includePdfs: false, onlyPdfs: false, recursivePdfs: false });

        const codebaseName = getSelectedCodebaseName();
        if (!codebaseName) {
            renderTextPreview("Select a codebase first from the pipeline page.");
            return;
        }

        try{
            const rootPath = `agent/UT_agent_output/${codebaseName}`;

            resetInsightFolderNavigation(rootPath);

            runPreviewCommand("files", {
                path: rootPath
            });
        } catch (error) {
            const rootPath = `backend/agent/UT_agent_output/${codebaseName}`;

            resetInsightFolderNavigation(rootPath);

            runPreviewCommand("files", {
                path: rootPath
            });
        }

    });

//Hardcoded to see if outputs work
document.getElementById("validatedBusinessRulesBtn").addEventListener("click", () => {

    const codebaseName = getSelectedCodebaseName();
    if (!codebaseName) {
        renderTextPreview("Select a codebase first from the pipeline page.");
        return;
    }

    try{
        runPreviewCommand(
            "open_file",
            {
                path: `agent/BR_agent_output/${codebaseName}/validated_rules.json`
            }
        );
    } catch (error) {
        runPreviewCommand(
            "open_file",
            {
                path: `backend/agent/BR_agent_output/${codebaseName}/validated_rules.json`
            }
        );
    }


});

//hoardcoded to see if outputs work
document.getElementById("discardedBusinessRulesBtn").addEventListener("click", () => {

    const codebaseName = getSelectedCodebaseName();
    if (!codebaseName) {
        renderTextPreview("Select a codebase first from the pipeline page.");
        return;
    }

    try{
        runPreviewCommand(
            "open_file",
            {
                path: `agent/BR_agent_output/${codebaseName}/discarded_rules.json`
            }
        );
    } catch (error) {
        runPreviewCommand(
            "open_file",
            {
                path: `backend/agent/BR_agent_output/${codebaseName}/discarded_rules.json`
            }
        );
    }

});

document.getElementById('mainViewBackBtn')
    .addEventListener('click', () => {

        

        showPage('homePage');
    }); 

// UML view should surface the generated PDFs for the selected codebase.
document.getElementById('viewUMLBtn')
    .addEventListener('click', () => {

        showButtons('viewFilesBtns');
        setActiveFileListView({ includePdfs: true, onlyPdfs: true, recursivePdfs: true });

        const codebaseName = getSelectedCodebaseName();
        if (!codebaseName) {
            renderTextPreview("Select a codebase first from the pipeline page.");
            return;
        }

        try{
            const rootPath = `agent/file_summary_agent_output/${codebaseName}`;

            resetInsightFolderNavigation(rootPath);

            runPreviewCommand('files', {
                path: rootPath,
                recursivePdfs: true
            });
        } catch (error) {
            const rootPath = `backend/agent/file_summary_agent_output/${codebaseName}`;

            resetInsightFolderNavigation(rootPath);

            runPreviewCommand('files', {
                path: rootPath,
                recursivePdfs: true
            });
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

document.getElementById('estimateTokensBtn')
    .addEventListener('click', () => {

        showLoading(
            "Token Usage Estimate",
            "Scanning codebase..."
        );

        runBackendCommand(
            "estimate_tokens",
        {
            codebase:selectedCodebasePath
        });
    });

document.getElementById('tokenCalibrationBtn')
    .addEventListener('click', () => {

        showLoading(
            "Token Calibration",
            "Reading recorded usage..."
        );

        runBackendCommand(
            "token_calibration",
        {
            codebase:selectedCodebasePath
        });
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
    .addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        showLoading(
            "Unit Test Validation",
            "Preparing..."
        );

        runBackendCommand(
            "validate_unit_tests",
            {
                codebase:selectedCodebasePath,
            }
        );
    });


document.getElementById('runIntegrationTestGenerationOnlyBtn')
    .addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        showLoading(
            "Integration Test Generation",
            "Preparing..."
        );

        runBackendCommand(
            "generate_integration_tests",
            {
                codebase:selectedCodebasePath,
                selected_rules: []
            }
        );
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
            "generate_all_uml",
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
    .addEventListener('click', async () => {

        const apiKeyInputEl = document.getElementById('apiKeyInput');
        const apiKey = apiKeyInputEl.value.trim();

        // Nothing typed: saving would write a bare "GOOGLE_API_KEY=" and
        // still report success, so the app would behave as though a key
        // were set until the next launch read it back as missing. trim()
        // so a box holding only spaces counts as empty too.
        if (!apiKey) {
            showApiKeyError("Please enter an API key.");
            return;
        }

        hideApiKeyError();

        // executeCommand resolves as soon as the command has been written
        // to the backend's stdin -- its {success:true} means "sent", not
        // "worked". The real verdict arrives later on the response stream,
        // so everything that depends on it lives in onBackendResponse.
        setApiKeyPending(true);

        await runBackendCommand("set_api_key", { api_key: apiKey });

    });

document.getElementById('replaceApiKeyBtn')
    .addEventListener('click', () => {

        console.log("Replace API Key button clicked");

        // newApiUi() reveals the Back button, and it is left revealed on
        // purpose. Hiding it here stranded anyone who opened this page to
        // change a key and then thought better of it -- the only way out
        // was to enter a key that Google would accept.
        newApiUi();

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

        

        showPage('homePage');
    });

document.getElementById('faqAndSupportBackBtn')
    .addEventListener('click', () => {

        

        showPage('homePage');
    });

//======================================================
// FAQ Page Buttons
//======================================================
document.getElementById("supportBtn")
.addEventListener("click", () => {

    setFAQSupportActive("support");

    document.getElementById('faqContainer').classList.add('hidden');
    document.getElementById('supportContainer').classList.remove('hidden');
    

});


document.getElementById("faqBtn")
.addEventListener("click", () => {

    setFAQSupportActive("faq");

    // show FAQ content here
    document.getElementById('supportContainer').classList.add('hidden');
    document.getElementById('faqContainer').classList.remove('hidden');
    
    

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


});

document.getElementById("browseCodebaseBtn")
.addEventListener("click", async () => {

    const path =
        await window.electronAPI.selectCodebase();

    if (!path)
        return;

    document.getElementById("codebasePath").value = path;

    selectedCodebasePath = path;
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
    // API key save / verification result
    // ----------------------------------------
    // Handled here rather than at the Submit button because that only ever
    // sees the "command sent" acknowledgement. Taken before the generic
    // error path below so a rejected key stays on the API page with an
    // explanation instead of being dumped into the error box.
    if (response.command === "set_api_key") {

        setApiKeyPending(false);
        activeCommand = null;

        if (!response.success) {
            showApiKeyError(
                response.error || "Could not save the API key. Please try again."
            );
            return;
        }

        hasAPI = true;

        // Saved now, so there is no reason to keep it on screen.
        document.getElementById('apiKeyInput').value = "";

        showApiKeyPresent();
        document.getElementById('analysisBtn').classList.remove('unusable-btn');

        // Show what the check found -- which model answered and what it
        // cost -- before leaving the page. Navigating straight home threw
        // that away, so a verified key looked no different from no check
        // at all.
        const verdict = response.result?.message || "API key saved.";

        if (response.result?.verified === false) {
            showApiKeyError(verdict);
        } else {
            showApiKeySuccess(verdict);
        }

        setTimeout(() => {
            hideApiKeyError();
            showPage('homePage');
        }, 2500);

        return;
    }


    // The command acknowledgement does not contain the error list.
    if (activeCommand === "get_errors" && response.errors !== undefined) {

        renderErrorPreview(response.errors);
        activeCommand = null;

        return;
    }

    // Handled here, ahead of the generic error path, so a missing or
    // unreadable log shows in the Insights panel instead of leaving the page.
    if (activeCommand === "get_run_usage" && !response.type) {

        if (response.success) {
            renderRunUsage(response.run_usage);
        } else {
            renderTextPreview(response.error || "Could not load AI usage.");
        }

        activeCommand = null;

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

        } else if (response.preview.type === "pdf") {

            renderPdfPreview(
                response.preview.content
            );

        } else if (response.preview.type === "integration_tests") {

            renderIntegrationTestsPreview(
                response.preview.content
            );

        } else {

            renderJsonPreview(
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

    // ----------------------------------------
    // Live token usage
    // ----------------------------------------
    if (response.type === "token_usage") {
        updateTokenMeter(response);
        return;
    }

    if (response.type === "token_usage_stage") {
        addTokenMeterStage(response);
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
            showPage('homePage');
            activeCommand = null;

        }


        return;
    }



    // ----------------------------------------
    // Token estimate report
    // ----------------------------------------
    // Handled ahead of the generic path because the report is multi-line and
    // loadingStepMessage collapses whitespace.
    const reportCommands = ["estimate_tokens", "token_calibration"];

    if (
        reportCommands.includes(activeCommand) &&
        reportCommands.includes(response.command) &&
        response.result
    ) {

        const report =
            document.getElementById("estimateOutput");

        if (report && response.result.message) {

            report.textContent = response.result.message;
            report.classList.remove("hidden");

        }

        const low  = response.result.total_input_low;
        const high = response.result.total_input_high;

        let summary =
            response.command === "token_calibration"
                ? "Calibration complete"
                : "Estimate complete";

        if (typeof low === "number" && typeof high === "number") {

            summary =
                low === high
                    ? `~${low.toLocaleString()} input tokens`
                    : `~${low.toLocaleString()} - ${high.toLocaleString()} input tokens`;

        }

        finishLoading(summary);

        activeCommand = null;

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
    if (response.success) {

        if (
            response.individualStep === true ||
            response.result ||
            response.message
        ) {

            finishLoading(
                response.result?.message ||
                response.message ||
                `${activeCommand} completed`
            );

            showLoadingWarning(response.result?.warning);

            activeCommand = null;
        }
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

function setApiKeyPending(pending) {

    const btn = document.getElementById('submitApiKeyBtn');

    if (!btn) return;

    btn.disabled = pending;
    btn.textContent = pending ? "Verifying..." : "Submit";

}


function showApiKeySuccess(text) {

    const el = document.getElementById('apiKeyErrorMsg');

    if (!el) return;

    el.textContent = text;
    el.classList.remove("api-key-error");
    el.classList.add("api-key-ok");
    el.classList.remove("hidden");

}


function showApiKeyError(text) {

    const el = document.getElementById('apiKeyErrorMsg');

    if (!el) return;

    el.textContent = text;
    el.classList.remove("api-key-ok");
    el.classList.add("api-key-error");
    el.classList.remove("hidden");

}


function hideApiKeyError() {

    const el = document.getElementById('apiKeyErrorMsg');

    if (el) el.classList.add("hidden");

}


function showApiKeyPresent() {

    const apiBtnEl = document.getElementById("apiBtn");

    if (!apiBtnEl) return;

    // Deliberately NOT .unusable-btn. That class is cosmetic -- it only
    // fades the button and shows a not-allowed cursor -- but this button
    // is the only route to the Replace / Keep page, so looking disabled
    // made a stale key appear unchangeable. Relabel instead of greying.
    apiBtnEl.classList.remove("unusable-btn");
    apiBtnEl.textContent = "Change API Key";

}


function overwriteApiUi() {
    hideApiKeyError();

    document.getElementById('apiKeyMsg').classList.remove("hidden");
    document.getElementById('apiKeyInput').classList.add("hidden");
    document.getElementById('submitApiKeyBtn').classList.add("hidden");
    document.getElementById('replaceApiKeyBtn').classList.remove("hidden");            
    document.getElementById('keepApiKeyBtn').classList.remove("hidden");
    document.getElementById('apiBackBtn').classList.add("hidden");
}

function newApiUi() {
    document.getElementById('apiKeyMsg').classList.add("hidden");

    // Start empty every time. Pages here are shown/hidden rather than
    // reloaded, so whatever the last person typed would otherwise still
    // be sitting in the box when someone opens it to change the key.
    document.getElementById('apiKeyInput').value = "";

    hideApiKeyError();

    document.getElementById('apiKeyInput').classList.remove("hidden");
    document.getElementById('submitApiKeyBtn').classList.remove("hidden");
    document.getElementById('replaceApiKeyBtn').classList.add("hidden");
    document.getElementById('keepApiKeyBtn').classList.add("hidden");
    document.getElementById('apiBackBtn').classList.remove("hidden");
}

function renderJsonPreview(content) {

    const output = document.getElementById("viewDisplayOutputBox");

    if (!output) return;

    output.innerHTML = "";

    const card = document.createElement("div");
    card.className = "json-card";

    const title = document.createElement("h2");
    title.className = "json-title";
    title.textContent = "JSON Preview";

    const pre = document.createElement("pre");
    pre.className = "json-body";

    let pretty = "";

    try {
        if (typeof content === 'string') {
            pretty = JSON.stringify(JSON.parse(content), null, 2);
        } else {
            pretty = JSON.stringify(content, null, 2);
        }
    } catch (e) {
        // not JSON, show raw text
        pretty = String(content || "");
    }

    pre.textContent = pretty;

    card.appendChild(title);
    card.appendChild(pre);

    output.appendChild(card);

}

function renderIntegrationTestsPreview(workflows) {

    const output = document.getElementById("viewDisplayOutputBox");

    if (!output) return;

    output.innerHTML = "";

    const rootCard = document.createElement("div");
    rootCard.className = "integration-tests-card";

    const title = document.createElement("h2");
    title.className = "integration-tests-title";
    title.textContent = "Integration Test Workflows";
    rootCard.appendChild(title);

    const items = Array.isArray(workflows) ? workflows : [];

    if (items.length === 0) {
        const empty = document.createElement("pre");
        empty.className = "integration-test-description";
        empty.textContent = "No integration tests were found.";
        rootCard.appendChild(empty);
        output.appendChild(rootCard);
        return;
    }

    items.forEach((workflow, idx) => {
        const section = document.createElement("section");
        section.className = "integration-test-workflow";

        const heading = document.createElement("h3");
        heading.className = "integration-test-workflow-title";
        heading.textContent = `${idx + 1}. ${workflow.workflow_name || "Workflow"}`;
        section.appendChild(heading);

        if (workflow.workflow_description) {
            const descHeader = document.createElement("h4");
            descHeader.className = "integration-test-section-header";
            descHeader.textContent = "Description";
            section.appendChild(descHeader);

            const desc = document.createElement("pre");
            desc.className = "integration-test-description";
            desc.textContent = workflow.workflow_description;
            section.appendChild(desc);
        }

        const ruleIds = Array.isArray(workflow.rule_ids)
            ? workflow.rule_ids
            : [];

        if (ruleIds.length > 0) {
            const ruleHeader = document.createElement("h4");
            ruleHeader.className = "integration-test-section-header";
            ruleHeader.textContent = "Rule IDs";
            section.appendChild(ruleHeader);

            const ruleBody = document.createElement("pre");
            ruleBody.className = "integration-test-description";
            ruleBody.textContent = ruleIds.join(", ");
            section.appendChild(ruleBody);
        }

        const imports = Array.isArray(workflow.imports)
            ? workflow.imports
            : [];

        if (imports.length > 0) {
            const importsHeader = document.createElement("h4");
            importsHeader.className = "integration-test-section-header";
            importsHeader.textContent = "Imports";
            section.appendChild(importsHeader);

            const importsBody = document.createElement("pre");
            importsBody.className = "integration-test-description";
            importsBody.textContent = imports.map(item => `• ${item}`).join("\n");
            section.appendChild(importsBody);
        }

        const codeHeader = document.createElement("h4");
        codeHeader.className = "integration-test-section-header";
        codeHeader.textContent = "Integration Test";
        section.appendChild(codeHeader);

        const code = document.createElement("pre");
        code.className = "integration-test-code";
        code.textContent = workflow.integration_test || "";
        section.appendChild(code);

        rootCard.appendChild(section);
    });

    output.appendChild(rootCard);
}