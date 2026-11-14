"""Salted password hashes; old plaintext records are deliberately rejected."""

import hashlib
import secrets

ITERATIONS = 600_000
ALGORITHM = "pbkdf2_sha256"
DUMMY_HASH = f"{ALGORITHM}$600000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"{ALGORITHM}${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_text, digest_text = encoded.split("$")
        salt, expected = bytes.fromhex(salt_text), bytes.fromhex(digest_text)
        if (
            algorithm != ALGORITHM
            or rounds != str(ITERATIONS)
            or len(salt) != 16
            or len(expected) != 32
        ):
            return False
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return secrets.compare_digest(actual, expected)
