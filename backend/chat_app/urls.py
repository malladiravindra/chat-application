from django.urls import path
from django.http import HttpResponse
from . import api_views


def api_root(request):
    base = request.build_absolute_uri('/')[:-1]   # e.g. http://127.0.0.1:8000

    endpoints = [
        # (group, method, path, description, auth_required)
        ("Auth", "POST", "/api/auth/register/",        "Register with phone number + password",        False),
        ("Auth", "POST", "/api/auth/send-otp/",        "Send / resend OTP to a phone number",          False),
        ("Auth", "POST", "/api/auth/verify-otp/",      "Verify OTP and activate account",              False),
        ("Auth", "POST", "/api/auth/login/",           "Login → receive JWT access + refresh tokens",  False),
        ("Auth", "POST", "/api/auth/forgot-password/", "Send password-reset OTP",                      False),
        ("Auth", "POST", "/api/auth/resend-otp/",      "Resend password-reset OTP",                    False),
        ("Auth", "POST", "/api/auth/reset-password/",  "Verify OTP and reset password",                False),
        ("Auth", "POST", "/api/auth/token/refresh/",   "Refresh JWT access token",                     False),
        ("Chat SMS", "POST", "/api/chat/send-sms/",                        "Send SMS via Twilio (creates Conversation)",     True),
        ("Chat SMS", "GET",  "/api/chat/conversations/",                   "List all conversations for logged-in user",      True),
        ("Chat SMS", "GET",  "/api/chat/conversations/{id}/messages/",     "Get full message history for a conversation",    True),
        ("Chat SMS", "POST", "/api/chat/inbound/",                         "Twilio inbound webhook (incoming SMS)",          False),
        ("Twilio Webhook", "POST", "/api/twilio/sms/status/",             "Twilio delivery-status callback",                False),
        ("Admin", "GET",  "/admin/",                                       "Django Admin panel",                             True),
    ]

    method_colors = {
        "GET":  ("#10B981", "#064e3b"),
        "POST": ("#6366F1", "#1e1b4b"),
    }

    rows = ""
    current_group = None
    for group, method, path_, desc, auth in endpoints:
        if group != current_group:
            current_group = group
            rows += f"""
            <tr class="group-header">
              <td colspan="4">{group}</td>
            </tr>"""
        fg, bg = method_colors.get(method, ("#94A3B8", "#1e293b"))
        auth_badge = (
            '<span class="badge auth">🔒 JWT</span>' if auth
            else '<span class="badge open">Public</span>'
        )
        full_url = f"{base}{path_}"
        rows += f"""
            <tr>
              <td><span class="method" style="color:{fg};background:{bg}">{method}</span></td>
              <td><a href="{full_url}" target="_blank" class="endpoint-link">{path_}</a></td>
              <td class="desc">{desc}</td>
              <td>{auth_badge}</td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>TextWave API</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{
      font-family:'Inter',sans-serif;
      background:#07090F;
      color:#e2e8f0;
      min-height:100vh;
      padding:40px 24px;
    }}
    .container{{max-width:960px;margin:0 auto}}

    /* ── Header ── */
    .header{{
      display:flex;align-items:center;gap:16px;
      padding:28px 32px;
      background:linear-gradient(135deg,rgba(99,102,241,.15),rgba(139,92,246,.08));
      border:1px solid rgba(99,102,241,.25);
      border-radius:16px;
      margin-bottom:32px;
    }}
    .logo{{
      width:52px;height:52px;border-radius:14px;
      background:linear-gradient(135deg,#6366F1,#8B5CF6);
      display:flex;align-items:center;justify-content:center;
      font-size:24px;flex-shrink:0;
      box-shadow:0 4px 16px rgba(99,102,241,.45);
    }}
    .header-text h1{{
      font-size:22px;font-weight:700;
      background:linear-gradient(135deg,#818CF8,#C4B5FD);
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    }}
    .header-text p{{font-size:13px;color:#94A3B8;margin-top:3px}}

    /* ── Badges row ── */
    .badges{{display:flex;gap:10px;margin-bottom:28px;flex-wrap:wrap}}
    .pill{{
      padding:5px 14px;border-radius:99px;font-size:12px;font-weight:600;
      display:flex;align-items:center;gap:6px;
    }}
    .pill-green{{background:rgba(16,185,129,.15);color:#34D399;border:1px solid rgba(16,185,129,.3)}}
    .pill-indigo{{background:rgba(99,102,241,.15);color:#818CF8;border:1px solid rgba(99,102,241,.3)}}
    .pill-amber{{background:rgba(251,191,36,.1);color:#FCD34D;border:1px solid rgba(251,191,36,.3)}}

    /* ── Base URL card ── */
    .base-card{{
      background:#0D1117;border:1px solid rgba(255,255,255,.07);
      border-radius:10px;padding:14px 20px;
      margin-bottom:28px;
      display:flex;align-items:center;gap:12px;
      font-family:'JetBrains Mono',monospace;
    }}
    .base-label{{font-size:11px;color:#64748B;flex-shrink:0;font-family:'Inter',sans-serif;font-weight:600}}
    .base-url{{font-size:14px;color:#6366F1;font-weight:500}}

    /* ── Table ── */
    .section-title{{
      font-size:11px;font-weight:700;color:#64748B;
      text-transform:uppercase;letter-spacing:.08em;
      margin-bottom:12px;
    }}
    .table-wrap{{
      background:#0D1117;
      border:1px solid rgba(255,255,255,.07);
      border-radius:14px;
      overflow:hidden;
      margin-bottom:32px;
    }}
    table{{width:100%;border-collapse:collapse}}
    thead tr{{background:#161B27}}
    thead th{{
      padding:12px 16px;
      font-size:11px;font-weight:700;
      color:#64748B;text-transform:uppercase;letter-spacing:.07em;
      text-align:left;
    }}
    tbody tr{{border-top:1px solid rgba(255,255,255,.05);transition:background .15s}}
    tbody tr:hover{{background:rgba(99,102,241,.05)}}

    .group-header td{{
      padding:8px 16px;
      font-size:11px;font-weight:700;
      color:#6366F1;
      background:rgba(99,102,241,.06);
      text-transform:uppercase;letter-spacing:.08em;
    }}
    td{{padding:12px 16px;vertical-align:middle}}

    .method{{
      display:inline-block;
      padding:3px 10px;
      border-radius:6px;
      font-family:'JetBrains Mono',monospace;
      font-size:11px;font-weight:700;
      letter-spacing:.03em;
    }}
    .endpoint-link{{
      color:#818CF8;
      text-decoration:none;
      font-family:'JetBrains Mono',monospace;
      font-size:13px;
      transition:color .15s;
    }}
    .endpoint-link:hover{{color:#C4B5FD;text-decoration:underline}}
    .desc{{font-size:13px;color:#94A3B8}}

    .badge{{
      display:inline-block;
      padding:2px 10px;border-radius:99px;
      font-size:11px;font-weight:600;
    }}
    .badge.auth{{
      background:rgba(99,102,241,.15);color:#818CF8;
      border:1px solid rgba(99,102,241,.3);
    }}
    .badge.open{{
      background:rgba(16,185,129,.1);color:#34D399;
      border:1px solid rgba(16,185,129,.25);
    }}

    /* ── Footer ── */
    .footer{{text-align:center;color:#475569;font-size:12px;margin-top:8px;padding-bottom:20px}}
    .footer a{{color:#6366F1;text-decoration:none}}
    .footer a:hover{{text-decoration:underline}}
  </style>
</head>
<body>
  <div class="container">

    <!-- Header -->
    <div class="header">
      <div class="logo">📡</div>
      <div class="header-text">
        <h1>TextWave — REST API</h1>
        <p>Django REST Framework · JWT Authentication · Twilio SMS</p>
      </div>
    </div>

    <!-- Pills -->
    <div class="badges">
      <span class="pill pill-green">✅ Server Running</span>
      <span class="pill pill-indigo">🔑 JWT Auth</span>
      <span class="pill pill-amber">📱 Twilio SMS</span>
    </div>

    <!-- Base URL -->
    <div class="base-card">
      <span class="base-label">BASE URL</span>
      <span class="base-url">{base}</span>
    </div>

    <!-- Endpoint Table -->
    <p class="section-title">All Endpoints</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Method</th>
            <th>Endpoint</th>
            <th>Description</th>
            <th>Auth</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>

    <!-- Footer -->
    <div class="footer">
      Frontend at&nbsp;<a href="http://localhost:5173" target="_blank">http://localhost:5173</a>
      &nbsp;·&nbsp;
      Admin at&nbsp;<a href="{base}/admin/" target="_blank">/admin/</a>
      &nbsp;·&nbsp;
      Use <code>Authorization: Bearer &lt;token&gt;</code> for 🔒 endpoints
    </div>
  </div>
</body>
</html>"""
    return HttpResponse(html)




