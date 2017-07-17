from typing import Callable, TypeVar, Tuple

import fastenum
import attr


class ListDiff(fastenum.Enum):
	INSERT = 0
	REPLACE = 1
	DELETE = 2


class DictDiff(fastenum.Enum):
	SET = 0
	DELETE = 1

@attr.s
class SquashResults:
	operation = attr.ib(validator = attr.validators.in_(ListDiff))
	start = attr.ib()
	stop = attr.ib()
	payload = attr.ib(default = attr.Factory(list))


DiffType = TypeVar('DiffType', ListDiff, DictDiff)
IndexType = TypeVar('IndexType')
DataType = TypeVar('DataType')
ContainerType = TypeVar('ContainerType')
Diff = Tuple[DiffType, IndexType, DataType]
ListenerType = Callable[[DiffType, IndexType, DataType], None]

# Indices of values in DiffType tuple
TYPE = 0
INDEX = 1
DATA = 2
