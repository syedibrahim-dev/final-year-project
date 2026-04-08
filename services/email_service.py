import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.settings import settings
import ssl

class EmailService:
    @staticmethod
    def send_email(to_email: str, subject: str, html_content: str) -> bool:
        """
        Sends an email using SMTP.
        Uses credentials defined in settings (from .env).
        Returns True if successful, False otherwise.
        """
        if not settings.SMTP_EMAIL or not settings.SMTP_PASSWORD:
            print("⚠️ SMTP credentials not configured. Skipping real email send.")
            return False
            
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = settings.SMTP_EMAIL
            message["To"] = to_email

            # Create the plain-text and HTML version of your message
            part = MIMEText(html_content, "html")
            message.attach(part)

            # Create a secure SSL context
            context = ssl.create_default_context()
            
            # Try to connect to the server and send email
            # Assuming Gmail for default configuration
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                server.login(settings.SMTP_EMAIL, settings.SMTP_PASSWORD)
                server.sendmail(
                    settings.SMTP_EMAIL, to_email, message.as_string()
                )
            print(f"✅ Successfully sent email to {to_email}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send email to {to_email}: {str(e)}")
            return False
