import axiosInstance from './axiosInstance';

export const authAPI = {
  register: (phone_number, password, confirm_password) =>
    axiosInstance.post('/api/auth/register/', { phone_number, password, confirm_password }),

  sendOTP: (phone_number, purpose = 'register') =>
    axiosInstance.post('/api/auth/send-otp/', { phone_number, purpose }),

  verifyOTP: (phone_number, otp, purpose = 'register') =>
    axiosInstance.post('/api/auth/verify-otp/', { phone_number, otp, purpose }),

  login: (phone_number, password) =>
    axiosInstance.post('/api/auth/login/', { phone_number, password }),

  forgotPassword: (phone_number) =>
    axiosInstance.post('/api/auth/forgot-password/', { phone_number }),

  resendOTP: (phone_number) =>
    axiosInstance.post('/api/auth/resend-otp/', { phone_number }),

  resetPassword: (tokenOrPhone, p2, p3, p4) => {
    // If 3 arguments: (reset_token, new_password, confirm_password)
    if (p4 === undefined) {
      return axiosInstance.post('/api/auth/reset-password/', {
        reset_token: tokenOrPhone,
        new_password: p2,
        confirm_password: p3,
      });
    }
    // If 4 arguments: (phone_number, otp, new_password, confirm_password)
    return axiosInstance.post('/api/auth/reset-password/', {
      phone_number: tokenOrPhone,
      otp: p2,
      new_password: p3,
      confirm_password: p4,
    });
  },
};
