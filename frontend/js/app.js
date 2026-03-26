/**
 * DocExtract - Frontend Application
 * Handles file upload, SSE streaming, results display, and CSV preview.
 */

let currentJobId = null;
let selectedFiles = [];
let eventSource = null;

// ============================================================
// Initialization
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    setupDragDrop();
    setupFileInput();
});

// ============================================================
// Health Check
// ============================================================

async function checkHealth() {
    try {
        const res = await fetch('/health');
        const data = await res.json();
        const dot = document.getElementById('health-dot');
        const text = document.getElementById('health-text');

        if (data.status === 'healthy') {
            dot.className = 'w-2 h-2 rounded-full bg-green-400';
            text.textContent = 'System Ready';
            text.className = 'text-green-400 text-sm';
        } else {
            dot.className = 'w-2 h-2 rounded-full bg-yellow-400';
            text.textContent = 'Degraded';
            text.className = 'text-yellow-400 text-sm';
        }
    } catch {
        const dot = document.getElementById('health-dot');
        const text = document.getElementById('health-text');
        dot.className = 'w-2 h-2 rounded-full bg-red-400';
        text.textContent = 'Offline';
        text.className = 'text-red-400 text-sm';
    }
}

// ============================================================
// Drag & Drop
// ============================================================

function setupDragDrop() {
    const dropzone = document.getElementById('dropzone');

    ['dragenter', 'dragover'].forEach(evt => {
        dropzone.addEventListener(evt, e => {
            e.preventDefault();
            dropzone.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(evt => {
        dropzone.addEventListener(evt, e => {
            e.preventDefault();
            dropzone.classList.remove('drag-over');
        });
    });

    dropzone.addEventListener('drop', e => {
        const files = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
        if (files.length > 0) {
            addFiles(files);
        }
    });
}

function setupFileInput() {
    document.getElementById('file-input').addEventListener('change', e => {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            addFiles(files);
        }
    });
}

function addFiles(files) {
    selectedFiles = [...selectedFiles, ...files];
    renderFileList();
    document.getElementById('upload-btn').classList.remove('hidden');
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    renderFileList();
    if (selectedFiles.length === 0) {
        document.getElementById('upload-btn').classList.add('hidden');
    }
}

function renderFileList() {
    const container = document.getElementById('file-list');
    container.classList.remove('hidden');
    container.innerHTML = selectedFiles.map((f, i) => `
        <div class="file-item flex items-center justify-between bg-surface rounded-lg px-4 py-2 border border-gray-800">
            <div class="flex items-center gap-3">
                <svg class="w-5 h-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"/>
                </svg>
                <span class="text-sm text-gray-200">${f.name}</span>
                <span class="text-xs text-gray-500">${(f.size / 1024).toFixed(0)} KB</span>
            </div>
            <button onclick="removeFile(${i})" class="text-gray-500 hover:text-red-400 transition-colors">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </button>
        </div>
    `).join('');
}

// ============================================================
// Upload & Processing
// ============================================================

async function startUpload() {
    if (selectedFiles.length === 0) return;

    const formData = new FormData();
    selectedFiles.forEach(f => formData.append('files', f));

    // Show progress, hide upload
    document.getElementById('upload-btn').classList.add('hidden');
    document.getElementById('progress-section').classList.remove('hidden');
    document.getElementById('results-section').classList.remove('hidden');

    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        if (!res.ok) {
            const err = await res.json();
            alert(`Upload failed: ${err.detail || 'Unknown error'}`);
            return;
        }

        const data = await res.json();
        currentJobId = data.job_id;

        // Initialize progress rows
        initProgressRows();

        // Connect SSE
        connectSSE(data.job_id);
    } catch (err) {
        alert(`Upload error: ${err.message}`);
    }
}

function initProgressRows() {
    const container = document.getElementById('progress-details');
    container.innerHTML = selectedFiles.map(f => `
        <div class="flex items-center gap-4" id="prog-${sanitize(f.name)}">
            <span class="text-sm text-gray-300 w-48 truncate">${f.name}</span>
            <div class="flex-1 bg-gray-800 rounded-full h-1.5">
                <div class="bg-gray-600 h-1.5 rounded-full transition-all duration-500" style="width:0%" data-bar></div>
            </div>
            <span class="text-xs text-gray-500 w-24 text-right stage-active" data-stage>Queued</span>
        </div>
    `).join('');
}

// ============================================================
// SSE Connection
// ============================================================

function connectSSE(jobId) {
    eventSource = new EventSource(`/api/jobs/${jobId}/stream`);

    eventSource.addEventListener('status', e => {
        const data = JSON.parse(e.data);
        updateProgress(data);
    });

    eventSource.addEventListener('classification', e => {
        const data = JSON.parse(e.data);
        updateClassification(data);
    });

    eventSource.addEventListener('extraction', e => {
        const data = JSON.parse(e.data);
        updateExtraction(data);
    });

    eventSource.addEventListener('file_completed', e => {
        const data = JSON.parse(e.data);
        markFileComplete(data);
    });

    eventSource.addEventListener('completed', e => {
        const data = JSON.parse(e.data);
        onJobCompleted(data);
        eventSource.close();
    });

    eventSource.addEventListener('error', e => {
        try {
            const data = JSON.parse(e.data);
            console.warn('Processing error:', data);
        } catch {
            // SSE connection error
        }
    });

    eventSource.onerror = () => {
        // Reconnect logic - fetch canonical state
        setTimeout(() => fetchJobState(jobId), 2000);
    };
}

// ============================================================
// Progress Updates
// ============================================================

const STAGE_LABELS = {
    converting: 'Converting PDF...',
    preprocessing: 'Preprocessing...',
    ocr: 'Running OCR...',
    classifying: 'Classifying...',
    extracting: 'Extracting data...',
    generating_csv: 'Generating CSV...',
};

function updateProgress(data) {
    // Update overall progress bar
    const pct = data.progress_pct || 0;
    document.getElementById('progress-bar').style.width = `${pct}%`;
    document.getElementById('progress-pct').textContent = `${pct}%`;

    // Update per-file progress
    if (data.current_file) {
        const row = document.getElementById(`prog-${sanitize(data.current_file)}`);
        if (row) {
            const stage = row.querySelector('[data-stage]');
            stage.textContent = STAGE_LABELS[data.current_stage] || data.current_stage;

            const stageMap = { converting: 10, preprocessing: 25, ocr: 45, classifying: 65, extracting: 85 };
            const bar = row.querySelector('[data-bar]');
            const width = stageMap[data.current_stage] || 0;
            bar.style.width = `${width}%`;
            bar.className = `bg-accent h-1.5 rounded-full transition-all duration-500 ${width < 100 ? 'progress-shimmer' : ''}`;
        }
    }
}

function updateClassification(data) {
    // Add or update result row
    addResultRow(data.filename, data.doc_type, data.confidence);
}

function updateExtraction(data) {
    updateResultRow(data.filename, data.fields_extracted, data.preview);
}

function markFileComplete(data) {
    const row = document.getElementById(`prog-${sanitize(data.filename)}`);
    if (row) {
        const stage = row.querySelector('[data-stage]');
        stage.textContent = 'Done';
        stage.classList.remove('stage-active');
        stage.classList.add('text-green-400');

        const bar = row.querySelector('[data-bar]');
        bar.style.width = '100%';
        bar.classList.remove('progress-shimmer');
        bar.classList.add('bg-green-500');
    }
}

// ============================================================
// Results Table
// ============================================================

function addResultRow(filename, docType, confidence) {
    const tbody = document.getElementById('results-body');
    const id = `result-${sanitize(filename)}`;

    if (document.getElementById(id)) return; // Already exists

    const confPct = Math.round(confidence * 100);
    const confClass = confPct >= 80 ? 'conf-high' : confPct >= 50 ? 'conf-medium' : 'conf-low';

    const row = document.createElement('tr');
    row.id = id;
    row.className = 'cursor-pointer';
    row.innerHTML = `
        <td class="px-6 py-4 text-sm text-gray-200">${filename}</td>
        <td class="px-6 py-4"><span class="badge badge-${docType}">${formatDocType(docType)}</span></td>
        <td class="px-6 py-4 text-sm text-gray-400" data-pages>--</td>
        <td class="px-6 py-4 text-sm text-gray-400" data-fields>--</td>
        <td class="px-6 py-4">
            <div class="flex items-center gap-2">
                <div class="w-16 bg-gray-800 rounded-full h-1.5">
                    <div class="${confClass} h-1.5 rounded-full" style="width:${confPct}%"></div>
                </div>
                <span class="text-xs text-gray-400">${confPct}%</span>
            </div>
        </td>
        <td class="px-6 py-4"><span class="text-xs text-yellow-400">Extracting...</span></td>
    `;
    tbody.appendChild(row);
}

function updateResultRow(filename, fieldsCount, preview) {
    const row = document.getElementById(`result-${sanitize(filename)}`);
    if (!row) return;

    const fieldsCell = row.querySelector('[data-fields]');
    if (fieldsCell) fieldsCell.textContent = fieldsCount;

    const statusCell = row.querySelector('td:last-child');
    statusCell.innerHTML = '<span class="text-xs text-green-400">Complete</span>';
}

// ============================================================
// Job Completion
// ============================================================

function onJobCompleted(data) {
    // Update progress bar to 100%
    document.getElementById('progress-bar').style.width = '100%';
    document.getElementById('progress-bar').classList.remove('progress-shimmer');
    document.getElementById('progress-bar').classList.add('bg-green-500');
    document.getElementById('progress-pct').textContent = '100%';

    // Show download buttons
    document.getElementById('result-actions').classList.remove('hidden');

    // Show metrics
    showMetrics(data.metrics);

    // Fetch final job state for complete data
    fetchJobState(currentJobId);
}

function showMetrics(metrics) {
    if (!metrics) return;
    document.getElementById('metrics-section').classList.remove('hidden');
    document.getElementById('metric-time').textContent = `${metrics.total_time_seconds}s`;
    document.getElementById('metric-docs').textContent = selectedFiles.length;
    document.getElementById('metric-tokens').textContent = (
        (metrics.tokens_used.input || 0) + (metrics.tokens_used.output || 0)
    ).toLocaleString();
    document.getElementById('metric-cost').textContent = `$${metrics.estimated_cost_usd.toFixed(4)}`;
}

async function fetchJobState(jobId) {
    try {
        const res = await fetch(`/api/jobs/${jobId}`);
        const job = await res.json();

        // Update page counts in results
        job.documents?.forEach(doc => {
            const row = document.getElementById(`result-${sanitize(doc.filename)}`);
            if (row) {
                const pagesCell = row.querySelector('[data-pages]');
                if (pagesCell) pagesCell.textContent = doc.page_count;
            }
        });

        if (job.status === 'completed') {
            showMetrics(job.metrics);
            loadCSVPreview(jobId);
        }
    } catch (err) {
        console.error('Failed to fetch job state:', err);
    }
}

// ============================================================
// CSV Preview
// ============================================================

async function loadCSVPreview(jobId) {
    document.getElementById('csv-preview-section').classList.remove('hidden');
    try {
        const res = await fetch(`/api/jobs/${jobId}/download/csv`);
        const contentType = res.headers.get('content-type');

        if (contentType?.includes('text/csv')) {
            const text = await res.text();
            window._csvData = { summary: text, transactions: null };
            renderCSVTable(text);
        }
        // For zip files, we just show a message
    } catch {
        document.getElementById('csv-preview-content').innerHTML =
            '<p class="text-gray-500">Download the CSV to view extracted data.</p>';
    }
}

function renderCSVTable(csvText) {
    const lines = csvText.trim().split('\n');
    if (lines.length < 2) return;

    const headers = parseCSVLine(lines[0]);
    const rows = lines.slice(1).map(parseCSVLine);

    let html = '<table class="w-full text-sm"><thead class="bg-gray-800/50"><tr>';
    headers.forEach(h => {
        html += `<th class="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase">${h}</th>`;
    });
    html += '</tr></thead><tbody class="divide-y divide-gray-800">';

    rows.forEach(row => {
        html += '<tr>';
        row.forEach(cell => {
            html += `<td class="px-4 py-2 text-gray-300 whitespace-nowrap">${cell}</td>`;
        });
        html += '</tr>';
    });
    html += '</tbody></table>';

    document.getElementById('csv-preview-content').innerHTML = html;
}

function parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"') {
            inQuotes = !inQuotes;
        } else if (ch === ',' && !inQuotes) {
            result.push(current.trim());
            current = '';
        } else {
            current += ch;
        }
    }
    result.push(current.trim());
    return result;
}

