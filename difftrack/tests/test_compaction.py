import random
import pprint

import difftrack



def test_compact_dict_diffs():
	diffs = [
		(difftrack.DictDiff.SET, 'x', 123),
		(difftrack.DictDiff.SET, 'y', 456),
		(difftrack.DictDiff.SET, 'y', 9999),
		(difftrack.DictDiff.DELETE, 'x', None),
	]
	assert set(difftrack.compact_dict_diffs(diffs)) == {
		(difftrack.DictDiff.SET, 'y', 9999),
		(difftrack.DictDiff.DELETE, 'x', None),
	}


def test_compact_dict_diffs_single_delete():
	diffs = [
		(difftrack.DictDiff.DELETE, 'x', None),
	]
	assert set(difftrack.compact_dict_diffs(diffs)) == {
		(difftrack.DictDiff.DELETE, 'x', None),
	}


def test_compact_list_diffs_simple_insert():
	diffs = [
		(difftrack.ListDiff.INSERT, 0, 'a'),
	]

	assert difftrack.compact_list_diffs(diffs) == [
		(difftrack.ListDiff.INSERT, 0, 'a')
	]


def test_compact_list_diffs_insert_same_index():
	diffs = [
		(difftrack.ListDiff.INSERT, 0, 'a'),
		(difftrack.ListDiff.INSERT, 0, 'b'),
	]

	assert difftrack.compact_list_diffs(diffs) == [
		(difftrack.ListDiff.INSERT, 0, 'a'),
		(difftrack.ListDiff.INSERT, 0, 'b'),
	]


def test_compact_list_diffs_insert_same_index_with_insert_before():
	diffs = [
		(difftrack.ListDiff.INSERT, 2, 'a'),
		(difftrack.ListDiff.INSERT, 3, 'b'),
		(difftrack.ListDiff.INSERT, 3, 'c'),
	]

	assert difftrack.compact_list_diffs(diffs) == [
		(difftrack.ListDiff.INSERT, 2, 'a'),
		(difftrack.ListDiff.INSERT, 3, 'b'),
		(difftrack.ListDiff.INSERT, 3, 'c'),
	]


def test_compact_list_diffs_simple_delete():
	diffs = [
		(difftrack.ListDiff.DELETE, 0, None),
	]

	assert difftrack.compact_list_diffs(diffs) == [
		(difftrack.ListDiff.DELETE, 0, None),
	]


def test_compact_list_diffs_delete_after_one_insert():
	diffs = [
		(difftrack.ListDiff.INSERT, 0, 'a'),
		(difftrack.ListDiff.DELETE, 0, None),
	]

	assert difftrack.compact_list_diffs(diffs) == []


def test_compact_list_diffs_delete_after_multiple_inserts():
	diffs = [
		(difftrack.ListDiff.INSERT, 0, 'a'),
		(difftrack.ListDiff.INSERT, 0, 'b'),
		(difftrack.ListDiff.INSERT, 0, 'c'),
		(difftrack.ListDiff.DELETE, 1, None),
	]

	assert difftrack.compact_list_diffs(diffs) == [
		(difftrack.ListDiff.INSERT, 0, 'a'),
		(difftrack.ListDiff.INSERT, 0, 'c'),
	]


def test_compact_list_diffs_simple_replace():
	diffs = [
		(difftrack.ListDiff.REPLACE, 3, 'a'),
	]

	assert difftrack.compact_list_diffs(diffs) == [
		(difftrack.ListDiff.REPLACE, 3, 'a'),
	]


def test_compact_list_diffs_replace_after_inserts():
	diffs = [
		(difftrack.ListDiff.INSERT, 0, 'a'),
		(difftrack.ListDiff.INSERT, 0, 'b'),
		(difftrack.ListDiff.INSERT, 0, 'c'),
		(difftrack.ListDiff.REPLACE, 1, 'd'),
	]

	assert difftrack.compact_list_diffs(diffs) == [
		(difftrack.ListDiff.INSERT, 0, 'a'),
		(difftrack.ListDiff.INSERT, 0, 'd'),
		(difftrack.ListDiff.INSERT, 0, 'c'),
	]


