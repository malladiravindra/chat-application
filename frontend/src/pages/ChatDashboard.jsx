import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { chatAPI } from '../api/chat';
import { useAuth } from '../context/AuthContext';
import ConversationList from '../components/ConversationList';
import ChatThread from '../components/ChatThread';
import NewChatModal from '../components/NewChatModal';
import '../styles/chat.css';

export default function ChatDashboard() {
  const { userPhone, logout } = useAuth();
  const navigate = useNavigate();

  const [conversations, setConversations] = useState([]);
  const [activeConv, setActiveConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loadingConvs, setLoadingConvs] = useState(true);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [showNewChat, setShowNewChat] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Load conversations on mount
  const loadConversations = useCallback(async () => {
    try {
      const { data } = await chatAPI.listConversations();
      setConversations(data.conversations || []);
    } catch {
      // silently fail
    } finally {
      setLoadingConvs(false);
    }
  }, []);

  useEffect(() => { loadConversations(); }, [loadConversations]);

  // Load messages when active conversation changes
  useEffect(() => {
    if (!activeConv) { setMessages([]); return; }
    setLoadingMsgs(true);
    chatAPI.getMessages(activeConv.id)
      .then(({ data }) => setMessages(data.messages || []))
      .catch(() => setMessages([]))
      .finally(() => setLoadingMsgs(false));
  }, [activeConv]);

  // Poll for new messages every 5 seconds when a conv is active
  useEffect(() => {
    if (!activeConv) return;
    const interval = setInterval(async () => {
      try {
        const { data } = await chatAPI.getMessages(activeConv.id);
        setMessages(data.messages || []);
      } catch { /* ignore */ }
    }, 5000);
    return () => clearInterval(interval);
  }, [activeConv]);

  async function handleSendMessage(phone, message) {
    const { data } = await chatAPI.sendSMS(phone, message);
    // Refresh conversations + messages
    await loadConversations();
    if (activeConv) {
      const { data: msgData } = await chatAPI.getMessages(activeConv.id);
      setMessages(msgData.messages || []);
    } else {
      // Might be a new conversation — reload and select it
      const { data: convData } = await chatAPI.listConversations();
      const convs = convData.conversations || [];
      setConversations(convs);
      const newConv = convs.find(c => c.phone_number === phone);
      if (newConv) {
        setActiveConv(newConv);
      }
    }
    return data;
  }

  function handleNewConversation(conv) {
    setConversations(prev => {
      const exists = prev.find(c => c.id === conv.id);
      if (exists) return prev.map(c => c.id === conv.id ? conv : c);
      return [conv, ...prev];
    });
    setActiveConv(conv);
    setShowNewChat(false);
  }

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <div className="chat-app">
      {/* ── Sidebar ── */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <svg viewBox="0 0 32 32" fill="none" width="28" height="28">
              <rect width="32" height="32" rx="9" fill="url(#slg)"/>
              <path d="M8 22l3-6 5 3 5-8 3 11" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <defs>
                <linearGradient id="slg" x1="0" y1="0" x2="32" y2="32">
                  <stop stopColor="#6366F1"/><stop offset="1" stopColor="#8B5CF6"/>
                </linearGradient>
              </defs>
            </svg>
            <span className="brand-name">TextWave</span>
          </div>
          <div className="sidebar-actions">
            <button id="new-chat-btn" className="icon-btn" onClick={() => setShowNewChat(true)} title="New conversation">
              <svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18">
                <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd"/>
              </svg>
            </button>
          </div>
        </div>

        <div className="sidebar-user">
          <div className="user-avatar" style={{ background: 'linear-gradient(135deg, #6366F1, #8B5CF6)' }}>
            {userPhone?.replace('+', '').slice(0, 2)}
          </div>
          <div className="user-info">
            <span className="user-phone">{userPhone}</span>
            <span className="user-status">
              <span className="status-dot" /> Online
            </span>
          </div>
          <button id="logout-btn" className="icon-btn logout-btn" onClick={handleLogout} title="Sign out">
            <svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18">
              <path fillRule="evenodd" d="M3 3a1 1 0 00-1 1v12a1 1 0 102 0V4a1 1 0 00-1-1zm10.293 9.293a1 1 0 001.414 1.414l3-3a1 1 0 000-1.414l-3-3a1 1 0 10-1.414 1.414L14.586 9H7a1 1 0 100 2h7.586l-1.293 1.293z" clipRule="evenodd"/>
            </svg>
          </button>
        </div>

        <div className="sidebar-search">
          <svg className="search-icon" viewBox="0 0 20 20" fill="currentColor" width="16">
            <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd"/>
          </svg>
          <input type="text" placeholder="Search conversations..." className="search-input" id="search-input"/>
        </div>

        <ConversationList
          conversations={conversations}
          loading={loadingConvs}
          activeId={activeConv?.id}
          onSelect={setActiveConv}
        />
      </aside>

      {/* ── Main area ── */}
      <main className="chat-main">
        <button className="sidebar-toggle" onClick={() => setSidebarOpen(s => !s)} id="sidebar-toggle">
          <svg viewBox="0 0 20 20" fill="currentColor" width="20">
            <path fillRule="evenodd" d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd"/>
          </svg>
        </button>

        {activeConv ? (
          <ChatThread
            conversation={activeConv}
            messages={messages}
            loading={loadingMsgs}
            userPhone={userPhone}
            onSend={handleSendMessage}
          />
        ) : (
          <div className="chat-empty">
            <div className="chat-empty-icon">
              <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" width="64" height="64">
                <circle cx="32" cy="32" r="32" fill="rgba(99,102,241,0.15)"/>
                <path d="M20 24a4 4 0 014-4h16a4 4 0 014 4v12a4 4 0 01-4 4h-4l-4 4-4-4h-4a4 4 0 01-4-4V24z" stroke="#6366F1" strokeWidth="2" fill="none"/>
                <circle cx="26" cy="30" r="1.5" fill="#6366F1"/>
                <circle cx="32" cy="30" r="1.5" fill="#6366F1"/>
                <circle cx="38" cy="30" r="1.5" fill="#6366F1"/>
              </svg>
            </div>
            <h2>Start a Conversation</h2>
            <p>Select a chat or send a new SMS message</p>
            <button id="new-chat-empty-btn" className="chat-empty-btn" onClick={() => setShowNewChat(true)}>
              <svg viewBox="0 0 20 20" fill="currentColor" width="16">
                <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd"/>
              </svg>
              New Message
            </button>
          </div>
        )}
      </main>

      {/* ── New Chat Modal ── */}
      {showNewChat && (
        <NewChatModal
          onClose={() => setShowNewChat(false)}
          onSent={handleNewConversation}
          userPhone={userPhone}
          onSendMessage={handleSendMessage}
        />
      )}
    </div>
  );
}
