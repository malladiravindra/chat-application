const messagesContainer = document.getElementById('messages-container');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const noMessagesPlaceholder = document.getElementById('no-messages-placeholder');

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}
scrollToBottom();

// Establish Global WebSocket Connection
const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
const chatSocket = new WebSocket(
    wsScheme + '://' + window.location.host + '/ws/chat/'
);

chatSocket.onmessage = function(e) {
    const data = jsonParseSafe(e.data);
    if (!data) return;

    if (data.type === 'user_status') {
        console.log(`User ${data.username} status: ${data.is_online ? 'online' : 'offline'}`);
    } 
    else if (data.type === 'user_typing') {
        const uid = parseInt(data.sender_id);
        const isTyping = data.is_typing;
        const senderUsername = data.sender_username;

        if (uid !== currentUserId) {
            const typingBubble = document.getElementById('typing-bubble');
            const typingMetaText = document.getElementById('typing-meta-text');
            const headerText = document.getElementById('header-status-text');

            if (isTyping) {
                if (typingBubble) {
                    messagesContainer.appendChild(typingBubble);
                    typingBubble.style.display = 'flex';
                    if (typingMetaText) {
                        typingMetaText.textContent = `${senderUsername} is typing...`;
                    }
                    scrollToBottom();
                }
                if (headerText) {
                    headerText.innerHTML = `<span class="typing-text-highlight">${senderUsername} is typing...</span>`;
                }
            } else {
                if (typingBubble) {
                    typingBubble.style.display = 'none';
                }
                if (headerText) {
                    headerText.textContent = 'Active now';
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
        messageRow.innerHTML = `
            <div class="message-bubble">
                <div class="message-content">${escapeHTML(data.message)}</div>
            </div>
            <div class="message-meta">
                ${data.timestamp} ${escapeHTML(data.sender_username)}
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
    console.error('Chat socket closed unexpectedly.');
};

let typingTimeout = null;
let isCurrentlyTyping = false;

function sendTypingStatus(isTyping) {
    if (chatSocket.readyState === WebSocket.OPEN) {
        chatSocket.send(JSON.stringify({
            'type': 'typing',
            'is_typing': isTyping
        }));
    }
}

chatInput.addEventListener('input', function() {
    if (chatInput.value.trim().length > 0) {
        if (!isCurrentlyTyping) {
            isCurrentlyTyping = true;
            sendTypingStatus(true);
        }
        
        // Clear the previous timeout and set a new one
        clearTimeout(typingTimeout);
        typingTimeout = setTimeout(function() {
            isCurrentlyTyping = false;
            sendTypingStatus(false);
        }, 2000);
    } else {
        // Input became empty
        if (isCurrentlyTyping) {
            isCurrentlyTyping = false;
            clearTimeout(typingTimeout);
            sendTypingStatus(false);
        }
    }
});

chatForm.addEventListener('submit', function(e) {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (message === '') return;

    // Stop typing immediately
    if (isCurrentlyTyping) {
        isCurrentlyTyping = false;
        clearTimeout(typingTimeout);
        sendTypingStatus(false);
    }

    chatSocket.send(JSON.stringify({
        'message': message
    }));

    chatInput.value = '';
    chatInput.focus();
});

function jsonParseSafe(str) {
    try { return JSON.parse(str); } catch (e) { return null; }
}

function escapeHTML(str) {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
