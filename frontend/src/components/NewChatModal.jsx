import { useState, useEffect, useRef } from 'react';
import { chatAPI } from '../api/chat';
import '../styles/chat.css';

export default function NewChatModal({ onClose, onSent, userPhone, onSendMessage }) {
  const [phone, setPhone] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
    // Close on Escape
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await onSendMessage(phone.trim(), message.trim());
      // data is the API response from chatAPI.sendSMS
      // Build a minimal conversation object to open the thread
      onSent({
        id: data.data?.conversation,
        phone_number: phone.trim(),
        updated_at: new Date().toISOString(),
        last_message: {
          message_body: message.trim(),
          direction: 'outgoing',
          status: data.status || 'queued',
        },
        unread_count: 0,
      });
    } catch (err) {
      setError(
        err.response?.data?.error?.message ||
        err.response?.data?.error ||
        'Failed to send SMS. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="New conversation">
        <div className="modal-header">
          <h2>New Message</h2>
          <button className="icon-btn" onClick={onClose} id="modal-close-btn" aria-label="Close">
            <svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"/>
            </svg>
          </button>
        </div>

        {error && (
          <div className="auth-error" role="alert">
            <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
            </svg>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="modal-form" id="new-sms-form">
          <div className="form-group">
            <label htmlFor="modal-phone">Recipient Phone Number</label>
            <div className="input-wrapper">
              <svg className="input-icon" viewBox="0 0 20 20" fill="currentColor">
                <path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 01-.54 1.06l-1.548.773a11.037 11.037 0 006.105 6.105l.774-1.548a1 1 0 011.059-.54l4.435.74a1 1 0 01.836.986V17a1 1 0 01-1 1h-2C7.82 18 2 12.18 2 5V3z"/>
              </svg>
              <input
                id="modal-phone"
                ref={inputRef}
                type="tel"
                className="form-input"
                placeholder="+919876543210"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                autoComplete="tel"
              />
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="modal-message">
              Message
              <span className="char-label">{message.length}/160</span>
            </label>
            <textarea
              id="modal-message"
              className="form-textarea"
              placeholder="Type your SMS message here…"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
              rows={4}
              maxLength={160}
            />
          </div>
          <div className="modal-footer">
            <button type="button" className="auth-btn-ghost" onClick={onClose} id="modal-cancel-btn">
              Cancel
            </button>
            <button
              id="modal-send-btn"
              type="submit"
              className={`auth-btn modal-send ${loading ? 'loading' : ''}`}
              disabled={loading || !phone.trim() || !message.trim()}
            >
              {loading ? <span className="spinner" /> : (
                <>
                  <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
                    <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z"/>
                  </svg>
                  Send SMS
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
