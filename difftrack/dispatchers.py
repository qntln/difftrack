from typing import Any, Generic, Callable, List # noqa

import collections
import contextlib

from . import types



class Dispatcher(Generic[types.DiffType, types.IndexType]):

	def __init__(self) -> None:
		self._listeners = [] # type: List[types.ListenerType]
		self._batch_finalizers = [] # type: List[Callable[[], None]]
		self._active = False
		self._apply_diff_recursion = 0
		self._diffs_to_apply = collections.deque()
		self._should_finalize = False


	def add_listener(self, listener: types.ListenerType) -> None:
		assert not self._active, 'Cannot add listener after diffs have been applied'
		self._listeners.append(listener)
		with contextlib.suppress(AttributeError):
			self._batch_finalizers.append(listener.finalize_batch)


	def apply_diff(self, dtype: types.DiffType, index: types.IndexType, data: types.DataType) -> None:
		'''
		If this function is recursed into (a diff application triggers a new diff) it will just note the
		new diff to be applied and let the very first invocation on the stack apply it. This way each diff
		is distributed to all listeners before a new diff may be applied.
		'''
		assert self._apply_diff_recursion < 10, 'Too many recursive calls to `apply_diff`'
		self._diffs_to_apply.append((dtype, index, data))
		self._apply_diff_recursion += 1
		if self._apply_diff_recursion > 1:
			return

		self._active = True
		self._should_finalize = True
		while self._diffs_to_apply:
			diff_dtype, diff_index, diff_data = self._diffs_to_apply.popleft()
			for listener in self._listeners:
				listener(diff_dtype, diff_index, diff_data)
		self._apply_diff_recursion = 0


	def finalize_batch(self):
		'''
		Call all `finalize_batch` methods if there is need to finalize
		'''
		if self._should_finalize:
			for finalize_batch in self._batch_finalizers:
				finalize_batch()
			self._should_finalize = False


	def __enter__(self):
		pass


	def __exit__(self, exc_type, exc_val, exc_tb):
		self.finalize_batch()



class ListDispatcher(Dispatcher[types.ListDiff, int]):

	def insert(self, index, value):
		self.apply_diff(types.ListDiff.INSERT, index, value)

	def __setitem__(self, index, value):
		self.apply_diff(types.ListDiff.REPLACE, index, value)

	def __delitem__(self, index):
		self.apply_diff(types.ListDiff.DELETE, index, None)



class DictDispatcher(Dispatcher[types.DictDiff, Any]):

	def __setitem__(self, key, value):
		self.apply_diff(types.DictDiff.SET, key, value)

	def __delitem__(self, key):
		self.apply_diff(types.DictDiff.DELETE, key, None)
