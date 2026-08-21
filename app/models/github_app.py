from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GitHubApp(Base):
    __tablename__ = "github_apps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    owner: Mapped[str] = mapped_column(String, nullable=False)
    public_key_pem: Mapped[str] = mapped_column(Text, nullable=False)
    private_key_pem: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    client_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    webhook_secret: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    installations = relationship("AppInstallation", back_populates="app", lazy="selectin")


class AppInstallation(Base):
    __tablename__ = "app_installations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_id: Mapped[int] = mapped_column(Integer, ForeignKey("github_apps.id"), nullable=False)
    owner: Mapped[str] = mapped_column(String, nullable=False)
    repo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    app = relationship("GitHubApp", back_populates="installations", lazy="selectin")
    tokens = relationship("InstallationToken", back_populates="installation", lazy="selectin")


class InstallationToken(Base):
    __tablename__ = "installation_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    installation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("app_installations.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    token_prefix: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    installation = relationship("AppInstallation", back_populates="tokens", lazy="selectin")
