import hmac
import hashlib


def verify_x_hub_signature(app_secret: str, request_body: bytes, x_hub_signature: str) -> bool:
    # Parse the signature
    try:
        algo, signature = x_hub_signature.split("=")
    except ValueError:
        return False
    if algo != "sha1":
        return False

    expected_signature = hmac.new(
        app_secret.encode(), request_body, hashlib.sha1
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)