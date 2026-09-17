"""Recognize the existing V1 patient schema revision.

Revision ID: 20260915_01
Revises: 20260826_01

Some local databases already have this revision and the V1 tables. The next
revision checks for the patient table and creates it only on fresh installs.
"""

from typing import Sequence, Union

revision: str = "20260915_01"
down_revision: Union[str, None] = "20260826_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
