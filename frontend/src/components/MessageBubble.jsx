import '../styles/chat.css';

const STATUS_ICONS = {
  queued:    { icon: '⏱', label: 'Queued',    color: '#94A3B8' },
  sent:      { icon: '✓',  label: 'Sent',      color: '#94A3B8' },
  delivered: { icon: '✓✓', label: 'Delivered', color: '#10B981' },
  failed:    { icon: '✕',  label: 'Failed',    color: '#EF4444' },
  received:  { icon: '✓',  label: 'Received',  color: '#6366F1' },
};

function formatTime(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export default function MessageBubble({ message, userPhone }) {
  const isOutgoing = message.direction === 'outgoing';
  const statusInfo = STATUS_ICONS[message.status] || STATUS_ICONS.queued;

  return (
    <div className={`bubble-wrapper ${isOutgoing ? 'outgoing' : 'incoming'}`}>
      <div className={`bubble ${isOutgoing ? 'bubble-out' : 'bubble-in'}`}>
        <p className="bubble-text">{message.message_body}</p>
        <div className="bubble-meta">
          <span className="bubble-time">{formatTime(message.created_at)}</span>
          {isOutgoing && (
            <span className="bubble-status" style={{ color: statusInfo.color }} title={statusInfo.label}>
              {statusInfo.icon}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
