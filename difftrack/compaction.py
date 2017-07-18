from typing import List, Iterator # noqa

import sortedcontainers.sorteddict

from . import types
from .types import TYPE, INDEX, DATA

_tombstone = object()



def compact_dict_diffs(diffs: List[types.Diff]) -> List[types.Diff]:
	'''
	[SET(x)_0, SET(x)_1, ... SET(x)_n] -> [SET(x)_n]
	[SET(x)_0, ... SET(x)_n, DELETE(x)] -> [DELETE(x)]

	TODO: this produces duplicate DELETEs when called repeatedly. We might want to suppress KeyErrors in DictListener.
	'''
	compacted = {}
	for dtype, key, data in diffs:
		if dtype is types.DictDiff.SET:
			compacted[key] = data
		elif dtype is types.DictDiff.DELETE:
			compacted[key] = _tombstone
	return [
		(types.DictDiff.DELETE, key, None) if value is _tombstone else (types.DictDiff.SET, key, value)
		for (key, value) in compacted.items()
	]


def compact_list_diffs(diffs: List[types.Diff]) -> List[types.Diff]:
	'''
	Compacts list of diffs using map of (operation index) -> (index in compacted array)
	using these rules:

		[INSERT, REPLACE] -> [INSERT]
		[REPLACE, REPLACE] -> [REPLACE]
		[INSERT, DELETE] -> []
		[REPLACE, DELETE] -> [DELETE]

	Note that the tracked list is not supposed to be empty at the beginning of the diff list.
	'''
	# Resulting list of operations
	compacted = [] # type: List[types.Diff]
	# Mapping from original operation index -> compacted list index. Updated on each operation, so that the index of
	# operation result -> index of operation in compacted list. First argument is load factor.
	op_index_to_compacted_index = sortedcontainers.SortedDict(10) # type: sortedcontainers.sorteddict[int, int]

	for op in diffs:
		if op[TYPE] is types.ListDiff.INSERT:
			_append_op(op, compacted, op_index_to_compacted_index)
		elif op[TYPE] is types.ListDiff.REPLACE:
			_perform_replace(op, compacted, op_index_to_compacted_index)
		elif op[TYPE] is types.ListDiff.DELETE:
			_perform_delete(op, compacted, op_index_to_compacted_index)
	return compacted


def _append_op(op: types.Diff, compacted: List[types.Diff], op_index_to_compacted_index: 'SortedDict[int, int]') -> None:
	'''
	If the op can't be compacted, append it at the end of compacted op list and update the
	`op_index_to_compacted_index` map.
	'''
	# If the update is DELETE, it will shift the operations after it's index by minus one.
	dtype, op_index, _ = op
	if dtype is types.ListDiff.DELETE:
		for key in op_index_to_compacted_index.keys()[:]:
			if key <= op_index:
				continue
			op_index_to_compacted_index[key - 1] = op_index_to_compacted_index[key]
			del op_index_to_compacted_index[key]
	# If the update is INSERT, it will shift the operations at and after it's index by one.
	elif dtype is types.ListDiff.INSERT:
		for key in reversed(op_index_to_compacted_index.keys()[:]):
			if key < op_index:
				break
			op_index_to_compacted_index[key + 1] = op_index_to_compacted_index[key]
			del op_index_to_compacted_index[key]

	op_index_to_compacted_index[op_index] = len(compacted)
	compacted.append(op)


def _perform_replace(op: types.Diff, compacted: List[types.Diff], op_index_to_compacted_index: 'SortedDict[int, int]') -> None:
	'''Compact [INSERT, ..., REPLACE] or [REPLACE, ..., REPLACE] pair if possible'''
	if op[INDEX] not in op_index_to_compacted_index:
		_append_op(op, compacted, op_index_to_compacted_index)
		return

	position_in_compacted = op_index_to_compacted_index[op[INDEX]]
	replaced_op = compacted[position_in_compacted]
	if replaced_op[TYPE] is types.ListDiff.DELETE:
		_append_op(op, compacted, op_index_to_compacted_index)
		return

	compacted[position_in_compacted] = replaced_op[TYPE], replaced_op[INDEX], op[DATA]


