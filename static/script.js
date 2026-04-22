// Auto-resize textarea
const messageInput = document.getElementById('messageInput');
const messagesContainer = document.getElementById('messages');
const sendButton = document.getElementById('sendButton');

if (messageInput) {
    messageInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });
}

// Handle key press
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage(event);
    }
}

// Send message
async function sendMessage(event) {
    event.preventDefault();

    const message = messageInput.value.trim();
    if (!message) return;

    // Disable input while processing
    messageInput.disabled = true;
    sendButton.disabled = true;

    // Add user message to chat
    addMessage('user', message);

    // Clear input
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Show processing message
    const agentMessageId = addMessage('agent', 'Processing your request...', 'processing');

    try {
        // Send to API
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message })
        });

        if (!response.ok) {
            throw new Error('Failed to send message');
        }

        // Poll for updates
        pollForUpdates(agentMessageId);
    } catch (error) {
        updateMessage(agentMessageId, `❌ Error: ${error.message}`, 'failed');
        messageInput.disabled = false;
        sendButton.disabled = false;
    }
}

// Add message to chat
let messageCounter = 0;  // Counter to ensure unique IDs
function addMessage(type, text, status = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    const messageId = `msg-${Date.now()}-${messageCounter++}`;
    messageDiv.id = messageId;

    const avatarDiv = document.createElement('div');
    avatarDiv.className = `message-avatar ${type}-avatar`;

    if (type === 'user') {
        avatarDiv.innerHTML = `
            <svg width="24" height="24" fill="currentColor">
                <circle cx="12" cy="8" r="4"/>
                <path d="M4 20c0-4 4-6 8-6s8 2 8 6"/>
            </svg>
        `;
    } else {
        // Agent avatar uses ONLY the idle video as requested
        avatarDiv.innerHTML = `
            <video class="avatar-video" autoplay loop muted playsinline>
                <source src="/static/bot_idle.mp4" type="video/mp4">
            </video>
        `;
    }

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    const headerDiv = document.createElement('div');
    headerDiv.className = 'message-header';
    headerDiv.innerHTML = `
        <span class="message-sender">${type === 'user' ? 'You' : 'Patch Agent'}</span>
        <span class="message-time">${formatTime(new Date())}</span>
    `;

    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.innerHTML = formatMessage(text);

    contentDiv.appendChild(headerDiv);
    contentDiv.appendChild(textDiv);

    if (status) {
        const badge = createStatusBadge(status);
        if (badge) {
            contentDiv.appendChild(badge);
        }
    }

    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    return messageId;
}

// Update existing message
function updateMessage(messageId, text, status = null, logs = []) {
    const messageDiv = document.getElementById(messageId);
    if (!messageDiv) return;

    const textDiv = messageDiv.querySelector('.message-text');
    textDiv.innerHTML = formatMessage(text);

    // Update status badge
    const existingBadge = messageDiv.querySelector('.status-badge');
    if (existingBadge) {
        existingBadge.remove();
    }

    if (status) {
        const badge = createStatusBadge(status);
        if (badge) {
            messageDiv.querySelector('.message-content').appendChild(badge);
        }
    }

    // Update or add logs display
    let logsContainer = messageDiv.querySelector('.agent-logs');
    if (logs && logs.length > 0) {
        if (!logsContainer) {
            logsContainer = document.createElement('div');
            logsContainer.className = 'agent-logs';
            messageDiv.querySelector('.message-content').appendChild(logsContainer);
        }

        // Only add new logs (incremental)
        const currentLogCount = logsContainer.children.length;
        for (let i = currentLogCount; i < logs.length; i++) {
            const log = logs[i];
            const logDiv = document.createElement('div');
            logDiv.className = `log-entry log-${log.level.toLowerCase()}`;
            logDiv.innerHTML = `
                <span class="log-icon">▸</span>
                <span class="log-text">${escapeHtml(log.message)}</span>
            `;
            logsContainer.appendChild(logDiv);

            // Animate in
            setTimeout(() => {
                logDiv.classList.add('visible');
            }, 50);
        }

        // Auto-scroll logs container to bottom
        setTimeout(() => {
            logsContainer.scrollTop = logsContainer.scrollHeight;
        }, 100);
    }

    // Auto-scroll main messages container to show latest message
    setTimeout(() => {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }, 100);
}

