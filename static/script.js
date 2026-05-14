// Global variables
let currentDocuments = [];
let responseStartTime = null;
let timerInterval = null;

// DOM elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const uploadStatus = document.getElementById('uploadStatus');
const documentsList = document.getElementById('documentsList');
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendButton = document.getElementById('sendButton');
const sendButtonText = document.getElementById('sendButtonText');
const sendSpinner = document.getElementById('sendSpinner');
const loadingIndicator = document.getElementById('loadingIndicator');
const responseTimer = document.getElementById('responseTimer');
const imageModal = document.getElementById('imageModal');
const modalImage = document.getElementById('modalImage');
const modalClose = document.querySelector('.close');
const themeToggle = document.getElementById('themeToggle');

// Add spinner element to the DOM
const uploadSpinner = document.createElement('div');
uploadSpinner.id = 'uploadSpinner';
uploadSpinner.className = 'hidden';
uploadSpinner.innerHTML = '<div class="spinner"></div><p>Uploading...</p>';
document.body.appendChild(uploadSpinner);

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadDocuments();
    loadTheme();
});

function loadTheme() {
    const theme = localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeIcon(theme);
}

function toggleTheme() {
    let theme = document.documentElement.getAttribute('data-theme');
    theme = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    updateThemeIcon(theme);
}

function updateThemeIcon(theme) {
    const themeIcon = document.getElementById('themeIcon');
    if (themeIcon) {
        themeIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
}

// Event listeners
function setupEventListeners() {
    // Upload area events
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);
    
    // File input
    fileInput.addEventListener('change', handleFileSelect);
    
    // Chat events
    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Modal events
    modalClose.addEventListener('click', closeModal);
    imageModal.addEventListener('click', (e) => {
        if (e.target === imageModal) {
            closeModal();
        }
    });
    
    // Escape key to close modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
        }
    });

    // Theme toggle
    themeToggle.addEventListener('click', toggleTheme);
}

// File upload handlers
function handleDragOver(e) {
    e.preventDefault();
    uploadArea.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        handleFile(file);
    }
}

async function handleFile(file) {
    // Validate file type
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showUploadStatus('Please upload a PDF file', 'error');
        return;
    }

    // Show spinner
    uploadSpinner.classList.remove('hidden');
    showUploadStatus('Uploading and processing document...', 'success');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            showUploadStatus(
                `✅ ${result.message} (${result.chunks_processed} chunks processed)`,
                'success'
            );
            clearWelcomeMessage();
            loadDocuments();
        } else {
            showUploadStatus(`❌ Error: ${result.detail}`, 'error');
        }
    } catch (error) {
        showUploadStatus(`❌ Upload failed: ${error.message}`, 'error');
    } finally {
        // Hide spinner
        uploadSpinner.classList.add('hidden');
    }
}

function showUploadStatus(message, type) {
    uploadStatus.textContent = message;
    uploadStatus.className = `upload-status ${type}`;
    uploadStatus.style.display = 'block';
    
    // Auto-hide success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            uploadStatus.style.display = 'none';
        }, 5000);
    }
}

// Document management
async function loadDocuments() {
    try {
        const response = await fetch('/documents');
        const data = await response.json();
        currentDocuments = data.documents;
        renderDocuments();
    } catch (error) {
        console.error('Failed to load documents:', error);
    }
}

function renderDocuments() {
    if (currentDocuments.length === 0) {
        documentsList.innerHTML = '<p class="no-documents">No documents uploaded yet</p>';
        return;
    }

    console.log('Rendering documents:', currentDocuments); // Log document names

    documentsList.innerHTML = currentDocuments.map(doc => `
        <div class="document-item">
            <div class="document-info">
                <span class="document-icon">📄</span>
                <span class="document-name">${escapeHtml(doc)}</span>
            </div>
            <button class="delete-btn" onclick="deleteDocument('${escapeHtml(doc)}')">Delete</button>
        </div>
    `).join('');
}

