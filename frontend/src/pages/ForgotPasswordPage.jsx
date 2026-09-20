import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authAPI } from '../api/auth';
import '../styles/auth.css';

const STEP_PHONE = 1;
const STEP_OTP = 2;
const STEP_NEW_PASSWORD = 3;
const STEP_SUCCESS = 4;

const COOLDOWN_SECONDS = 60;

export default function ForgotPasswordPage() {
  const [step, setStep] = useState(STEP_PHONE);
  const [phone, setPhone] = useState('');
  const [otpDigits, setOtpDigits] = useState(['', '', '', '', '', '']);
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [loading, setLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  const otpInputsRef = useRef([]);
  const navigate = useNavigate();

  // Cooldown countdown timer
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => {
      setCooldown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  // Focus first OTP input when transitioning to Step 2
  useEffect(() => {
    if (step === STEP_OTP) {
      setTimeout(() => {
        otpInputsRef.current[0]?.focus();
      }, 100);
    }
  }, [step]);

  // Step 1: Send OTP
  async function handleSendOTP(e) {
    e.preventDefault();
    setError('');
    setInfo('');
    setLoading(true);

    try {
      const { data } = await authAPI.forgotPassword(phone);
      setInfo(data.message || 'If an account exists, an OTP has been sent.');
      setStep(STEP_OTP);
      setCooldown(COOLDOWN_SECONDS);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to send OTP. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  // Handle single OTP box change
  function handleOtpChange(index, value) {
    const cleaned = value.replace(/\D/g, '');
    if (!cleaned) {
      const nextDigits = [...otpDigits];
      nextDigits[index] = '';
      setOtpDigits(nextDigits);
      return;
    }

    const nextDigits = [...otpDigits];
    nextDigits[index] = cleaned[cleaned.length - 1]; // take the last typed digit
    setOtpDigits(nextDigits);

    // Auto-advance to next input
    if (index < 5 && cleaned) {
      otpInputsRef.current[index + 1]?.focus();
    }
  }

  // Handle Backspace navigation
  function handleOtpKeyDown(index, e) {
    if (e.key === 'Backspace' && !otpDigits[index] && index > 0) {
      otpInputsRef.current[index - 1]?.focus();
    }
  }

  // Handle Paste of complete 6-digit OTP
  function handleOtpPaste(e) {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (!pasted) return;

    const nextDigits = [...otpDigits];
    for (let i = 0; i < pasted.length; i++) {
      nextDigits[i] = pasted[i];
    }
    setOtpDigits(nextDigits);

    const targetIndex = Math.min(pasted.length, 5);
    otpInputsRef.current[targetIndex]?.focus();
  }

  // Step 2: Verify OTP
  async function handleVerifyOTP(e) {
    e.preventDefault();
    const fullOtp = otpDigits.join('');
    if (fullOtp.length < 6) {
      setError('Please enter the complete 6-digit OTP.');
      return;
    }

    setError('');
    setInfo('');
    setLoading(true);

    try {
      const { data } = await authAPI.verifyOTP(phone, fullOtp, 'reset');
      setResetToken(data.reset_token);
      setInfo('OTP verified! Please create your new password.');
      setStep(STEP_NEW_PASSWORD);
    } catch (err) {
      setError(err.response?.data?.error || 'Invalid OTP. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  // Resend OTP
  async function handleResendOTP() {
    if (cooldown > 0) return;
    setError('');
    setInfo('');
    setLoading(true);

    try {
      const { data } = await authAPI.resendOTP(phone);
      setInfo(data.message || 'A new OTP has been sent.');
      setCooldown(COOLDOWN_SECONDS);
      setOtpDigits(['', '', '', '', '', '']);
      otpInputsRef.current[0]?.focus();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to resend OTP.');
    } finally {
      setLoading(false);
    }
  }

  // Step 3: Reset Password
  async function handleResetPassword(e) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    setError('');
    setInfo('');
    setLoading(true);

    try {
      await authAPI.resetPassword(resetToken, newPassword, confirmPassword);
      setStep(STEP_SUCCESS);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to reset password. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        {/* Brand Header */}
        <div className="auth-brand">
          <div className="auth-logo">
            <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="40" height="40" rx="12" fill="url(#lg_fp)" />
              <path
                d="M10 28l4-8 6 4 6-10 4 14"
                stroke="white"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <defs>
                <linearGradient id="lg_fp" x1="0" y1="0" x2="40" y2="40">
                  <stop stopColor="#6366F1" />
                  <stop offset="1" stopColor="#8B5CF6" />
                </linearGradient>
              </defs>
            </svg>
          </div>
          <h1 className="auth-title">TextWave</h1>
          <p className="auth-subtitle">
            {step === STEP_PHONE && 'Reset your password via SMS OTP'}
            {step === STEP_OTP && 'Enter verification code'}
            {step === STEP_NEW_PASSWORD && 'Create new password'}
            {step === STEP_SUCCESS && 'Password reset complete'}
          </p>
        </div>

        {/* Step Indicator */}
        {step !== STEP_SUCCESS && (
          <div className="step-indicator">
            <div className={`step-dot ${step >= STEP_PHONE ? 'active' : ''}`} />
            <div className="step-line" />
            <div className={`step-dot ${step >= STEP_OTP ? 'active' : ''}`} />
            <div className="step-line" />
            <div className={`step-dot ${step >= STEP_NEW_PASSWORD ? 'active' : ''}`} />
          </div>
        )}

        {/* Error / Info Alerts */}
        {error && (
          <div className="auth-error" role="alert">
            <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
            {error}
          </div>
        )}
        {info && <div className="auth-info">{info}</div>}

        {/* Step 1: Phone Number */}
        {step === STEP_PHONE && (
          <form onSubmit={handleSendOTP} className="auth-form" id="forgot-password-form">
            <div className="form-group">
              <label htmlFor="fp-phone">Phone Number</label>
              <div className="input-wrapper">
                <svg className="input-icon" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 01-.54 1.06l-1.548.773a11.037 11.037 0 006.105 6.105l.774-1.548a1 1 0 011.059-.54l4.435.74a1 1 0 01.836.986V17a1 1 0 01-1 1h-2C7.82 18 2 12.18 2 5V3z" />
                </svg>
                <input
                  id="fp-phone"
                  type="tel"
                  className="form-input"
                  placeholder="+91 9876543210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  required
                  autoComplete="tel"
                  autoFocus
                />
              </div>
            </div>

            <button
              id="send-otp-btn"
              type="submit"
              className={`auth-btn ${loading ? 'loading' : ''}`}
              disabled={loading}
            >
              {loading ? <span className="spinner" /> : 'Send OTP'}
            </button>
          </form>
        )}

        {/* Step 2: Enter 6-digit OTP */}
        {step === STEP_OTP && (
          <form onSubmit={handleVerifyOTP} className="auth-form" id="verify-otp-form">
            <p className="otp-hint">
              Enter the 6-digit verification code sent to <strong>{phone}</strong>
            </p>

            <div className="form-group">
              <label>Enter OTP</label>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(6, 1fr)',
                  gap: '8px',
                  marginTop: '4px',
                }}
              >
                {otpDigits.map((digit, idx) => (
                  <input
                    key={idx}
                    ref={(el) => (otpInputsRef.current[idx] = el)}
                    id={`otp-digit-${idx}`}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleOtpChange(idx, e.target.value)}
                    onKeyDown={(e) => handleOtpKeyDown(idx, e)}
                    onPaste={idx === 0 ? handleOtpPaste : undefined}
                    className="form-input"
                    style={{
                      textAlign: 'center',
                      fontSize: '20px',
                      fontWeight: '700',
                      padding: '12px 0',
                      height: '52px',
                    }}
                    required
                  />
                ))}
              </div>
            </div>

            <button
              id="verify-otp-btn"
              type="submit"
              className={`auth-btn ${loading ? 'loading' : ''}`}
              disabled={loading || otpDigits.join('').length < 6}
            >
              {loading ? <span className="spinner" /> : 'Verify OTP'}
            </button>

            <button
              type="button"
              id="resend-otp-btn"
              className="auth-btn-ghost"
              onClick={handleResendOTP}
              disabled={loading || cooldown > 0}
            >
              {cooldown > 0 ? `Resend OTP in ${cooldown}s` : 'Resend OTP'}
            </button>

            <button
              type="button"
              className="auth-btn-ghost"
              style={{ fontSize: '12px', padding: '8px' }}
              onClick={() => {
                setStep(STEP_PHONE);
                setError('');
                setInfo('');
              }}
            >
              Change Phone Number
            </button>
          </form>
        )}

        {/* Step 3: Create New Password */}
        {step === STEP_NEW_PASSWORD && (
          <form onSubmit={handleResetPassword} className="auth-form" id="new-password-form">
            <div className="form-group">
              <label htmlFor="new-password">New Password</label>
              <div className="input-wrapper">
                <svg className="input-icon" viewBox="0 0 20 20" fill="currentColor">
                  <path
                    fillRule="evenodd"
                    d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z"
                    clipRule="evenodd"
                  />
                </svg>
                <input
                  id="new-password"
                  type="password"
                  className="form-input"
                  placeholder="New strong password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                  autoFocus
                />
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="confirm-password">Confirm Password</label>
              <div className="input-wrapper">
                <svg className="input-icon" viewBox="0 0 20 20" fill="currentColor">
                  <path
                    fillRule="evenodd"
                    d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z"
                    clipRule="evenodd"
                  />
                </svg>
                <input
                  id="confirm-password"
                  type="password"
                  className="form-input"
                  placeholder="Confirm new password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                />
              </div>
            </div>

            <button
              id="reset-password-btn"
              type="submit"
              className={`auth-btn ${loading ? 'loading' : ''}`}
              disabled={loading}
            >
              {loading ? <span className="spinner" /> : 'Reset Password'}
            </button>
          </form>
        )}

        {/* Step 4: Password Reset Success */}
        {step === STEP_SUCCESS && (
          <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div
              style={{
                width: '64px',
                height: '64px',
                margin: '0 auto',
                borderRadius: '50%',
                background: 'rgba(16,185,129,0.15)',
                border: '2px solid rgba(16,185,129,0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#34D399',
                fontSize: '28px',
              }}
            >
              ✓
            </div>

            <div>
              <h2 style={{ fontSize: '18px', fontWeight: '700', marginBottom: '8px' }}>
                Password Reset Successfully
              </h2>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                Your password has been updated. You can now log in with your new credentials.
              </p>
            </div>

            <button
              id="go-to-login-btn"
              type="button"
              className="auth-btn"
              onClick={() => navigate('/login')}
            >
              Go to Login
            </button>
          </div>
        )}

        {/* Footer */}
        {step !== STEP_SUCCESS && (
          <div className="auth-footer">
            Remember your password?&nbsp;
            <Link to="/login" className="auth-link">
              Sign in
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
