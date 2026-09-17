"""Reserved revision from the local login migration attempt.

Revision ID: 20260917_02
Revises: 20260915_01
"""

from typing import Sequence, Union

revision: str = "20260917_02"
down_revision: Union[str, None] = "20260915_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
