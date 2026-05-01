from flask_mail import Message
from app import mail


def send_receipt_email(user, amount, payment_type, reference):

    msg = Message(
        subject="Payment Receipt - Nestora",
        recipients=[user.email]
    )

    msg.html = f"""
    <h2>Payment Successful 🎉</h2>
    <p>Hello <b>{user.name}</b>,</p>

    <ul>
        <li>Amount: ₦{amount}</li>
        <li>Type: {payment_type}</li>
        <li>Reference: {reference}</li>
    </ul>
    """

    mail.send(msg)