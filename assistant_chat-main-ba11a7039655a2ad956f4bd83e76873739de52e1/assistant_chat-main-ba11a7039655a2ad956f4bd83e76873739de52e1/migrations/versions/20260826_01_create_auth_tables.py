"""Create Server user and WeChat identity tables.

Revision ID: 20260826_01
Revises:
Create Date: 2026-08-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260826_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_users",
        sa.Column(
            "id",
            mysql.CHAR(36, charset="ascii", collation="ascii_bin"),
            nullable=False,
        ),
        sa.Column(
            "status",
            mysql.TINYINT(unsigned=True),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        ),
        sa.Column("last_login_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        comment="Server内部用户账号",
    )
    op.create_index("idx_auth_users_status", "auth_users", ["status"])

    op.create_table(
        "auth_wechat_identities",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column(
            "user_id",
            mysql.CHAR(36, charset="ascii", collation="ascii_bin"),
            nullable=False,
        ),
        sa.Column(
            "appid",
            mysql.VARCHAR(32, charset="ascii", collation="ascii_bin"),
            nullable=False,
        ),
        sa.Column(
            "openid",
            mysql.VARCHAR(128, charset="ascii", collation="ascii_bin"),
            nullable=False,
        ),
        sa.Column(
            "unionid",
            mysql.VARCHAR(128, charset="ascii", collation="ascii_bin"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=6),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
        ),
        sa.Column("last_login_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_users.id"],
            name="fk_wechat_identity_user",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uk_wechat_user_id"),
        mysql_charset="utf8mb4",
        comment="微信身份与Server用户映射",
    )
    op.create_index(
        "uk_wechat_appid_openid",
        "auth_wechat_identities",
        ["appid", "openid"],
        unique=True,
    )
    op.create_index(
        "idx_wechat_unionid",
        "auth_wechat_identities",
        ["unionid"],
    )

    op.execute(
        "ALTER TABLE auth_users MODIFY updated_at DATETIME(6) NOT NULL "
        "DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"
    )
    op.execute(
        "ALTER TABLE auth_wechat_identities MODIFY updated_at DATETIME(6) NOT NULL "
        "DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"
    )


def downgrade() -> None:
    op.drop_table("auth_wechat_identities")
    op.drop_table("auth_users")
