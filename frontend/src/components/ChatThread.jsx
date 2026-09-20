import { useState, useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';
import '../styles/chat.css';

export default function ChatThread({ conversation, messages, loading, userPhone, onSend }) {
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState('');
  const endRef = useRef(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleSend(e) {
    e.preventDefault();
    if (!text.trim() || sending) return;
    setSendError('');
    setSending(true);
    try {
      await onSend(conversation.phone_number, text.trim());
      setText('');
    } catch (err) {
      setSendError(
        err.response?.data?.error?.message || 'Failed to send message.'
      );
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  }

  // Derive initials for recipient header
  const recipientInitials = conversation.phone_number.replace('+', '').slice(-4);

  return (
    <div className="chat-thread">
      {/* Header */}
      <div className="thread-header">
        <div className="thread-avatar" style={{ background: 'linear-gradient(135deg,#6366F1,#8B5CF6)' }}>
          {recipientInitials}
        </div>
        <div className="thread-info">
          <span className="thread-phone">{conversation.phone_number}</span>
          <span className="thread-meta">SMS via Twilio</span>
        </div>
      </div>

      {/* Messages */}
      <div className="messages-area" id="messages-area">
        {loading ? (
          <div className="messages-loading">
            <span className="spinner-large" />
          </div>
        ) : messages.length === 0 ? (
          <div className="messages-empty">
            <p>No messages yet. Say hello! 👋</p>
          </div>
        ) : (
          messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} userPhone={userPhone} />
          ))
        )}
        <div ref={endRef} />
      </div>

      {/* Error banner */}
      {sendError && (
        <div className="send-error-banner" role="alert">
          <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
          </svg>
          {sendError}
        </div>
      )}

      {/* Input */}
      <form className="message-form" onSubmit={handleSend} id="message-form">
        <textarea
          id="message-input"
          className="message-input"
          placeholder="Type a message…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          maxLength={160}
          disabled={sending}
        />
        <div className="message-form-meta">
          <span className="char-count">{text.length}/160</span>
          <button
            id="send-btn"
            type="submit"
            className={`send-btn ${sending ? 'loading' : ''}`}
            disabled={!text.trim() || sending}
            aria-label="Send message"
          >
            {sending ? (
              <span className="spinner" />
            ) : (
              <svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18">
                <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z"/>
              </svg>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
