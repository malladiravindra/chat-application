// ── SMS API service ─────────────────────────────────────────
// Talks only to our own Django backend. Twilio is never called
// from the browser and no credentials live here.
const E164_REGEX = /^\+[1-9]\d{6,14}$/;

function getAccessToken() {
    return localStorage.getItem('access_token') || '';
}

async function sendSms(phoneNumber, message) {
    const res = await fetch('/api/sms/send/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + getAccessToken(),
        },
        body: JSON.stringify({ to: phoneNumber, message: message }),
    });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data };
}

async function fetchSmsStatus(smsId) {
    const res = await fetch(`/api/sms/${smsId}/`, {
        headers: { 'Authorization': 'Bearer ' + getAccessToken() },
    });
    if (!res.ok) return null;
    const data = await res.json().catch(() => null);
    return data ? data.message : null;
}

// ── Page wiring ─────────────────────────────────────────────
const smsForm       = document.getElementById('sms-form');
const receiverInput = document.getElementById('receiver');
const receiverError = document.getElementById('receiver-error');
const messageInput  = document.getElementById('message');
const charCount      = document.getElementById('char-count');
const alertBox       = document.getElementById('alert-box');
const sendBtn         = document.getElementById('send-btn');
const btnText         = document.getElementById('btn-text');
const btnSpinner      = document.getElementById('btn-spinner');
const statusPanel     = document.getElementById('status-panel');
const statusBadge     = document.getElementById('status-badge');
const statusMeta      = document.getElementById('status-meta');

let pollTimer = null;

function showAlert(msg, type) {
    alertBox.textContent = msg;
    alertBox.className = `alert ${type}`;
    alertBox.style.display = 'block';
}

function hideAlert() {
    alertBox.style.display = 'none';
}

function setLoading(loading) {
    sendBtn.disabled = loading;
    btnText.style.display = loading ? 'none' : 'inline';
    btnSpinner.style.display = loading ? 'block' : 'none';
}

function renderStatus(smsMessage) {
    statusPanel.hidden = false;
    const statusLabels = {
        QUEUED: 'Queued',
        SENDING: 'Sending',
        SENT: '✓ Sent',
        DELIVERED: '✓✓ Delivered',
        FAILED: '❌ Failed',
        UNDELIVERED: '❌ Undelivered',
    };
    statusBadge.textContent = statusLabels[smsMessage.status] || smsMessage.status;
    statusBadge.className = `status-badge ${smsMessage.status.toLowerCase()}`;
    statusMeta.textContent = `To ${smsMessage.to} · SID: ${smsMessage.twilio_message_sid || '—'}`;
}

function pollStatus(smsId, attemptsLeft) {
    if (pollTimer) clearTimeout(pollTimer);
    if (attemptsLeft <= 0) return;

    pollTimer = setTimeout(async () => {
        const smsMessage = await fetchSmsStatus(smsId);
        if (!smsMessage) return;
        renderStatus(smsMessage);

        const terminal = ['DELIVERED', 'FAILED', 'UNDELIVERED'].includes(smsMessage.status);
        if (!terminal) {
            pollStatus(smsId, attemptsLeft - 1);
        }
    }, 3000);
}

messageInput.addEventListener('input', () => {
    charCount.textContent = messageInput.value.length;
});

receiverInput.addEventListener('input', () => {
    receiverError.textContent = '';
});

smsForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideAlert();
    receiverError.textContent = '';

    const receiver = receiverInput.value.trim();
    const message = messageInput.value.trim();

    if (!E164_REGEX.test(receiver)) {
        receiverError.textContent = 'Enter a valid phone number including country code.';
        return;
    }
    if (!message) {
        showAlert('Message cannot be empty.', 'error');
        return;
    }
    if (message.length > 160) {
        showAlert('Message must be 160 characters or fewer.', 'error');
        return;
    }

    setLoading(true);
    try {
        const { ok, status, data } = await sendSms(receiver, message);

        if (ok && data.success) {
            showAlert('SMS sent successfully.', 'success');
            renderStatus(data.message);
            pollStatus(data.message.id, 8);
        } else if (status === 429) {
            showAlert('Too many SMS requests. Please wait before trying again.', 'error');
        } else {
            const errMsg = (data.error && data.error.message) || 'Unable to send SMS.';
            showAlert(errMsg, 'error');
        }
    } catch (err) {
        showAlert('Network error. Please check your connection.', 'error');
    } finally {
        setLoading(false);
    }
});
