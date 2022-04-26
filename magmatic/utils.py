from __future__ import annotations

from os import getenv
from typing import Literal, TYPE_CHECKING

__all__ = (
    'IS_DOCUMENTING',
)


if TYPE_CHECKING:
    IS_DOCUMENTING: Literal[False] = False
else:
    IS_DOCUMENTING: bool = getenv('READTHEDOCS', False)
