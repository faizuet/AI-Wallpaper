from fastapi_mail import FastMail, MessageSchema
from app.core.email_config import MAIL_CONFIG
from fastapi import HTTPException
import logging

fm = FastMail(MAIL_CONFIG)

async def _send_email(subject: str, to_email: str, html: str):
    """Helper to send an HTML email with error handling."""
    message = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=html,
        subtype="html"
    )
    try:
        await fm.send_message(message)
    except Exception as e:
        logging.error(f"Failed to send email to {to_email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")


async def send_verification_code_email(to_email: str, code: int):
    """Send a 6-digit verification code to the user's email."""
    subject = "Verify your AI-Wallpaper account"
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #6A0DAD;">Welcome to AI-Wallpaper!</h2>
        <p>Hello,</p>
        <p>Your verification code is:</p>
        <p style="text-align: center; font-size: 24px; font-weight: bold; color: #6A0DAD;">
          {code}
        </p>
        <p>This code will expire in 15 minutes.</p>
        <p>If you did not sign up, you can safely ignore this email.</p>
        <br>
        <p>Thanks,<br>AI-Wallpaper Team</p>
      </body>
    </html>
    """
    await _send_email(subject, to_email, html)


async def send_password_reset_code_email(to_email: str, code: int):
    """Send a 6-digit password reset code to the user's email."""
    subject = "Reset your AI-Wallpaper account password"
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #6A0DAD;">Password Reset Request</h2>
        <p>Hello,</p>
        <p>Your password reset code is:</p>
        <p style="text-align: center; font-size: 24px; font-weight: bold; color: #6A0DAD;">
          {code}
        </p>
        <p>This code will expire in 15 minutes.</p>
        <p>If you did not request this, you can safely ignore this email.</p>
        <br>
        <p>Thanks,<br>AI-Wallpaper Team</p>
      </body>
    </html>
    """
    await _send_email(subject, to_email, html)

