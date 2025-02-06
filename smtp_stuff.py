import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import random

load_dotenv()

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

def send_email(recipient_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = recipient_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.sendmail(EMAIL_ADDRESS, recipient_email, msg.as_string())

        print("Email sent successfully!")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    recipient_email = "recipient@domain.com"  # Enter the recipient email here!!
    subject = "Hello it's a test mail"
    verification_code = random.randint(1000, 9999)
    body = "Your verification code is " + str(verification_code)
    send_email(recipient_email, subject, body)
