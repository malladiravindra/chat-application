# TextWave — Chat Application with Twilio SMS

Full-stack SMS chat app built with **Django + DRF** (backend) and **React + Vite** (frontend).

---

## Project Structure

```
chat_application/
├── backend/                     ← Django project
│   ├── chat_app/                ← Main Django app (models, views, APIs)
│   ├── chat_application/        ← Django settings, URLs, ASGI/WSGI
│   ├── twilio_service/          ← Twilio SMS service layer
│   ├── manage.py
│   ├── .env                     ← Backend environment variables
│   └── db.sqlite3               ← SQLite database (dev)
│
└── frontend/                    ← React + Vite app
    ├── src/
    │   ├── api/                 ← axiosInstance, auth.js, chat.js
    │   ├── components/          ← ConversationList, ChatThread, MessageBubble...
    │   ├── context/             ← AuthContext (JWT state)
    │   ├── pages/               ← LoginPage, RegisterPage, ChatDashboard
    │   └── styles/              ← index.css, auth.css, chat.css
    ├── .env                     ← VITE_API_BASE_URL=http://127.0.0.1:8000
    └── package.json
```

---

## Running the App

### Backend (Terminal 1)
```bash
cd backend
python manage.py runserver
```
API available at: **http://127.0.0.1:8000**

### Frontend (Terminal 2)
```bash
cd frontend
npm run dev
```
App available at: **http://localhost:5173**

---

## Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register/` | Register with phone + password |
| `POST` | `/api/auth/verify-otp/` | Verify OTP to activate account |
| `POST` | `/api/auth/login/` | Login → JWT tokens |
| `POST` | `/api/chat/send-sms/` | **Send SMS via Twilio** |
| `GET`  | `/api/chat/conversations/` | List all conversations |
| `GET`  | `/api/chat/conversations/<id>/messages/` | Get message history |
| `POST` | `/api/chat/inbound/` | Twilio inbound webhook |

---

## Environment Setup

### `backend/.env`
```
SECRET_KEY=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...
```

### `frontend/.env`
```
VITE_API_BASE_URL=http://127.0.0.1:8000
```
