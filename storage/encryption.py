"""Encrypt/decrypt functions for sensitive account credentials.

Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
Key is always passed as a parameter — no global state.
"""

from cryptography.fernet import Fernet, InvalidToken

from exceptions import CredentialDecryptionError


def encrypt(value: str, key: bytes) -> str:
    """Encrypt a plaintext string and return a base64-encoded ciphertext.

    Args:
        value: The plaintext string to encrypt.
        key: A valid Fernet key (32 url-safe base64-encoded bytes).

    Returns:
        Base64-encoded encrypted string.
    """
    f = Fernet(key)
    return f.encrypt(value.encode()).decode()


def decrypt(value: str, key: bytes) -> str:
    """Decrypt a base64-encoded ciphertext and return the plaintext string.

    Args:
        value: The base64-encoded encrypted string.
        key: The same Fernet key used for encryption.

    Returns:
        Decrypted plaintext string.

    Raises:
        CredentialDecryptionError: If decryption fails (wrong key, corrupted data).
    """
    f = Fernet(key)
    try:
        return f.decrypt(value.encode()).decode()
    except (InvalidToken, Exception) as e:
        raise CredentialDecryptionError(
            f"Failed to decrypt credential. Check that METAMIND_ENCRYPTION_KEY is correct. "
            f"Detail: {e}"
        ) from e


# Hook point for key rotation:
# To rotate keys, decrypt all stored credentials with the old key,
# then re-encrypt with the new key using the functions above.
