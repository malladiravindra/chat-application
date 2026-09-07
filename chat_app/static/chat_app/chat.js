const messagesContainer = document.getElementById('messages-container');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const noMessagesPlaceholder = document.getElementById('no-messages-placeholder');
const headerStatusDot = document.getElementById('header-status-dot');
const headerStatusText = document.getElementById('header-status-text');

function scrollToBottom() {
    if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}
scrollToBottom();

// WebSocket Connection Management
let chatSocket = null;
let reconnectTimer = null;

function connectWebSocket() {
    const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
    const token = localStorage.getItem('access_token') || '';
    const wsUrl = wsScheme + '://' + window.location.host + '/ws/chat/' + (token ? '?token=' + encodeURIComponent(token) : '');

    if (headerStatusText) headerStatusText.textContent = 'Connecting...';

    chatSocket = new WebSocket(wsUrl);

    chatSocket.onopen = function() {
        console.log('WebSocket connection established.');
        if (headerStatusDot) {
            headerStatusDot.classList.remove('offline');
            headerStatusDot.classList.add('online');
        }
        if (headerStatusText) {
            headerStatusText.textContent = 'Active now';
        }
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
    };

    chatSocket.onmessage = function(e) {
        const data = jsonParseSafe(e.data);
        if (!data) return;

        if (data.type === 'connection_established') {
            console.log('Connected:', data.message);
        }
        else if (data.type === 'user_status') {
            console.log(`User ${data.username} status: ${data.is_online ? 'online' : 'offline'}`);
        } 
        else if (data.type === 'user_typing') {
            const uid = parseInt(data.sender_id);
            const isTyping = data.is_typing;
            const senderUsername = data.sender_username;

            if (uid !== currentUserId) {
                const typingBubble = document.getElementById('typing-bubble');
                const typingMetaText = document.getElementById('typing-meta-text');

                if (isTyping) {
                    if (typingBubble) {
                        messagesContainer.appendChild(typingBubble);
                        typingBubble.style.display = 'flex';
                        if (typingMetaText) {
                            typingMetaText.textContent = `${senderUsername} is typing...`;
                        }
                        scrollToBottom();
                    }
                    if (headerStatusText) {
                        headerStatusText.innerHTML = `<span class="typing-text-highlight">${escapeHTML(senderUsername)} is typing...</span>`;
                    }
                } else {
                    if (typingBubble) {
                        typingBubble.style.display = 'none';
                    }
                    if (headerStatusText) {
                        headerStatusText.textContent = 'Active now';
                    }
                }
            }
        }
        else if (data.type === 'chat_message') {
            const senderId = parseInt(data.sender_id);
            const isSentByMe = senderId === currentUserId;

            if (noMessagesPlaceholder) {
                noMessagesPlaceholder.remove();
            }

            const typingBubble = document.getElementById('typing-bubble');
            const messageRow = document.createElement('div');
            messageRow.className = `message-row ${isSentByMe ? 'sent' : 'received'}`;
            const messageBody = data.message || data.content || '';
            messageRow.innerHTML = `
                <div class="message-bubble">
                    <div class="message-content">${escapeHTML(messageBody)}</div>
                </div>
                <div class="message-meta">
                    ${data.timestamp} ${escapeHTML(data.sender_username || '')}
                </div>
            `;
            
            if (typingBubble) {
                messagesContainer.insertBefore(messageRow, typingBubble);
            } else {
                messagesContainer.appendChild(messageRow);
            }
            scrollToBottom();
        }
    };

    chatSocket.onclose = function(e) {
        console.warn('Chat WebSocket closed. Attempting reconnect in 2s...', e.reason);
        if (headerStatusDot) {
            headerStatusDot.classList.remove('online');
            headerStatusDot.classList.add('offline');
        }
        if (headerStatusText) {
            headerStatusText.textContent = 'Disconnected (reconnecting...)';
        }

        if (!reconnectTimer) {
            reconnectTimer = setTimeout(function() {
                reconnectTimer = null;
                connectWebSocket();
            }, 2000);
        }
    };

    chatSocket.onerror = function(err) {
        console.error('WebSocket error encountered:', err);
    };
}

// Initial connection
connectWebSocket();

let typingTimeout = null;
let isCurrentlyTyping = false;

function sendTypingStatus(isTyping) {
    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.send(JSON.stringify({
            'type': 'typing',
            'is_typing': isTyping
        }));
    }
}

if (chatInput) {
    chatInput.addEventListener('input', function() {
        if (chatInput.value.trim().length > 0) {
            if (!isCurrentlyTyping) {
                isCurrentlyTyping = true;
                sendTypingStatus(true);
            }
            
            clearTimeout(typingTimeout);
            typingTimeout = setTimeout(function() {
                isCurrentlyTyping = false;
                sendTypingStatus(false);
            }, 2000);
        } else {
            if (isCurrentlyTyping) {
                isCurrentlyTyping = false;
                clearTimeout(typingTimeout);
                sendTypingStatus(false);
            }
        }
    });
}

if (chatForm) {
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (message === '') return;

        // Stop typing status immediately
        if (isCurrentlyTyping) {
            isCurrentlyTyping = false;
            clearTimeout(typingTimeout);
            sendTypingStatus(false);
        }

        if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
            chatSocket.send(JSON.stringify({
                'message': message
            }));
            chatInput.value = '';
            chatInput.focus();
        } else {
            alert('WebSocket is currently disconnected. Please wait for reconnection.');
        }
    });
}

function jsonParseSafe(str) {
    try { return JSON.parse(str); } catch (e) { return null; }
}

function escapeHTML(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
