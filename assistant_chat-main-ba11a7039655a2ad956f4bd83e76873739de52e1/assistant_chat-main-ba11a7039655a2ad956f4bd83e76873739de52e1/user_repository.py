"""Persistence operations for authentication users."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from account_models import PatientAccount, UserAccount, WeChatIdentity
from passwords import hash_password

USER_STATUS_DISABLED = 0
USER_STATUS_ACTIVE = 1


class DuplicateLoginCodeError(Exception):
    """The requested patient login code already belongs to an account."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserRepository:
    """Repository for internal users and WeChat identity mappings."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: str) -> Optional[UserAccount]:
        return self.db.get(UserAccount, user_id)

    def get_patient_by_user_id(self, user_id: str) -> Optional[PatientAccount]:
        return self.db.get(PatientAccount, user_id)

    def get_patient_by_login_code(self, login_code: str) -> Optional[PatientAccount]:
        return self.db.scalar(
            select(PatientAccount).where(PatientAccount.login_code == login_code)
        )

    def create_patient_account(
        self, *, id_card_last4: str, phone_last4: str, password: str
    ) -> PatientAccount:
        login_code = id_card_last4 + phone_last4
        if self.get_patient_by_login_code(login_code) is not None:
            raise DuplicateLoginCodeError

        now = _utc_now()
        user = UserAccount(id=str(uuid.uuid4()), status=USER_STATUS_ACTIVE)
        patient = PatientAccount(
            id=user.id,
            id_card_last4=id_card_last4,
            phone_last4=phone_last4,
            login_code=login_code,
            password_hash=hash_password(password),
            status=USER_STATUS_ACTIVE,
            privacy_consent_at=now,
        )
        self.db.add_all([user, patient])
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if self.get_patient_by_login_code(login_code) is not None:
                raise DuplicateLoginCodeError from exc
            raise
        return patient

    def record_patient_login(self, patient: PatientAccount) -> None:
        now = _utc_now()
        patient.last_login_at = now
        patient.user.last_login_at = now
        self.db.commit()

    def change_patient_password(self, patient: PatientAccount, new_password: str) -> None:
        patient.password_hash = hash_password(new_password)
        self.db.commit()

    def find_or_create_by_wechat_identity(
        self,
        *,
        appid: str,
        openid: str,
        unionid: Optional[str],
    ) -> UserAccount:
        identity = self._find_wechat_identity(appid=appid, openid=openid)
        if identity is not None:
            if identity.user.status == USER_STATUS_ACTIVE:
                self._record_login(identity, unionid)
            return identity.user

        now = _utc_now()
        user = UserAccount(
            id=str(uuid.uuid4()),
            status=USER_STATUS_ACTIVE,
            last_login_at=now,
        )
        identity = WeChatIdentity(
            user=user,
            appid=appid,
            openid=openid,
            unionid=unionid,
            last_login_at=now,
        )
        self.db.add_all([user, identity])

        try:
            self.db.commit()
            return user
        except IntegrityError:
            self.db.rollback()
            identity = self._find_wechat_identity(appid=appid, openid=openid)
            if identity is None:
                raise
            self._record_login(identity, unionid)
            return identity.user

    def _find_wechat_identity(self, *, appid: str, openid: str) -> Optional[WeChatIdentity]:
        statement = select(WeChatIdentity).where(
            WeChatIdentity.appid == appid,
            WeChatIdentity.openid == openid,
        )
        return self.db.scalar(statement)

    def _record_login(self, identity: WeChatIdentity, unionid: Optional[str]) -> None:
        now = _utc_now()
        identity.last_login_at = now
        identity.user.last_login_at = now
        if unionid and not identity.unionid:
            identity.unionid = unionid
        self.db.commit()
