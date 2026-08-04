"""Utilidades criptograficas - Hashing, encriptacion, firma digital."""
import hashlib
import hmac
import secrets
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("aegis.crypto")


def generate_sha256(data: bytes) -> str:
    """Genera hash SHA-256 de datos binarios."""
    return hashlib.sha256(data).hexdigest()


def generate_blake2b(data: bytes, key: Optional[bytes] = None) -> str:
    """Genera hash Blake2b (mas rapido que SHA-256)."""
    return hashlib.blake2b(data, key=key).hexdigest()


def verify_file_integrity(file_path: Path, expected_hash: str) -> bool:
    """Verifica integridad de archivo contra hash esperado."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    computed = hasher.hexdigest()
    result = hmac.compare_digest(computed, expected_hash)
    logger.info("file_integrity_check", path=str(file_path), valid=result)
    return result


def encrypt_field(plaintext: str, key: bytes) -> bytes:
    """Encripta un campo con AES-256-GCM."""
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ciphertext


def decrypt_field(ciphertext: bytes, key: bytes) -> str:
    """Desencripta un campo con AES-256-GCM."""
    nonce, encrypted = ciphertext[:12], ciphertext[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, encrypted, None)
    return plaintext.decode("utf-8")


def generate_rsa_keypair(key_size: int = 4096) -> tuple[bytes, bytes]:
    """Genera par de claves RSA para firma digital."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def sign_evidence(data: bytes, private_key_pem: bytes) -> bytes:
    """Firma evidencia digital con RSA-PSS."""
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    signature = private_key.sign(
        data,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )
    return signature


def verify_evidence_signature(data: bytes, signature: bytes, public_key_pem: bytes) -> bool:
    """Verifica firma digital de evidencia."""
    try:
        public_key = serialization.load_pem_public_key(public_key_pem)
        public_key.verify(
            signature,
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def generate_secure_token(length: int = 32) -> str:
    """Genera token criptograficamente seguro."""
    return secrets.token_urlsafe(length)
