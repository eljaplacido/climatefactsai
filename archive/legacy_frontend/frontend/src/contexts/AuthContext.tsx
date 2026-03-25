import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5200';

interface User {
  id: string;
  email: string;
  full_name: string;
  subscription_tier: 'freemium' | 'basic' | 'professional' | 'enterprise';
  is_active: boolean;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  isAuthenticated: boolean;
  isPremium: boolean;
  hasTier: (tier: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('access_token'));
  const [loading, setLoading] = useState(true);

  // Configure axios defaults
  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
      delete axios.defaults.headers.common['Authorization'];
    }
  }, [token]);

  // Load user on mount if token exists
  useEffect(() => {
    const loadUser = async () => {
      if (token) {
        try {
          const response = await axios.get(`${API_URL}/api/auth/me`);
          setUser(response.data);
        } catch (error) {
          console.error('Failed to load user:', error);
          // Token might be expired
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          setToken(null);
        }
      }
      setLoading(false);
    };

    loadUser();
  }, [token]);

  const login = async (email: string, password: string) => {
    try {
      const response = await axios.post(`${API_URL}/api/auth/login`, {
        email,
        password,
      });

      const { access_token, refresh_token, user: userData } = response.data;

      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);
      setToken(access_token);
      setUser(userData);
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Login failed');
    }
  };

  const register = async (email: string, password: string, fullName: string) => {
    try {
      await axios.post(`${API_URL}/api/auth/register`, {
        email,
        password,
        full_name: fullName,
      });

      // Auto-login after registration
      await login(email, password);
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Registration failed');
    }
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setUser(null);
  };

  const refreshToken = async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        throw new Error('No refresh token');
      }

      const response = await axios.post(`${API_URL}/api/auth/refresh`, {
        refresh_token: refreshToken,
      });

      const { access_token } = response.data;
      localStorage.setItem('access_token', access_token);
      setToken(access_token);
    } catch (error) {
      console.error('Token refresh failed:', error);
      logout();
    }
  };

  const hasTier = (tier: string): boolean => {
    if (!user) return false;

    const tierHierarchy = ['freemium', 'basic', 'professional', 'enterprise'];
    const userTierIndex = tierHierarchy.indexOf(user.subscription_tier);
    const requiredTierIndex = tierHierarchy.indexOf(tier);

    return userTierIndex >= requiredTierIndex;
  };

  const value: AuthContextType = {
    user,
    token,
    loading,
    login,
    register,
    logout,
    refreshToken,
    isAuthenticated: !!user,
    isPremium: user ? user.subscription_tier !== 'freemium' : false,
    hasTier,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