function showPreview(type) {
    document.getElementById('btn-summary').className =
        type === 'summary' ? 'px-3 py-1 rounded-lg text-sm bg-accent text-white' :
        'px-3 py-1 rounded-lg text-sm bg-gray-700 text-gray-300 hover:bg-gray-600';
    document.getElementById('btn-transactions').className =
        type === 'transactions' ? 'px-3 py-1 rounded-lg text-sm bg-accent text-white' :
        'px-3 py-1 rounded-lg text-sm bg-gray-700 text-gray-300 hover:bg-gray-600';
}

// ============================================================
// Downloads
// ============================================================

function downloadCSV() {
    if (currentJobId) {
        window.location.href = `/api/jobs/${currentJobId}/download/csv`;
    }
}

function downloadReport() {
    if (currentJobId) {
        window.open(`/api/jobs/${currentJobId}/download/report`, '_blank');
    }
}

// ============================================================
// Reset
// ============================================================

function resetUI() {
    currentJobId = null;
    selectedFiles = [];
    if (eventSource) eventSource.close();

    document.getElementById('file-list').classList.add('hidden');
    document.getElementById('file-list').innerHTML = '';
    document.getElementById('upload-btn').classList.add('hidden');
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('results-section').classList.add('hidden');
    document.getElementById('metrics-section').classList.add('hidden');
    document.getElementById('csv-preview-section').classList.add('hidden');
    document.getElementById('result-actions').classList.add('hidden');
    document.getElementById('results-body').innerHTML = '';
    document.getElementById('progress-details').innerHTML = '';
    document.getElementById('progress-bar').style.width = '0%';
    document.getElementById('progress-bar').className = 'bg-accent h-2 rounded-full transition-all duration-500';
    document.getElementById('progress-pct').textContent = '0%';
    document.getElementById('file-input').value = '';
}

// ============================================================
// Helpers
// ============================================================

function sanitize(name) {
    return name.replace(/[^a-zA-Z0-9]/g, '_');
}

function formatDocType(type) {
    const labels = {
        bank_statement: 'Bank Statement',
        invoice: 'Invoice',
        receipt: 'Receipt',
        kyc_document: 'KYC Document',
        unknown: 'Unknown',
    };
    return labels[type] || type;
}
