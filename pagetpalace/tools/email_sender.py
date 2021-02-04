# Python standard.
import smtplib
import ssl
from typing import List
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Local.
from pagetpalace.config import EMAIL_ADDRESS, EMAIL_ACCOUNT_PASSWORD, EMAIL_DEFAULT_RECEIVERS


class EmailSender:
    SENDER = EMAIL_ADDRESS
    SMTP_SERVER = "smtp.gmail.com"
    PORT = 465

    def __init__(self, receivers: List[str] = None):
        self.receivers = receivers if receivers else EMAIL_DEFAULT_RECEIVERS
        self.context = ssl.create_default_context()

    def _create_message(self, subject: str, body: str, receiver: str) -> MIMEMultipart:
        message = MIMEMultipart()
        message["From"] = self.SENDER
        message["To"] = receiver
        message["Subject"] = subject
        message["Bcc"] = receiver
        message.attach(MIMEText(body, "plain"))

        return message

    def send_mail(self, subject: str, body: str):
        with smtplib.SMTP_SSL("smtp.gmail.com", self.PORT, context=self.context) as server:
            server.login(self.SENDER, EMAIL_ACCOUNT_PASSWORD)
            for receiver in self.receivers:
                message = self._create_message(subject, body, receiver)
                server.sendmail(self.SENDER, receiver, message.as_string())
