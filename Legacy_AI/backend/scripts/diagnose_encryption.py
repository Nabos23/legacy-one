"""Read-only scan for connector secrets that can't be decrypted with the
currently-configured key (ENCRYPTION_KEY, or the JWT_SECRET_KEY-derived
fallback — see backend/core/encryption.py).

A mismatch here means the secret was encrypted by a backend process using a
different ENCRYPTION_KEY/JWT_SECRET_KEY than the one this script (and your
running server) currently resolves — most commonly because different
environments (local .env vs. Docker vs. another teammate's machine) point at
the same shared database but don't agree on those two env vars. It does NOT
mean anyone edited a key by hand.

This script only reads and reports — it changes nothing.

Usage (from project root):
    uv run python -m backend.scripts.diagnose_encryption
"""

import asyncio

from backend.core.encryption import decrypt_or_none
from backend.db.database import connector_credentials_collection, connector_tokens_collection

# Fields worth checking per collection — anything encrypted with `encrypt()`
# when saved (see backend/connectors/services.py).
_TOKEN_FIELDS = ["access_token", "refresh_token"]
_CREDENTIAL_FIELDS = ["client_secret", "signing_secret", "bot_token", "api_key"]


async def _scan(collection, fields: list[str], label: str) -> tuple[int, int]:
    total = 0
    broken = 0
    async for doc in collection.find({}):
        total += 1
        bad_fields = [f for f in fields if doc.get(f) and decrypt_or_none(doc[f]) is None]
        if bad_fields:
            broken += 1
            print(
                f"  [BROKEN] {label} connector_id={doc.get('connector_id')} "
                f"owner_id={doc.get('owner_id')} provider={doc.get('provider_id', '?')} "
                f"undecryptable_fields={bad_fields}"
            )
    return total, broken


async def main() -> None:
    print("Scanning connector_tokens...")
    tok_total, tok_broken = await _scan(connector_tokens_collection, _TOKEN_FIELDS, "token")

    print("\nScanning connector_credentials...")
    cred_total, cred_broken = await _scan(connector_credentials_collection, _CREDENTIAL_FIELDS, "credential")

    print("\n---- Summary ----------------------------------------------")
    print(f"connector_tokens:      {tok_broken}/{tok_total} documents have an undecryptable secret")
    print(f"connector_credentials: {cred_broken}/{cred_total} documents have an undecryptable secret")
    if tok_broken or cred_broken:
        print(
            "\nAffected connectors will show 'Reauthorization required' in the UI. "
            "The fix is to disconnect + reconnect each one — the old secret can't be "
            "recovered, only replaced. If the count is large, check that ENCRYPTION_KEY "
            "and JWT_SECRET_KEY are set identically across every environment that talks "
            "to this database."
        )
    else:
        print("\nNo undecryptable secrets found.")


if __name__ == "__main__":
    asyncio.run(main())
