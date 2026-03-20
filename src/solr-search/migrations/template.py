"""Example migration template.

Copy this file as ``mNNNN_<description>.py`` where NNNN is the next
schema version number.  Implement the ``upgrade`` function with your
DDL/DML statements.  The function receives an open ``sqlite3.Connection``
inside a transaction — do NOT call ``connection.commit()``.
"""

from __future__ import annotations

# VERSION must be an integer greater than all previous migration versions.
# VERSION = 2
# DESCRIPTION = "Add email column to users table"
#
#
# def upgrade(connection):
#     connection.execute(
#         "ALTER TABLE users ADD COLUMN email TEXT DEFAULT NULL"
#     )
