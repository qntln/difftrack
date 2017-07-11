from typing import Callable, List, Iterator
import contextlib
import functools

from . import types, listeners




def data_mapper(mapper: Callable[[types.DataType], types.DataType]) -> Callable[[types.ListenerType], types.ListenerType]:
	'''
	Apply a mapper to the listener's `data` argument.
	'''

	def decorator(listener: types.ListenerType) -> types.ListenerType:

		@functools.wraps(listener)
		def wrapped(dtype: types.DiffType, index: int, data: types.DataType) -> None:
			listener(dtype, index, mapper(data))

		with contextlib.suppress(AttributeError):
			wrapped.finalize_batch = listener.finalize_batch

		return wrapped
	return decorator



_tombstone = object()

def compact_dict_diffs(diffs: List[types.Diff]) -> List[types.Diff]:
	'''
	[SET(x)_0, SET(x)_1, ... SET(x)_n] -> [SET(x)_n]
	[SET(x)_0, ... SET(x)_n, DELETE(x)] -> [DELETE(x)]

	TODO: this produces duplicate DELETEs when called repeatedly. We might want to suppress KeyErrors in DictListener.
	'''
	compacted = {}
	for (dtype, key, data) in diffs:
		if dtype is types.DictDiff.SET:
			compacted[key] = data
		elif dtype is types.DictDiff.DELETE:
			compacted[key] = _tombstone
	return [
		(types.DictDiff.DELETE, key, None) if value is _tombstone else (types.DictDiff.SET, key, value)
		for (key, value) in compacted.items()
	]



class BoundedListDiffHandler:
	'''
	This creates a proxy over ``ListListener.__call__`` ensuring that the listener never grows past a certain maximum size.

	It keeps a copy of the entire list, but only passes diffs to the underlying ListListener so that its length
	remains bounded.
	'''

	def __init__(self, listener: listeners.ListListener, max_size: int) -> None:
		self._listener = listener
		self._max_size = max_size
		self._full_list = [] # type: List[types.DataType]
		# We have to keep a running sum of INSERT-DELETE ops passed to the listener since the listener
		# doesn't apply them immediately.
		self._listener_len = 0
		try:
			self._listener_finalize_batch_function = self._listener.finalize_batch
		except AttributeError:
			self._listener_finalize_batch_function = None


	def __call__(self, dtype: types.DiffType, index: types.IndexType, data: types.DataType) -> None:
		# Always keep a private copy of the entire list.
		if dtype is types.ListDiff.INSERT:
			self._full_list.insert(index, data)
		elif dtype is types.ListDiff.REPLACE:
			self._full_list[index] = data
		elif dtype is types.ListDiff.DELETE:
			del self._full_list[index]
		# Pass the original operation if it happened within the bound...
		if index < self._max_size:
			self._listener(dtype, index, data)
			# ...but also possibly add a trimming or an expanding operation to adhere to max_size.
			if dtype is types.ListDiff.INSERT:
				self._listener_len += 1
				if self._listener_len > self._max_size:
					# This insertion has grown the bounded list over the limit. Trim.
					self._listener(types.ListDiff.DELETE, self._max_size, None)
					self._listener_len -= 1
			elif dtype is types.ListDiff.DELETE:
				self._listener_len -= 1
				if self._listener_len < self._max_size <= len(self._full_list):
					# This deletion made the bounded list too short, AND we have enough data to grow it back to max_size.
					self._listener(types.ListDiff.INSERT, self._max_size - 1, self._full_list[self._max_size - 1])
					self._listener_len += 1


	def finalize_batch(self):
		if self._listener_finalize_batch_function is not None:
			self._listener_finalize_batch_function()



def merge_difftrack_results(diffs: List[types.Diff]) -> types.SquashResults:
	'''
	Squashables:
		Inserts by indexes (appending):
				1, 2, 3, 4, 5, ..
		Replaces by indexes and payload lengths (merging replaces by consecutive blocks):
				4 (+2), 6 (+3), 9 (+1), ..
		Deletes by indexes (removing single elements /w reindexing):
				1, 1, 1, 1, ..
	'''
	dtype = diffs[0][0]
	start = diffs[0][1]
	payload = [] # List[types.DataType]
	if dtype is types.ListDiff.INSERT:
		for _, _, _p in diffs:
			payload.append(_p)
		stop = start + len(payload) - 1
	elif dtype is types.ListDiff.REPLACE:
		for _, _, _p in diffs:
			payload.append(_p)
		stop = start + len(payload)
	else: # DELETE
		stop = start + len(diffs)
	return types.SquashResults(dtype, start, stop, payload)


def squash_difftrack_results(diffs: List[types.Diff]) -> Iterator[types.SquashResults]:
	'''
	Squashes consecutive insert / replace / delete operations
	'''
	current_batch = [ diffs[0] ] # List[types.Diff]
	for data in diffs[1:]:
		dtype, index, payload = data
		prev_dtype, prev_index, prev_payload = current_batch[-1]

		append_to_storage = False
		if dtype == prev_dtype:
			if dtype is types.ListDiff.INSERT:
				append_to_storage = prev_index + 1 == index
			elif dtype is types.ListDiff.DELETE:
				append_to_storage = prev_index == index
			else: # REPLACE
				append_to_storage = prev_index + 1 == index

		if append_to_storage:
			current_batch.append(data)
		else:
			yield merge_difftrack_results(current_batch)
			current_batch = [ data ]

	if len(current_batch) > 0:
		yield merge_difftrack_results(current_batch)
