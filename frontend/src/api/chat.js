import axiosInstance from './axiosInstance';

export const chatAPI = {
  /**
   * POST /api/chat/send-sms/
   * @param {string} phone_number  E.164 recipient number
   * @param {string} message       SMS body
   */
  sendSMS: (phone_number, message) =>
    axiosInstance.post('/api/chat/send-sms/', { phone_number, message }),

  /**
   * GET /api/chat/conversations/
   * Returns all conversations for the authenticated user.
   */
  listConversations: () =>
    axiosInstance.get('/api/chat/conversations/'),

  /**
   * GET /api/chat/conversations/<id>/messages/
   * Returns full message history for a conversation.
   */
  getMessages: (conversationId) =>
    axiosInstance.get(`/api/chat/conversations/${conversationId}/messages/`),
};