def _perform_delete(op: types.Diff, compacted: List[types.Diff], op_index_to_compacted_index: 'SortedDict[int, int]') -> None:
	'''Compact [INSERT, ..., DELETE] or [REPLACE, ..., DELETE] pair if possible'''
	if op[INDEX] not in op_index_to_compacted_index:
		# [..., DELETE]. Unpaired DELETE: nothing to compact
		_append_op(op, compacted, op_index_to_compacted_index)
		return

	position_in_compacted = op_index_to_compacted_index[op[INDEX]]
	deleted_op_type, deleted_op_index, _ = compacted[position_in_compacted]

	if deleted_op_type is types.ListDiff.DELETE:
		# [..., DELETE, ..., DELETE]. Sequence of unpaired DELETEs: nothing to compact
		_append_op(op, compacted, op_index_to_compacted_index)
		return

	elif deleted_op_type is types.ListDiff.REPLACE:
		# [REPLACE, ... DELETE] pair: delete the REPLACE and append the DELETE
		_remove_from_compacted(position_in_compacted, compacted, op_index_to_compacted_index)
		del op_index_to_compacted_index[op[INDEX]]
		_append_op(op, compacted, op_index_to_compacted_index)
		return

	else:
		# [INSERT, ..., DELETE] pair: delete the INSERT
		_update_compacted_on_delete(deleted_op_index, position_in_compacted, compacted)
		# delete from compacted array and helper map
		_remove_from_compacted(position_in_compacted, compacted, op_index_to_compacted_index)
		del op_index_to_compacted_index[op[INDEX]]

		# Update the other operations in helper map
		for map_op_index in op_index_to_compacted_index.keys()[:]:
			if map_op_index > op[INDEX]:
				# assert map_op_index - 1 not in op_index_to_compacted_index
				op_index_to_compacted_index[map_op_index - 1] = op_index_to_compacted_index[map_op_index]
				del op_index_to_compacted_index[map_op_index]


def _remove_from_compacted(index: int, compacted: List[types.Diff], op_index_to_compacted_index: 'SortedDict[int, int]') -> None:
	'''Remove given Diff from `compacted` list and update the helper map'''
	del compacted[index]

	for map_op_index in op_index_to_compacted_index:
		if op_index_to_compacted_index[map_op_index] >= index:
			op_index_to_compacted_index[map_op_index] -= 1


def _update_compacted_on_delete(deleted_op_index: int, position_in_compacted: int, compacted: List[types.Diff]) -> None:
	'''
	Index of previous compacted operations should be decreased if:
	- operation was added later than the deleted operation and
	- index accessed by the operation is >/>= than the deleted operation index at the time of
	  applying compacted_op
	'''
	for op_index, compacted_op in enumerate(compacted):
		if op_index <= position_in_compacted:
			continue

		if compacted_op[TYPE] is types.ListDiff.INSERT and compacted_op[INDEX] <= deleted_op_index:
			deleted_op_index += 1
		elif compacted_op[TYPE] is types.ListDiff.DELETE and compacted_op[INDEX] < deleted_op_index:
			deleted_op_index -= 1

		if compacted_op[INDEX] >= deleted_op_index:
			compacted[op_index] = (compacted_op[TYPE], compacted_op[INDEX] - 1, compacted_op[DATA])


def _squash_single_list_diffs_sequence(diffs: List[types.Diff]) -> types.SquashResults:
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
	payload = [] # type: List[types.DataType]
	if dtype is types.ListDiff.INSERT:
		for _, _, _p in diffs:
			payload.append(_p)
		stop = start + len(payload) - 1
	elif dtype is types.ListDiff.REPLACE:
		for _, _, _p in diffs:
			payload.append(_p)
		stop = start + len(payload)
	else:
		# DELETE
		stop = start + len(diffs)
	return types.SquashResults(dtype, start, stop, payload)


def squash_list_diffs(diffs: List[types.Diff]) -> Iterator[types.SquashResults]:
	'''
	Squashes consecutive insert / replace / delete operations
	'''
	if not diffs:
		return []

	current_batch = [diffs[0]] # type: List[types.Diff]
	for data in diffs[1:]:
		dtype, index, payload = data
		prev_dtype, prev_index, prev_payload = current_batch[-1]

		append_to_storage = False
		if dtype == prev_dtype:
			if dtype is types.ListDiff.INSERT:
				append_to_storage = prev_index + 1 == index
			elif dtype is types.ListDiff.DELETE:
				append_to_storage = prev_index == index
			else:
				# REPLACE
				append_to_storage = prev_index + 1 == index

		if append_to_storage:
			current_batch.append(data)
		else:
			yield _squash_single_list_diffs_sequence(current_batch)
			current_batch = [data]

	if len(current_batch) > 0:
		yield _squash_single_list_diffs_sequence(current_batch)