// Helper to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Create status badge
function createStatusBadge(status) {
    // No badge for chat/conversational responses
    if (status === 'chat') {
        return null;
    }

    const badge = document.createElement('div');
    badge.className = `status-badge status-${status}`;

    if (status === 'processing') {
        badge.innerHTML = `
            <div class="spinner"></div>
            <span>Processing...</span>
        `;
    } else if (status === 'success') {
        badge.innerHTML = '✅ Success';
    } else if (status === 'failed' || status === 'error') {
        badge.innerHTML = '❌ Failed';
    }

    return badge;
}

// Format message text
function formatMessage(text) {
    // Convert markdown-like syntax to HTML
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/`(.*?)`/g, '<code>$1</code>');

    // Convert line breaks
    text = text.replace(/\n/g, '<br>');

    // Wrap in paragraph
    if (!text.startsWith('<')) {
        text = `<p>${text}</p>`;
    }

    return text;
}

// Format time
function formatTime(date) {
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
}

// Clear chat
async function clearChat() {
    if (!confirm('Are you sure you want to clear the chat history?')) {
        return;
    }

    try {
        const response = await fetch('/api/clear', {
            method: 'POST'
        });

        if (response.ok) {
            // Clear all messages except the welcome message
            const messages = messagesContainer.querySelectorAll('.message');
            messages.forEach((msg, index) => {
                if (index > 0) {  // Keep the first welcome message
                    msg.remove();
                }
            });
        }
    } catch (error) {
        console.error('Clear error:', error);
    }
}

// Poll for updates
let pollInterval;
function pollForUpdates(messageId) {
    let lastLogCount = 0;
    let lastStatus = 'processing';
    let pollCount = 0;
    const MAX_POLLS = 600; // 5 minutes max

    pollInterval = setInterval(async () => {
        pollCount++;

        // Safety timeout
        if (pollCount > MAX_POLLS) {
            console.warn('Polling timeout reached');
            clearInterval(pollInterval);
            updateMessage(messageId, '⚠️ Request timed out. Please try again.', 'failed');
            messageInput.disabled = false;
            sendButton.disabled = false;
            return;
        }

        try {
            const response = await fetch('/api/history');
            const data = await response.json();

            // Find the latest agent message
            const agentMessages = data.history.filter(msg => msg.type === 'agent');
            if (agentMessages.length > 0) {
                const latestMessage = agentMessages[agentMessages.length - 1];

                // Track log count
                const currentLogCount = latestMessage.logs ? latestMessage.logs.length : 0;

                // Check if status changed OR logs changed
                if (latestMessage.status !== lastStatus || currentLogCount > lastLogCount) {
                    lastStatus = latestMessage.status;
                    lastLogCount = currentLogCount;

                    updateMessage(
                        messageId,
                        latestMessage.message,
                        latestMessage.status,
                        latestMessage.logs || []
                    );

                    // Stop polling if status is final
                    if (latestMessage.status !== 'processing') {
                        clearInterval(pollInterval);
                        messageInput.disabled = false;
                        sendButton.disabled = false;
                        messageInput.focus();
                        // No state change logic needed here
                    }
                }
            }
        } catch (error) {
            console.error('Polling error:', error);
            if (pollCount > 10) {
                clearInterval(pollInterval);
                messageInput.disabled = false;
                sendButton.disabled = false;
            }
        }
    }, 500);
}

// Auto-focus on input
if (messageInput) messageInput.focus();
