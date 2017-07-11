from typing import Any, List, Generic, Dict, Callable, Optional

import abc

from . import types



OnChangeCallbackType = Callable[[types.DiffType, types.IndexType, types.DataType], None]
OnFinalizeBatchCallbackType = Callable[[], None]


class Listener(abc.ABC, Generic[types.ContainerType, types.IndexType]):

	_DATA_FACTORY = None # type: Callable[[], types.ContainerType]

	def __init__(self, on_change: Optional[OnChangeCallbackType] = None,
	on_finalize_batch: Optional[OnFinalizeBatchCallbackType] = None) -> None:

		'''
		:param on_change: Optional callback executed after every diff application.
		'''
		self._data = self._DATA_FACTORY()
		self._new_diffs = [] # type: List[types.Diff]
		self.on_change = on_change
		self.on_finalize_batch = on_finalize_batch


	def __call__(self, dtype: types.DiffType, index: types.IndexType, data: types.DataType) -> None:
		self._new_diffs.append((dtype, index, data))
		if self.on_change is not None:
			self.on_change(dtype, index, data)


	@abc.abstractmethod
	def _apply_diff(self, dtype: types.DiffType, index: types.IndexType, data: types.DataType) -> None:
		pass


	def get_snapshot(self) -> types.ContainerType:
		return self._data


	def get_new_diffs(self) -> List[types.Diff]:
		'''
		Return any outstanding diffs *and apply them* to the current snapshot. This guarantees that the following
		two sequences of operations produce an equivalent ``result``:

			1) snapshot = listener.get_snapshot()
			   diffs = listener.get_new_diffs()
			   result = snapshot "+" diffs

			2) listener.get_new_diffs() # diffs get applied but the caller doesn't use them
			   result = listener.get_snapshot()

		Once the diffs are applied and returned from this function they are forgotten.
		'''
		diffs = self._new_diffs
		self._new_diffs = []
		for diff in diffs:
			self._apply_diff(*diff)
		return diffs


	@property
	def has_changed(self) -> bool:
		return bool(self._new_diffs)


	def finalize_batch(self):
		if self.on_finalize_batch is not None:
			self.on_finalize_batch()



class ListListener(Listener[List[Any], int]):

	_DATA_FACTORY = list

	def _apply_diff(self, dtype: types.ListDiff, index: int, data: types.DataType) -> None:
		if dtype is types.ListDiff.INSERT:
			self._data.insert(index, data)
		elif dtype is types.ListDiff.REPLACE:
			self._data[index] = data
		elif dtype is types.ListDiff.DELETE:
			del self._data[index]



class DictListener(Listener[Dict[Any, Any], Any]):

	_DATA_FACTORY = dict

	def _apply_diff(self, dtype: types.DictDiff, index: Any, data: types.DataType) -> None:
		if dtype is types.DictDiff.SET:
			self._data[index] = data
		elif dtype is types.DictDiff.DELETE:
			# TODO should we suppress KeyError? utils.compact_dict_diffs may generate invalid DELETEs.
			del self._data[index]