def test_compact_list_diffs_replace_after_inserts_missed_index():
	diffs = [
		(difftrack.ListDiff.INSERT, 0, 'a'),
		(difftrack.ListDiff.INSERT, 0, 'b'),
		(difftrack.ListDiff.REPLACE, 4, 'd'),
	]

	assert difftrack.compact_list_diffs(diffs) == [
		(difftrack.ListDiff.INSERT, 0, 'a'),
		(difftrack.ListDiff.INSERT, 0, 'b'),
		(difftrack.ListDiff.REPLACE, 4, 'd'),
	]


def test_compact_list_diffs_replace_after_delete():
	diffs = [
		(difftrack.ListDiff.DELETE, 0, None),
		(difftrack.ListDiff.REPLACE, 0, 'd'),
	]

	assert difftrack.compact_list_diffs(diffs) == [
		(difftrack.ListDiff.DELETE, 0, None),
		(difftrack.ListDiff.REPLACE, 0, 'd'),
	]


def test_compact_list_diffs_consecutive_deletes():
	diffs = [
		(difftrack.ListDiff.DELETE, 0, None),
		(difftrack.ListDiff.DELETE, 0, None),
	]

	assert difftrack.compact_list_diffs(diffs) == [
		(difftrack.ListDiff.DELETE, 0, None),
		(difftrack.ListDiff.DELETE, 0, None),
	]


def test_compact_list_diffs_whiteboard_case_1():
	diffs = [
		(difftrack.ListDiff.REPLACE, 3, 'x'),
		(difftrack.ListDiff.INSERT, 2, 'y'),
		(difftrack.ListDiff.INSERT, 2, 'yy'),
		(difftrack.ListDiff.REPLACE, 5, 'z'),
	]

	assert difftrack.compact_list_diffs(diffs) == [
		(difftrack.ListDiff.REPLACE, 3, 'z'),
		(difftrack.ListDiff.INSERT, 2, 'y'),
		(difftrack.ListDiff.INSERT, 2, 'yy'),
	]


def test_compact_list_diffs_whiteboard_case_2():
	diffs = [
		(difftrack.ListDiff.INSERT, 0, 'x'),
		(difftrack.ListDiff.INSERT, 0, 'y'),
		(difftrack.ListDiff.DELETE, 0, None),
		(difftrack.ListDiff.REPLACE, 0, 'z'),
	]

	assert difftrack.compact_list_diffs(diffs) == [
		(difftrack.ListDiff.INSERT, 0, 'z'),
	]


def test_compact_list_diffs_only_delete():
	diffs = [
		(difftrack.ListDiff.DELETE, 1, 1)
	]
	compacted_diffs = difftrack.compact_list_diffs(diffs)
	assert compacted_diffs == diffs


def test_compact_list_diffs_replace_delete():
	diffs = [
		(difftrack.ListDiff.REPLACE, 1, 1),
		(difftrack.ListDiff.DELETE, 1, 2)
	]
	compacted_diffs = difftrack.compact_list_diffs(diffs)
	assert compacted_diffs == [
		(difftrack.ListDiff.DELETE, 1, 2)
	]


def test_compact_list_diffs_replace_replace():
	diffs = [
		(difftrack.ListDiff.REPLACE, 1, 1),
		(difftrack.ListDiff.REPLACE, 1, 2),
		(difftrack.ListDiff.REPLACE, 1, 3),
	]
	compacted_diffs = difftrack.compact_list_diffs(diffs)
	assert compacted_diffs == [
		(difftrack.ListDiff.REPLACE, 1, 3)
	]


def _get_dispatcher_listener_pair():
	dispatcher = difftrack.ListDispatcher()
	listener = difftrack.ListListener()
	dispatcher.add_listener(listener)

	return dispatcher, listener


