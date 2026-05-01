import requests
from flask import current_app


# -------------------------
# INIT PAYMENT (Paystack)
# -------------------------
def initialize_payment(email, amount, callback_url, metadata=None):

    secret = current_app.config.get("PAYSTACK_SECRET_KEY")

    if not secret:
        raise ValueError("PAYSTACK_SECRET_KEY not configured")

    url = "https://api.paystack.co/transaction/initialize"

    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json"
    }

    data = {
        "email": email,
        "amount": int(amount) * 100,  # convert to kobo
        "callback_url": callback_url,
        "metadata": metadata or {}
    }

    response = requests.post(url, json=data, headers=headers)
    return response.json()


# -------------------------
# VERIFY PAYMENT
# -------------------------
def verify_transaction(reference):

    secret = current_app.config.get("PAYSTACK_SECRET_KEY")

    if not secret:
        raise ValueError("PAYSTACK_SECRET_KEY not configured")

    url = f"https://api.paystack.co/transaction/verify/{reference}"

    headers = {
        "Authorization": f"Bearer {secret}"
    }

    response = requests.get(url, headers=headers)
    return response.json()