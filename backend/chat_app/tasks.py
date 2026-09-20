from celery import shared_task
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_offline_email_notification(sender_username, receiver_email, receiver_username, message_content):
    """
    Sends an email notification to the receiver when they are offline and receive a message.
    """
    logger.info(f"Sending offline notification email to {receiver_username} ({receiver_email})")
    
    subject = f"New message from {sender_username} on Real-time Chat"
    message = (
        f"Hi {receiver_username},\n\n"
        f"You received a new message from {sender_username} while you were offline:\n\n"
        f"\"{message_content}\"\n\n"
        f"Log in to the chat application to reply!\n\n"
        f"Best regards,\n"
        f"Real-time Chat Team"
    )
    
    html_message = (
        f"<div style='font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px; background-color: #f9f9f9;'>"
        f"  <h2 style='color: #6366f1; margin-top: 0;'>New Message Notification</h2>"
        f"  <p>Hi <strong>{receiver_username}</strong>,</p>"
        f"  <p>You received a new message from <span style='color: #4f46e5; font-weight: bold;'>{sender_username}</span> while you were offline:</p>"
        f"  <div style='background-color: #ffffff; padding: 15px; border-left: 4px solid #6366f1; border-radius: 4px; margin: 20px 0; font-style: italic; color: #4b5563;'>"
        f"    \"{message_content}\""
        f"  </div>"
        f"  <p style='margin-bottom: 25px;'>Click the button below to log in and reply instantly.</p>"
        f"  <div style='text-align: center;'>"
        f"    <a href='http://127.0.0.1:8000/' style='background-color: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;'>Go to Chat</a>"
        f"  </div>"
        f"  <hr style='border: none; border-top: 1px solid #e0e0e0; margin: 30px 0 20px;'>"
        f"  <p style='font-size: 12px; color: #9ca3af; text-align: center;'>This is an automated notification. Please do not reply directly to this email.</p>"
        f"</div>"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'Real-time Chat <noreply@chat.com>'),
            recipient_list=[receiver_email],
            fail_silently=False,
            html_message=html_message
        )
        logger.info(f"Offline notification email successfully sent to {receiver_username}")
        return f"Email sent successfully to {receiver_username}"
    except Exception as e:
        logger.error(f"Failed to send offline notification email: {str(e)}")
        return f"Error sending email: {str(e)}"
