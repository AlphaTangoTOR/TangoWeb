"""TangoWeb site configuration — override via environment variables."""

from __future__ import annotations

import os

GITHUB_URL = os.environ.get("TANGOWEB_GITHUB_URL", "https://github.com/AlphaTangoTOR/TangoWeb")

OPERATOR = {
    "display_name": os.environ.get("TANGOWEB_OPERATOR_NAME", "TangoWeb Operator"),
    "email": os.environ.get("TANGOWEB_OPERATOR_EMAIL", "operator@tangoweb.example"),
    "jabber": os.environ.get("TANGOWEB_OPERATOR_JABBER", "operator@tangoweb.example"),
    "pgp_fingerprint": os.environ.get(
        "TANGOWEB_OPERATOR_PGP_FINGERPRINT",
        "0000 0000 0000 0000 0000 0000 0000 0000 0000 0000",
    ),
    "pgp_key": os.environ.get(
        "TANGOWEB_OPERATOR_PGP_KEY",
        """-----BEGIN PGP PUBLIC KEY BLOCK-----

mQINBGexampleQBEADexamplePlaceholderReplaceWithYourRealKey
Contact the operator to obtain the current public key.

-----END PGP PUBLIC KEY BLOCK-----""",
    ),
}

# Cryptocurrency donation wallets (add your wallet addresses here)
CRYPTO_WALLETS = {
    "bitcoin": os.environ.get("TANGOWEB_WALLET_BITCOIN", ""),
    "ethereum": os.environ.get("TANGOWEB_WALLET_ETHEREUM", ""),
    "monero": os.environ.get("TANGOWEB_WALLET_MONERO", ""),
}
