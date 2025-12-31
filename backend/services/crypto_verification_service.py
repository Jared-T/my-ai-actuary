"""
Cryptographic verification service for audit trail integrity.

Provides:
- SHA-256 hash generation and verification for artifacts
- HMAC-based signatures for audit log integrity
- Chain verification for tamper detection
- Content fingerprinting for deduplication
"""

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from core.logging import get_logger

logger = get_logger(__name__)

# Default secret for HMAC signing - should be configured via environment in production
DEFAULT_SIGNING_SECRET = "audit-trail-signing-secret-change-in-production"


class CryptoVerificationService:
    """
    Service for cryptographic operations on audit trail data.

    Provides hash generation, verification, and integrity checking
    for artifacts and audit records.
    """

    def __init__(self, signing_secret: Optional[str] = None) -> None:
        """
        Initialize the crypto verification service.

        Args:
            signing_secret: Secret key for HMAC signatures. Uses default if not provided.
        """
        self._signing_secret = (signing_secret or DEFAULT_SIGNING_SECRET).encode("utf-8")

    def generate_content_hash(self, content: bytes) -> str:
        """
        Generate SHA-256 hash of binary content.

        Args:
            content: Binary content to hash

        Returns:
            64-character hex string of SHA-256 hash
        """
        return hashlib.sha256(content).hexdigest()

    def generate_string_hash(self, text: str) -> str:
        """
        Generate SHA-256 hash of string content.

        Args:
            text: String content to hash

        Returns:
            64-character hex string of SHA-256 hash
        """
        return self.generate_content_hash(text.encode("utf-8"))

    def generate_json_hash(self, data: dict[str, Any]) -> str:
        """
        Generate deterministic SHA-256 hash of JSON data.

        Args:
            data: Dictionary to hash (will be serialized with sorted keys)

        Returns:
            64-character hex string of SHA-256 hash
        """
        # Use sorted keys and no extra whitespace for deterministic output
        json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return self.generate_string_hash(json_str)

    def verify_content_hash(self, content: bytes, expected_hash: str) -> bool:
        """
        Verify that content matches its expected hash.

        Args:
            content: Binary content to verify
            expected_hash: Expected SHA-256 hash

        Returns:
            True if hash matches, False otherwise
        """
        actual_hash = self.generate_content_hash(content)
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(actual_hash, expected_hash.lower())

    def generate_audit_signature(
        self,
        audit_id: UUID,
        action: str,
        resource_type: str,
        timestamp: datetime,
        user_id: Optional[UUID] = None,
        previous_signature: Optional[str] = None,
    ) -> str:
        """
        Generate HMAC signature for an audit log entry.

        Creates a chain by including the previous signature, enabling
        tamper detection across the audit trail.

        Args:
            audit_id: Unique identifier of the audit entry
            action: Action type being audited
            resource_type: Type of resource being acted upon
            timestamp: Timestamp of the audit event
            user_id: ID of the user performing the action (optional)
            previous_signature: Signature of the previous audit entry for chaining

        Returns:
            64-character hex string of HMAC-SHA256 signature
        """
        # Build the message to sign
        message_parts = [
            str(audit_id),
            action,
            resource_type,
            timestamp.isoformat(),
            str(user_id) if user_id else "system",
            previous_signature or "genesis",
        ]
        message = "|".join(message_parts).encode("utf-8")

        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self._signing_secret,
            message,
            hashlib.sha256,
        ).hexdigest()

        logger.debug(
            "Generated audit signature",
            audit_id=str(audit_id),
            action=action,
            has_previous=previous_signature is not None,
        )

        return signature

    def verify_audit_signature(
        self,
        signature: str,
        audit_id: UUID,
        action: str,
        resource_type: str,
        timestamp: datetime,
        user_id: Optional[UUID] = None,
        previous_signature: Optional[str] = None,
    ) -> bool:
        """
        Verify an audit log entry's signature.

        Args:
            signature: The signature to verify
            audit_id: Unique identifier of the audit entry
            action: Action type being audited
            resource_type: Type of resource being acted upon
            timestamp: Timestamp of the audit event
            user_id: ID of the user performing the action (optional)
            previous_signature: Signature of the previous audit entry

        Returns:
            True if signature is valid, False otherwise
        """
        expected_signature = self.generate_audit_signature(
            audit_id=audit_id,
            action=action,
            resource_type=resource_type,
            timestamp=timestamp,
            user_id=user_id,
            previous_signature=previous_signature,
        )
        return hmac.compare_digest(signature, expected_signature)

    def generate_artifact_fingerprint(
        self,
        content_hash: str,
        file_name: str,
        file_size: int,
        created_at: datetime,
    ) -> str:
        """
        Generate a unique fingerprint for an artifact.

        Combines content hash with metadata for a comprehensive fingerprint.

        Args:
            content_hash: SHA-256 hash of the file content
            file_name: Original filename
            file_size: Size in bytes
            created_at: Creation timestamp

        Returns:
            64-character hex string fingerprint
        """
        fingerprint_data = {
            "content_hash": content_hash,
            "file_name": file_name,
            "file_size": file_size,
            "created_at": created_at.isoformat(),
        }
        return self.generate_json_hash(fingerprint_data)

    def verify_chain_integrity(
        self,
        audit_entries: list[dict[str, Any]],
    ) -> tuple[bool, Optional[int], Optional[str]]:
        """
        Verify the integrity of an audit chain.

        Checks that each entry's signature correctly chains to the previous.

        Args:
            audit_entries: List of audit entries in chronological order.
                Each entry must have: id, action, resource_type, created_at,
                user_id (optional), signature, previous_signature (optional)

        Returns:
            Tuple of (is_valid, failed_index, error_message)
            - is_valid: True if entire chain is valid
            - failed_index: Index of first invalid entry (None if valid)
            - error_message: Description of the failure (None if valid)
        """
        if not audit_entries:
            return True, None, None

        for i, entry in enumerate(audit_entries):
            expected_previous = (
                audit_entries[i - 1].get("signature") if i > 0 else None
            )

            # Verify this entry's signature
            if not self.verify_audit_signature(
                signature=entry["signature"],
                audit_id=entry["id"],
                action=entry["action"],
                resource_type=entry["resource_type"],
                timestamp=entry["created_at"],
                user_id=entry.get("user_id"),
                previous_signature=expected_previous,
            ):
                return (
                    False,
                    i,
                    f"Invalid signature at entry {i} (ID: {entry['id']})",
                )

            # Verify chain linkage
            stored_previous = entry.get("previous_signature")
            if i > 0 and stored_previous != expected_previous:
                return (
                    False,
                    i,
                    f"Chain broken at entry {i}: previous signature mismatch",
                )

        return True, None, None

    def generate_verification_token(self) -> str:
        """
        Generate a secure random verification token.

        Useful for one-time verification links or confirmation codes.

        Returns:
            64-character URL-safe random token
        """
        return secrets.token_urlsafe(48)

    def generate_report_hash(
        self,
        report_data: dict[str, Any],
        generated_at: datetime,
        generated_by: Optional[UUID] = None,
    ) -> str:
        """
        Generate a verification hash for a compliance report.

        Args:
            report_data: The report data to hash
            generated_at: Report generation timestamp
            generated_by: ID of user who generated the report

        Returns:
            64-character hex string hash
        """
        verification_data = {
            "report": report_data,
            "generated_at": generated_at.isoformat(),
            "generated_by": str(generated_by) if generated_by else "system",
        }
        return self.generate_json_hash(verification_data)


# Singleton instance for global access
_crypto_service: Optional[CryptoVerificationService] = None


def get_crypto_service(signing_secret: Optional[str] = None) -> CryptoVerificationService:
    """
    Get the global crypto verification service instance.

    Args:
        signing_secret: Optional secret key (only used on first call)

    Returns:
        Configured CryptoVerificationService instance
    """
    global _crypto_service
    if _crypto_service is None:
        _crypto_service = CryptoVerificationService(signing_secret)
    return _crypto_service
