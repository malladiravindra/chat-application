import '../styles/chat.css';

function formatTime(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString);
  const now = new Date();
  const diffDays = Math.floor((now - date) / 86400000);
  if (diffDays === 0) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return date.toLocaleDateString([], { weekday: 'short' });
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

export default function ConversationList({ conversations, loading, activeId, onSelect }) {
  if (loading) {
    return (
      <div className="conv-list">
        {[1, 2, 3].map(i => (
          <div key={i} className="conv-item skeleton">
            <div className="conv-avatar skeleton-box" />
            <div className="conv-preview skeleton-lines">
              <div className="skeleton-line short" />
              <div className="skeleton-line long" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (conversations.length === 0) {
    return (
      <div className="conv-empty">
        <p>No conversations yet</p>
        <span>Tap + to start chatting</span>
      </div>
    );
  }

  return (
    <div className="conv-list" role="list">
      {conversations.map(conv => {
        const initials = conv.phone_number.replace('+', '').slice(-4);
        const isActive = conv.id === activeId;
        const lastMsg = conv.last_message;

        return (
          <button
            key={conv.id}
            id={`conv-${conv.id}`}
            className={`conv-item ${isActive ? 'active' : ''}`}
            onClick={() => onSelect(conv)}
            role="listitem"
          >
            <div className="conv-avatar" style={{ background: phoneToColor(conv.phone_number) }}>
              {initials}
            </div>
            <div className="conv-content">
              <div className="conv-header-row">
                <span className="conv-phone">{conv.phone_number}</span>
                <span className="conv-time">{formatTime(conv.updated_at)}</span>
              </div>
              <div className="conv-preview-row">
                <span className="conv-preview-text">
                  {lastMsg
                    ? (lastMsg.direction === 'outgoing' ? '↗ ' : '↙ ') + lastMsg.message_body
                    : 'No messages yet'}
                </span>
                {conv.unread_count > 0 && (
                  <span className="conv-badge">{conv.unread_count}</span>
                )}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}

// Deterministically pick a gradient from the phone number
function phoneToColor(phone) {
  const colors = [
    'linear-gradient(135deg,#6366F1,#8B5CF6)',
    'linear-gradient(135deg,#10B981,#059669)',
    'linear-gradient(135deg,#F59E0B,#D97706)',
    'linear-gradient(135deg,#EC4899,#DB2777)',
    'linear-gradient(135deg,#06B6D4,#0891B2)',
    'linear-gradient(135deg,#EF4444,#DC2626)',
  ];
  const sum = phone.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  return colors[sum % colors.length];
}
