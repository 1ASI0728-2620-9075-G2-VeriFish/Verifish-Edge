import hashlib
import hmac


def sign(body: str, key: str) -> str:
    """Firma HMAC-SHA256 en hex minúsculas del body usando key como secreto."""
    return hmac.new(
        key.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
