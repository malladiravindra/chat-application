import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authAPI } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import '../styles/auth.css';

const STEP_REGISTER = 1;
const STEP_OTP = 2;

export default function RegisterPage() {
  const [step, setStep] = useState(STEP_REGISTER);
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleRegister(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await authAPI.register(phone, password, confirmPassword);
      setInfo('OTP sent to your phone. Enter it below.');
      setStep(STEP_OTP);
    } catch (err) {
      setError(err.response?.data?.error || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  async function handleVerify(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { data } = await authAPI.verifyOTP(phone, otp, 'register');
      login(data.access, data.refresh, phone);
      navigate('/chat');
    } catch (err) {
      setError(err.response?.data?.error || 'OTP verification failed.');
    } finally {
      setLoading(false);
    }
  }

  async function handleResendOTP() {
    setError('');
    setInfo('');
    try {
      await authAPI.sendOTP(phone, 'register');
      setInfo('OTP resent successfully.');
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to resend OTP.');
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="auth-logo">
            <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="40" height="40" rx="12" fill="url(#lg2)"/>
              <path d="M10 28l4-8 6 4 6-10 4 14" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
              <defs>
                <linearGradient id="lg2" x1="0" y1="0" x2="40" y2="40">
                  <stop stopColor="#6366F1"/>
                  <stop offset="1" stopColor="#8B5CF6"/>
                </linearGradient>
              </defs>
            </svg>
          </div>
          <h1 className="auth-title">TextWave</h1>
          <p className="auth-subtitle">
            {step === STEP_REGISTER ? 'Create your account' : 'Verify your phone'}
          </p>
        </div>

        {/* Step indicator */}
        <div className="step-indicator">
          <div className={`step-dot ${step >= STEP_REGISTER ? 'active' : ''}`} />
          <div className="step-line" />
          <div className={`step-dot ${step >= STEP_OTP ? 'active' : ''}`} />
        </div>

        {error && (
          <div className="auth-error" role="alert">
            <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
            </svg>
            {error}
          </div>
        )}
        {info && <div className="auth-info">{info}</div>}

        {step === STEP_REGISTER ? (
          <form onSubmit={handleRegister} className="auth-form" id="register-form">
            <div className="form-group">
              <label htmlFor="reg-phone">Phone Number</label>
              <div className="input-wrapper">
                <svg className="input-icon" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 01-.54 1.06l-1.548.773a11.037 11.037 0 006.105 6.105l.774-1.548a1 1 0 011.059-.54l4.435.74a1 1 0 01.836.986V17a1 1 0 01-1 1h-2C7.82 18 2 12.18 2 5V3z"/>
                </svg>
                <input id="reg-phone" type="tel" className="form-input" placeholder="+919876543210"
                  value={phone} onChange={(e) => setPhone(e.target.value)} required autoComplete="tel"/>
              </div>
            </div>
            <div className="form-group">
              <label htmlFor="reg-password">Password</label>
              <div className="input-wrapper">
                <svg className="input-icon" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd"/>
                </svg>
                <input id="reg-password" type="password" className="form-input" placeholder="At least 8 characters"
                  value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password"/>
              </div>
            </div>
            <div className="form-group">
              <label htmlFor="reg-confirm">Confirm Password</label>
              <div className="input-wrapper">
                <svg className="input-icon" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd"/>
                </svg>
                <input id="reg-confirm" type="password" className="form-input" placeholder="Repeat password"
                  value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required autoComplete="new-password"/>
              </div>
            </div>
            <button id="register-btn" type="submit" className={`auth-btn ${loading ? 'loading' : ''}`} disabled={loading}>
              {loading ? <span className="spinner" /> : 'Create Account'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerify} className="auth-form" id="otp-form">
            <p className="otp-hint">We sent a 6-digit code to <strong>{phone}</strong></p>
            <div className="form-group">
              <label htmlFor="otp-input">Verification Code</label>
              <div className="input-wrapper">
                <svg className="input-icon" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/><path fillRule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clipRule="evenodd"/>
                </svg>
                <input id="otp-input" type="text" className="form-input otp-input" placeholder="123456"
                  maxLength={6} value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                  required inputMode="numeric" autoComplete="one-time-code"/>
              </div>
            </div>
            <button id="verify-otp-btn" type="submit" className={`auth-btn ${loading ? 'loading' : ''}`} disabled={loading}>
              {loading ? <span className="spinner" /> : 'Verify & Sign In'}
            </button>
            <button type="button" id="resend-otp-btn" className="auth-btn-ghost" onClick={handleResendOTP}>
              Resend OTP
            </button>
          </form>
        )}

        <div className="auth-footer">
          Already have an account?&nbsp;
          <Link to="/login" className="auth-link">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