def generate_random_diffs():
	dispatcher, listener = _get_dispatcher_listener_pair()

	diffs = []
	for i in range(random.randint(1, 16)):
		llen = len(listener.get_snapshot())
		if llen:
			possible_ops = [difftrack.ListDiff.INSERT, difftrack.ListDiff.REPLACE, difftrack.ListDiff.DELETE]
			index = random.randint(0, llen - 1)
		else:
			possible_ops = [difftrack.ListDiff.INSERT]
			index = 0

		op = random.choice(possible_ops)
		dispatcher.apply_diff(op, index, i)
		diffs += listener.get_new_diffs() # Apply diffs so that listener.get_snapshot reports current length.
	return diffs


def pytest_generate_tests(metafunc):
	if 'random_diffs' in metafunc.fixturenames:
		metafunc.parametrize('random_diffs', [generate_random_diffs() for _ in range(20000)])


def test_fuzzy(random_diffs):
	dispatcher, listener = _get_dispatcher_listener_pair()
	dispatcher_optimized, listener_optimized = _get_dispatcher_listener_pair()

	diffs_compacted = difftrack.compact_list_diffs(random_diffs)

	for diff in random_diffs:
		dispatcher.apply_diff(*diff)

	for diff in diffs_compacted:
		dispatcher_optimized.apply_diff(*diff)

	listener.get_new_diffs()
	listener_optimized.get_new_diffs()
	assert listener.get_snapshot() == listener_optimized.get_snapshot(), \
		'Compaction failed on diffs: \n' + pprint.pformat(random_diffs)


def test_split_into_halves_and_compact(random_diffs):
	dispatcher, listener = _get_dispatcher_listener_pair()
	dispatcher_optimized, listener_optimized = _get_dispatcher_listener_pair()

	if len(random_diffs) == 1:
		fst = []
		snd = random_diffs
	else:
		half = int(len(random_diffs) / 2)
		fst = random_diffs[:half]
		snd = random_diffs[half:]

	for diff in fst:
		dispatcher.apply_diff(*diff)
		dispatcher_optimized.apply_diff(*diff)
	listener.get_new_diffs()
	listener_optimized.get_new_diffs()

	for diff in snd:
		dispatcher.apply_diff(*diff)
		listener.get_new_diffs()

	snd_compacted = difftrack.compact_list_diffs(snd)
	snapshots_optimized = []
	for diff in snd_compacted:
		dispatcher_optimized.apply_diff(*diff)
		listener_optimized.get_new_diffs()
		snapshots_optimized.append(listener_optimized.get_snapshot()[:])

	assert listener.get_snapshot() == listener_optimized.get_snapshot(), \
		'Compaction failed on diffs: \n' + pprint.pformat(random_diffs)


def test_insert_reorder():
	dispatcher, listener = _get_dispatcher_listener_pair()
	diffs = [
		(difftrack.ListDiff.INSERT, 0, 5),
		(difftrack.ListDiff.INSERT, 0, 3),
		(difftrack.ListDiff.INSERT, 1, 4),
		(difftrack.ListDiff.DELETE, 0, None),
	]
	for diff in difftrack.compact_list_diffs(diffs):
		dispatcher.apply_diff(*diff)
	listener.get_new_diffs()
	assert listener.get_snapshot() == [4, 5]


def test_insert_reorder_2():
	dispatcher, listener = _get_dispatcher_listener_pair()
	diffs = [
		(difftrack.ListDiff.INSERT, 0, 2),  # [2]
		(difftrack.ListDiff.INSERT, 0, 3),  # [3, 2]
		(difftrack.ListDiff.INSERT, 1, 4),  # [3, 4, 2]
		(difftrack.ListDiff.INSERT, 0, 7),  # [7, 3, 4, 2]
		(difftrack.ListDiff.INSERT, 0, 8),  # [8, 7, 3, 4, 2]
		# This deletes the above IN,0,3 and therefore changed the order of IN,0,2 and IN,1,4
		(difftrack.ListDiff.DELETE, 2, 10)  # [8, 7, 4, 2]
	]
	for diff in difftrack.compact_list_diffs(diffs):
		dispatcher.apply_diff(*diff)
	listener.get_new_diffs()
	assert listener.get_snapshot() == [8, 7, 4, 2]
