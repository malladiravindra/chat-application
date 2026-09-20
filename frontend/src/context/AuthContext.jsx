import { createContext, useContext, useState, useCallback } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [accessToken, setAccessToken] = useState(
    () => localStorage.getItem('access_token') || null
  );
  const [userPhone, setUserPhone] = useState(
    () => localStorage.getItem('user_phone') || null
  );

  const login = useCallback((access, refresh, phone) => {
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
    localStorage.setItem('user_phone', phone);
    setAccessToken(access);
    setUserPhone(phone);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_phone');
    setAccessToken(null);
    setUserPhone(null);
  }, []);

  return (
    <AuthContext.Provider value={{ accessToken, userPhone, login, logout, isAuthenticated: !!accessToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
