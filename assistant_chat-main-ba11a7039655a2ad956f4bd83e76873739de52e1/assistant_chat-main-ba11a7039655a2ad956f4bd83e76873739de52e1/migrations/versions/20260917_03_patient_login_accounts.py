"""Create new patient login identities without modifying legacy accounts.

Revision ID: 20260917_03
Revises: 20260917_02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260917_03"
down_revision: Union[str, None] = "20260917_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patient_login_accounts",
        sa.Column("id", mysql.CHAR(36, charset="ascii", collation="ascii_bin"), nullable=False),
        sa.Column("id_card_last4", mysql.CHAR(4, charset="ascii", collation="ascii_bin"), nullable=False),
        sa.Column("phone_last4", mysql.CHAR(4, charset="ascii", collation="ascii_bin"), nullable=False),
        sa.Column("login_code", mysql.CHAR(8, charset="ascii", collation="ascii_bin"), nullable=False),
        sa.Column("password_hash", mysql.TEXT(), nullable=False),
        sa.Column("status", mysql.TINYINT(unsigned=True), nullable=False, server_default="1"),
        sa.Column("privacy_consent_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(6)")),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(6)")),
        sa.Column("last_login_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.ForeignKeyConstraint(["id"], ["auth_users.id"], name="fk_patient_login_user", onupdate="RESTRICT", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("login_code", name="uk_patient_login_code_v2"),
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_patient_login_status", "patient_login_accounts", ["status"])
    op.execute(
        "ALTER TABLE patient_login_accounts MODIFY updated_at DATETIME(6) NOT NULL "
        "DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"
    )


def downgrade() -> None:
    op.drop_table("patient_login_accounts")
