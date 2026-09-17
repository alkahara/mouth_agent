"""SQLAlchemy models for Server users and login identities."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME, TINYINT, VARCHAR, TEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class UserAccount(Base):
    """Internal Server user account."""

    __tablename__ = "auth_users"

    id: Mapped[str] = mapped_column(
        CHAR(36, charset="ascii", collation="ascii_bin"), primary_key=True
    )
    status: Mapped[int] = mapped_column(
        TINYINT(unsigned=True), nullable=False, default=1
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DATETIME(fsp=6))

    wechat_identity: Mapped[Optional["WeChatIdentity"]] = relationship(
        back_populates="user", uselist=False
    )
    patient_identity: Mapped[Optional["PatientAccount"]] = relationship(
        back_populates="user", uselist=False
    )

    __table_args__ = (Index("idx_auth_users_status", "status"),)


class WeChatIdentity(Base):
    """Mapping from a WeChat Mini Program identity to a Server user."""

    __tablename__ = "auth_wechat_identities"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        CHAR(36, charset="ascii", collation="ascii_bin"),
        ForeignKey("auth_users.id", onupdate="RESTRICT", ondelete="RESTRICT"),
        nullable=False,
    )
    appid: Mapped[str] = mapped_column(
        VARCHAR(32, charset="ascii", collation="ascii_bin"), nullable=False
    )
    openid: Mapped[str] = mapped_column(
        VARCHAR(128, charset="ascii", collation="ascii_bin"), nullable=False
    )
    unionid: Mapped[Optional[str]] = mapped_column(
        VARCHAR(128, charset="ascii", collation="ascii_bin")
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DATETIME(fsp=6))

    user: Mapped[UserAccount] = relationship(back_populates="wechat_identity")

    __table_args__ = (
        UniqueConstraint("user_id", name="uk_wechat_user_id"),
        Index("uk_wechat_appid_openid", "appid", "openid", unique=True),
        Index("idx_wechat_unionid", "unionid"),
    )


class PatientAccount(Base):
    """Password identity for a new platform patient account."""

    __tablename__ = "patient_login_accounts"

    id: Mapped[str] = mapped_column(
        CHAR(36, charset="ascii", collation="ascii_bin"),
        ForeignKey("auth_users.id", onupdate="RESTRICT", ondelete="RESTRICT"),
        primary_key=True,
    )
    id_card_last4: Mapped[str] = mapped_column(
        CHAR(4, charset="ascii", collation="ascii_bin"), nullable=False
    )
    phone_last4: Mapped[str] = mapped_column(
        CHAR(4, charset="ascii", collation="ascii_bin"), nullable=False
    )
    login_code: Mapped[str] = mapped_column(
        CHAR(8, charset="ascii", collation="ascii_bin"), nullable=False
    )
    password_hash: Mapped[str] = mapped_column(TEXT, nullable=False)
    status: Mapped[int] = mapped_column(TINYINT(unsigned=True), nullable=False, default=1)
    privacy_consent_at: Mapped[Optional[datetime]] = mapped_column(DATETIME(fsp=6))
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False, server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    last_login_at: Mapped[Optional[datetime]] = mapped_column(DATETIME(fsp=6))

    user: Mapped[UserAccount] = relationship(back_populates="patient_identity")

    __table_args__ = (
        UniqueConstraint("login_code", name="uk_patient_login_code_v2"),
        Index("idx_patient_login_status", "status"),
    )
