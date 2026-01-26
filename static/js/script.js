document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const progressContainer = document.getElementById('progress-container');
    const resultContainer = document.getElementById('result-container');
    const uploadContent = document.querySelector('.upload-content');
    const openBtn = document.getElementById('open-btn');
    const downloadBtn = document.getElementById('download-btn');
    const cookiePill = document.getElementById('cookie-pill');
    const acceptCookies = document.getElementById('accept-cookies');

    // Cookie Consent
    if (cookiePill && !localStorage.getItem('cookies-accepted')) {
        setTimeout(() => cookiePill.classList.remove('hidden'), 2000);
    }

    if (acceptCookies) {
        acceptCookies.addEventListener('click', () => {
            localStorage.setItem('cookies-accepted', 'true');
            cookiePill.classList.add('hidden');
        });
    }

    if (!dropZone) return;

    // Drag and Drop Events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        dropZone.classList.add('drag-over');
    }

    function unhighlight(e) {
        dropZone.classList.remove('drag-over');
    }

    // Handle Drop
    dropZone.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    // Handle Click
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', () => {
        handleFiles(fileInput.files);
    });

    function handleFiles(files) {
        if (files.length > 0) {
            uploadFile(files[0]);
        }
    }

    function uploadFile(file) {
        // UI Reset
        resultContainer.classList.add('hidden');
        uploadContent.classList.add('hidden');
        progressContainer.classList.remove('hidden');

        const formData = new FormData();
        formData.append('file', file);

        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.detail || 'Upload failed') });
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                // Backend returns raw HTML string now
                showResult(data.report_html);
            } else {
                alert('Analysis failed: ' + (data.message || 'Unknown error'));
                resetUI();
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred: ' + error.message);
            resetUI();
        });
    }

    function showResult(htmlContent) {
        progressContainer.classList.add('hidden');
        resultContainer.classList.remove('hidden');
        
        // Create a Blob from the HTML content
        const blob = new Blob([htmlContent], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        
        openBtn.href = url;
        downloadBtn.href = url;
        // Set download attribute for download button
        downloadBtn.download = 'analysis_report.html';
    }

    function resetUI() {
        progressContainer.classList.add('hidden');
        uploadContent.classList.remove('hidden');
        fileInput.value = ''; // Reset input
    }
});
