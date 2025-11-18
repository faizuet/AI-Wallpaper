from fastapi_mail import FastMail, MessageSchema
from app.core.email_config import MAIL_CONFIG

async def send_verification_email(to_email: str, token: str):
    link = f"http://127.0.0.1:8000/auth/verify/{token}"
    subject = "Verify your AI-Wallpaper account"

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #4CAF50;">Welcome to AI-Wallpaper!</h2>
        <p>Hello,</p>
        <p>Thank you for signing up. Please verify your email address by clicking the button below:</p>
        <p style="text-align: center;">
          <a href="{link}" 
             style="background-color:#4CAF50;color:white;padding:12px 24px;
                    text-decoration:none;border-radius:5px;display:inline-block;font-weight:bold;">
             Verify Email
          </a>
        </p>
        <p>This link will expire in 24 hours.</p>
        <p>If you did not sign up, you can safely ignore this email.</p>
        <br>
        <p>Thanks,<br>AI-Wallpaper Team</p>
      </body>
    </html>
    """

    message = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=html,
        subtype="html"  # <-- send as HTML
    )

    fm = FastMail(MAIL_CONFIG)
    await fm.send_message(message)


async def send_password_reset_email(to_email: str, token: str):
    link = f"http://127.0.0.1:8000/auth/reset-password/{token}"
    subject = "Reset your AI-Wallpaper account password"

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #f44336;">Password Reset Request</h2>
        <p>Hello,</p>
        <p>We received a request to reset your password. Click the button below to set a new password:</p>
        <p style="text-align: center;">
          <a href="{link}" 
             style="background-color:#f44336;color:white;padding:12px 24px;
                    text-decoration:none;border-radius:5px;display:inline-block;font-weight:bold;">
             Reset Password
          </a>
        </p>
        <p>This link will expire in 15 minutes.</p>
        <p>If you did not request this, you can safely ignore this email.</p>
        <br>
        <p>Thanks,<br>AI-Wallpaper Team</p>
      </body>
    </html>
    """

    message = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=html,
        subtype="html"  # <-- send as HTML
    )

    fm = FastMail(MAIL_CONFIG)
    await fm.send_message(message)