urlpatterns = [
    # ── API Root ─────────────────────────────────────────
    path('',    api_root,   name='api_root'),
    path('api/', api_root,  name='api_root_prefix'),

    # ── Auth API Endpoints ───────────────────────────────
    path('api/auth/register/',        api_views.RegisterView.as_view(),       name='api_register'),
    path('api/auth/send-otp/',        api_views.SendOTPView.as_view(),        name='api_send_otp'),
    path('api/auth/verify-otp/',      api_views.VerifyOTPView.as_view(),      name='api_verify_otp'),
    path('api/auth/login/',           api_views.LoginView.as_view(),          name='api_login'),
    path('api/auth/forgot-password/', api_views.ForgotPasswordView.as_view(), name='api_forgot_password'),
    path('api/auth/resend-otp/',      api_views.ResendOTPView.as_view(),      name='api_resend_otp'),
    path('api/auth/reset-password/',  api_views.ResetPasswordView.as_view(),  name='api_reset_password'),

    # ── SMS API Endpoints (real SMS via Twilio) ──────────
    path('api/sms/send/',             api_views.SendSMSView.as_view(),                name='api_sms_send'),
    path('api/sms/<int:pk>/',         api_views.SMSStatusView.as_view(),              name='api_sms_status'),
    path('api/twilio/sms/status/',    api_views.TwilioSMSStatusWebhookView.as_view(), name='api_twilio_sms_status'),

    # ── Chat SMS API Endpoints (Conversation + ChatMessage) ──────────
    path('api/chat/send-sms/',                        api_views.ChatSendSMSView.as_view(),        name='api_chat_send_sms'),
    path('api/chat/conversations/',                   api_views.ConversationListView.as_view(),   name='api_conversations'),
    path('api/chat/conversations/<int:pk>/messages/', api_views.ConversationDetailView.as_view(), name='api_conversation_messages'),
    path('api/chat/inbound/',                         api_views.TwilioInboundWebhookView.as_view(), name='api_chat_inbound'),
]
