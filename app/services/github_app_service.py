"""GitHub App service — app management, JWT validation, installation tokens."""

import hashlib
import re
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.github_app import AppInstallation, GitHubApp, InstallationToken


def _generate_rsa_keypair() -> tuple[str, str]:
    """Generate an RSA 2048-bit keypair. Returns (private_pem, public_pem)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "app"


def _generate_client_id() -> str:
    return f"Iv1.{''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(12))}"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _generate_installation_token() -> tuple[str, str, str]:
    """Generate a ghs_ installation token. Returns (full_token, hash, prefix)."""
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(36))
    full_token = f"ghs_{random_part}"
    return full_token, _hash_token(full_token), full_token[:8]


async def create_app(
    db: AsyncSession, name: str, owner: str
) -> tuple[GitHubApp, str]:
    """Create a new GitHub App. Returns (app, private_key_pem)."""
    private_pem, public_pem = _generate_rsa_keypair()
    slug = _slugify(name)

    # Ensure unique slug
    base_slug = slug
    counter = 1
    while True:
        existing = await db.execute(
            select(GitHubApp).where(GitHubApp.slug == slug)
        )
        if existing.scalar_one_or_none() is None:
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    app = GitHubApp(
        name=name,
        slug=slug,
        owner=owner,
        public_key_pem=public_pem,
        private_key_pem=private_pem,
        client_id=_generate_client_id(),
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app, private_pem


async def get_app(db: AsyncSession, app_id: int) -> Optional[GitHubApp]:
    result = await db.execute(select(GitHubApp).where(GitHubApp.id == app_id))
    return result.scalar_one_or_none()


async def list_apps(db: AsyncSession) -> list[GitHubApp]:
    result = await db.execute(select(GitHubApp))
    return list(result.scalars().all())


async def regenerate_private_key(
    db: AsyncSession, app_id: int
) -> Optional[tuple[GitHubApp, str]]:
    """Regenerate RSA keypair. Returns (app, new_private_pem) or None."""
    app = await get_app(db, app_id)
    if app is None:
        return None
    private_pem, public_pem = _generate_rsa_keypair()
    app.public_key_pem = public_pem
    app.private_key_pem = private_pem
    await db.commit()
    await db.refresh(app)
    return app, private_pem


async def create_installation(
    db: AsyncSession, app_id: int, owner: str, repo: Optional[str] = None
) -> Optional[AppInstallation]:
    app = await get_app(db, app_id)
    if app is None:
        return None
    installation = AppInstallation(app_id=app_id, owner=owner, repo=repo)
    db.add(installation)
    await db.commit()
    await db.refresh(installation)
    return installation


async def get_installation(
    db: AsyncSession, installation_id: int
) -> Optional[AppInstallation]:
    result = await db.execute(
        select(AppInstallation).where(AppInstallation.id == installation_id)
    )
    return result.scalar_one_or_none()


async def list_installations(
    db: AsyncSession, app_id: int
) -> list[AppInstallation]:
    result = await db.execute(
        select(AppInstallation).where(AppInstallation.app_id == app_id)
    )
    return list(result.scalars().all())


async def create_installation_token(
    db: AsyncSession, installation_id: int
) -> Optional[tuple[str, InstallationToken]]:
    """Create an installation access token. Returns (raw_token, token_obj) or None."""
    installation = await get_installation(db, installation_id)
    if installation is None:
        return None
    full_token, token_hash, prefix = _generate_installation_token()
    token = InstallationToken(
        installation_id=installation_id,
        token_hash=token_hash,
        token_prefix=prefix,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return full_token, token


async def validate_jwt(db: AsyncSession, token: str) -> Optional[GitHubApp]:
    """Validate a JWT and return the associated GitHubApp."""
    try:
        if settings.APP_JWT_PERMISSIVE:
            unverified = jwt.get_unverified_claims(token)
            app_id = int(unverified.get("iss", 0))
            app = await get_app(db, app_id)
            return app

        unverified = jwt.get_unverified_claims(token)
        app_id = int(unverified.get("iss", 0))
        app = await get_app(db, app_id)
        if app is None:
            return None

        jwt.decode(token, app.public_key_pem, algorithms=["RS256"])
        return app
    except (JWTError, ValueError, KeyError):
        return None


async def validate_installation_token(
    db: AsyncSession, token: str
) -> Optional[InstallationToken]:
    """Validate a ghs_ installation token. Returns token record or None."""
    token_hash = _hash_token(token)
    result = await db.execute(
        select(InstallationToken).where(
            InstallationToken.token_hash == token_hash
        )
    )
    inst_token = result.scalar_one_or_none()
    if inst_token is None:
        return None
    if inst_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return None
    return inst_token
