from twilio.rest import Client
import os

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")

client = Client(account_sid, auth_token)

def send_whatsapp_message(phone, message):

    client.messages.create(
        from_='whatsapp:+14155238886',
        body=message,
        to=f'whatsapp:{phone}'
    )

    print("Message request sent to Twilio")