async function deleteDocument(documentName) {
    console.log('Deleting document:', documentName);
    
    if (!confirm(`Are you sure you want to delete "${documentName}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/documents/${encodeURIComponent(documentName)}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadDocuments();
        } else {
            alert('Failed to delete document');
        }
    } catch (error) {
        alert('Failed to delete document: ' + error.message);
    }
}

// Chat functionality
function clearWelcomeMessage() {
    const welcomeMessage = chatMessages.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }
}

async function sendMessage() {
    const message = chatInput.value.trim();
    if (!message) return;

    // Add user message to chat
    addMessage(message, 'user');
    chatInput.value = '';

    // Show loading state
    sendButton.disabled = true;
    sendButtonText.classList.add('hidden');
    sendSpinner.classList.remove('hidden');
    loadingIndicator.classList.remove('hidden');

    // Start timer
    responseStartTime = Date.now();
    timerInterval = setInterval(updateTimer, 100);

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message
            })
        });

        const data = await response.json();

        if (response.ok) {
            const responseTime = ((Date.now() - responseStartTime) / 1000).toFixed(2);
            addMessage(data.response, 'assistant', data.images, data.relevant_chunks, responseTime);
        } else {
            addMessage(`Error: ${data.detail || 'Failed to get response'}`, 'assistant');
        }
    } catch (error) {
        addMessage(`Connection error: ${error.message}`, 'assistant');
    } finally {
        // Stop timer
        clearInterval(timerInterval);
        timerInterval = null;

        // Hide loading state
        sendButton.disabled = false;
        sendButtonText.classList.remove('hidden');
        sendSpinner.classList.add('hidden');
        loadingIndicator.classList.add('hidden');
        responseTimer.textContent = '0.0s';
    }
}

function updateTimer() {
    if (responseStartTime) {
        const elapsed = ((Date.now() - responseStartTime) / 1000).toFixed(1);
        responseTimer.textContent = `${elapsed}s`;
    }
}

function addMessage(content, sender, images = [], relevantChunks = [], responseTime = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = sender === 'user' ? '👤' : '🤖';

    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';

    // Add text content
    const textContent = document.createElement('div');
    textContent.textContent = content;
    messageContent.appendChild(textContent);

    // Add response time if available (for assistant messages)
    if (responseTime && sender === 'assistant') {
        const timeInfo = document.createElement('div');
        timeInfo.className = 'response-time-info';
        timeInfo.textContent = `⏱️ Response time: ${responseTime}s`;
        messageContent.appendChild(timeInfo);
    }

    // Add images if available
    if (images && images.length > 0) {
        const imagesContainer = document.createElement('div');
        imagesContainer.className = 'message-images';

        images.forEach(image => {
            const imageDiv = document.createElement('div');
            imageDiv.className = 'message-image';
            imageDiv.onclick = () => openImageModal(image.path, image.caption);

            const img = document.createElement('img');
            img.src = image.thumbnail || image.path;
            img.alt = image.caption || 'Document image';
            img.onerror = () => {
                // If thumbnail fails, try original image
                img.src = image.path;
            };

            imageDiv.appendChild(img);
            imagesContainer.appendChild(imageDiv);
        });

        messageContent.appendChild(imagesContainer);
    }

    // Add relevant chunks info (for debugging, can be hidden in production)
    if (relevantChunks && relevantChunks.length > 0) {
        const chunksInfo = document.createElement('div');
        chunksInfo.style.fontSize = '0.8rem';
        chunksInfo.style.color = '#a0aec0';
        chunksInfo.style.marginTop = '10px';
        chunksInfo.innerHTML = `<em>Sources: ${relevantChunks.map(c => c.source_document).join(', ')}</em>`;
        messageContent.appendChild(chunksInfo);
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(messageContent);

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Image modal
function openImageModal(imagePath, caption) {
    modalImage.src = imagePath;
    modalImage.alt = caption || 'Document image';

    const captionDiv = imageModal.querySelector('.image-caption');
    captionDiv.textContent = caption || '';

    imageModal.style.display = 'block';
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    imageModal.style.display = 'none';
    document.body.style.overflow = 'auto';
}

// Utility functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
