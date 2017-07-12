from unittest import mock

import pytest

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


class TestBoundedListDiffHandler:

	@pytest.fixture
	def listener(self):
		return difftrack.ListListener()


	@pytest.fixture
	def dispatcher(self, listener):
		disp = difftrack.ListDispatcher()
		disp.add_listener(difftrack.BoundedListDiffHandler(listener, 2))
		return disp


	def test_do_not_grow_beyond_maxsize(self, dispatcher, listener):
		dispatcher.insert(0, 'a')
		dispatcher.insert(1, 'b')
		dispatcher.insert(2, 'c')
		dispatcher.insert(3, 'd')
		assert listener.get_new_diffs() == [
			(difftrack.ListDiff.INSERT, 0, 'a'),
			(difftrack.ListDiff.INSERT, 1, 'b'),
		]
		assert listener.get_snapshot() == ['a', 'b']
		dispatcher[1] = 'BB'
		assert listener.get_new_diffs() == [
			(difftrack.ListDiff.REPLACE, 1, 'BB'),
		]
		assert listener.get_snapshot() == ['a', 'BB']


	def test_push_data_outside_maxsize(self, dispatcher, listener):
		dispatcher.insert(0, 'a')
		dispatcher.insert(1, 'b')
		assert listener.get_new_diffs() == [
			(difftrack.ListDiff.INSERT, 0, 'a'),
			(difftrack.ListDiff.INSERT, 1, 'b'),
		]
		assert listener.get_snapshot() == ['a', 'b']

		dispatcher.insert(0, 'c')
		assert listener.get_new_diffs() == [
			(difftrack.ListDiff.INSERT, 0, 'c'),
			(difftrack.ListDiff.DELETE, 2, None),
		]
		assert listener.get_snapshot() == ['c', 'a']

		dispatcher.insert(0, 'd')
		assert listener.get_new_diffs() == [
			(difftrack.ListDiff.INSERT, 0, 'd'),
			(difftrack.ListDiff.DELETE, 2, None),
		]
		assert listener.get_snapshot() == ['d', 'c']


	def test_recover_data_previously_outside_maxsize(self, dispatcher, listener):
		dispatcher.insert(0, 'a')
		dispatcher.insert(1, 'b')
		dispatcher.insert(0, 'c')
		dispatcher.insert(0, 'd')
		listener.get_new_diffs() # flush the initial diffs as we don't care about them
		assert listener.get_snapshot() == ['d', 'c']

		del dispatcher[0]
		assert listener.get_new_diffs() == [
			(difftrack.ListDiff.DELETE, 0, None),
			(difftrack.ListDiff.INSERT, 1, 'a'),
		]
		assert listener.get_snapshot() == ['c', 'a']

		del dispatcher[1]
		assert listener.get_new_diffs() == [
			(difftrack.ListDiff.DELETE, 1, None),
			(difftrack.ListDiff.INSERT, 1, 'b'),
		]
		assert listener.get_snapshot() == ['c', 'b']


	def test_not_enough_data_to_recover(self, dispatcher, listener):
		dispatcher.insert(0, 'a')
		dispatcher.insert(1, 'b')
		dispatcher.insert(0, 'c')
		dispatcher.insert(0, 'd')
		listener.get_new_diffs() # flush the initial diffs as we don't care about them
		assert listener.get_snapshot() == ['d', 'c']

		del dispatcher[3]
		del dispatcher[2]
		assert listener.get_new_diffs() == [], 'No effect expected'
		assert listener.get_snapshot() == ['d', 'c'], 'No effect expected'

		# Now there will be no data to put back in the bounded list
		del dispatcher[1]
		assert listener.get_new_diffs() == [
			(difftrack.ListDiff.DELETE, 1, None),
		]
		assert listener.get_snapshot() == ['d']

		del dispatcher[0]
		assert listener.get_new_diffs() == [
			(difftrack.ListDiff.DELETE, 0, None),
		]
		assert listener.get_snapshot() == []


	def test_no_flapping(self, dispatcher, listener):
		dispatcher.insert(0, 'a')
		dispatcher.insert(1, 'b')
		listener.get_new_diffs() # flush the initial diffs as we don't care about them
		assert listener.get_snapshot() == ['a', 'b']
		dispatcher.insert(2, 'c')
		assert listener.get_new_diffs() == [], 'Do not generate redundant INSERT(x)+DELETE(x) operations'
		assert listener.get_snapshot() == ['a', 'b']



def test_finalize_batch_nested_listeners():
	'''
	Test that utils pass `finalize_batch` signal on
	'''
	def mapper(data):
		if data is None:
			return None
		return data.lower()

	cb = mock.Mock()
	# dispatcher -> BoundedListDiffHandler -> mapper -> listener
	listener = difftrack.ListListener(on_finalize_batch = cb)
	mapped_listener = difftrack.data_mapper(mapper)(listener)
	bounded_listener = difftrack.BoundedListDiffHandler(mapped_listener, 2)
	dispatcher = difftrack.ListDispatcher()
	dispatcher.add_listener(bounded_listener)

	with dispatcher:
		dispatcher.insert(0, 'AAA')
		dispatcher.insert(0, 'BBB')
		dispatcher.insert(0, 'CCC')
		cb.assert_not_called()
	cb.assert_called_once_with()
	listener.get_new_diffs()
	assert listener.get_snapshot() == ['ccc', 'bbb']



def test_finalize_batch_nested_listeners_only_function():
	'''
	Test that utils pass `finalize_batch` signal on
	'''
	def mapper(data):
		if data is None:
			return None
		return data.lower()

	function_listener_counter = 0
	def function_listener(*args):
		nonlocal function_listener_counter
		function_listener_counter += 1

	# dispatcher -> BoundedListDiffHandler -> mapper -> function_listener
	mapped_listener = difftrack.data_mapper(mapper)(function_listener)
	bounded_listener = difftrack.BoundedListDiffHandler(mapped_listener, 2)
	dispatcher = difftrack.ListDispatcher()
	dispatcher.add_listener(bounded_listener)

	with dispatcher:
		dispatcher.insert(0, 'AAA')
		dispatcher.insert(0, 'BBB')
		dispatcher.insert(0, 'CCC')
	# three inserts and one delete
	assert function_listener_counter == 4


def test_squash_diffs_no_squash():
	diffs = [
		(difftrack.ListDiff.INSERT, 1, {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 1, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 1, None)
	]

	out_diffs = [
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 1, [{'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 2, [{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, [])
	]

	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs


def test_squash_diffs_insert():
	diffs = [
		(difftrack.ListDiff.INSERT, 1, {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.INSERT, 2, {'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.INSERT, 3, {'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 1, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 1, None)
	]

	out_diffs = [
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 3, [
			{'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}
		]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 2, [{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, [])
	]

	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs


def test_squash_diffs_mixed_insert_with_space():
	diffs = [
		(difftrack.ListDiff.INSERT, 1, {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.INSERT, 2, {'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.INSERT, 4, {'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 1, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 1, None)
	]

	out_diffs = [
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 2, [
			{'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
		]),
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 4, 4, [
			{'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}
		]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 2, [{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, [])
	]

	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs


def test_squash_diffs_mixed_insert_with_op_between():
	diffs = [
		(difftrack.ListDiff.INSERT, 1, {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.INSERT, 2, {'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 1, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.INSERT, 4, {'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 1, None)
	]

	out_diffs = [
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 2, [
			{'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
		]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 2, [{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 4, 4, [
			{'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}
		]),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, [])
	]

	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs


def test_squash_diffs_mixed_insert_wrong_ordering():
	diffs = [
		(difftrack.ListDiff.INSERT, 1, {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.INSERT, 1, {'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.INSERT, 3, {'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 1, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 1, None)
	]

	out_diffs = [
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 1, [ {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}, ]),
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 1, [ {'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]} ]),
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 3, 3, [ {'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]} ]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 2, [{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, [])
	]

	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs


def test_squash_diffs_replace():
	diffs = [
		(difftrack.ListDiff.INSERT, 1, {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 1, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 2, {'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 3, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 4, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 5, {'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 1, None)
	]

	out_diffs = [
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 1, [{'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 6, [
			{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}
		]),

		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, [])
	]

	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs


def test_squash_diffs_mixed_replace_with_space():
	diffs = [
		(difftrack.ListDiff.INSERT, 1, {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 1, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 2, {'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),

		(difftrack.ListDiff.REPLACE, 4, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 5, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 6, {'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 1, None)
	]

	out_diffs = [
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 1, [{'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 3, [
			{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}
		]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 4, 7, [
			{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}
		]),

		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, [])
	]

	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs


def test_squash_diffs_mixed_replace_with_op_betwen():
	diffs = [
		(difftrack.ListDiff.INSERT, 1, {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 1, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 2, {'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),

		(difftrack.ListDiff.REPLACE, 4, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 1, None),
		(difftrack.ListDiff.REPLACE, 5, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 6, {'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 1, None)
	]

	out_diffs = [
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 1, [{'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 3, [
			{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}
		]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 4, 5, [
			{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
		]),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, []),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 5, 7, [
			{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}
		]),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, [])
	]

	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs


def test_squash_diffs_mixed_replace_with_wrong_order():
	diffs = [
		(difftrack.ListDiff.INSERT, 1, {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 1, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 2, {'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),

		(difftrack.ListDiff.REPLACE, 1, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 4, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 5, {'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 1, None)
	]

	out_diffs = [
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 1, [{'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 3, [
			{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 4, 'price': '35.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
		]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 2, [
			{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
		]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 4, 6, [
			{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]},
			{'order_count': 5, 'price': '50.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}
		]),

		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, [])
	]

	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs


def test_squash_diffs_delete():
	diffs = [
		(difftrack.ListDiff.INSERT, 1, {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 1, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 1, None),
		(difftrack.ListDiff.DELETE, 1, None),
		(difftrack.ListDiff.DELETE, 1, None)
	]

	out_diffs = [
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 1, [{'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 2, [{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 4, [])
	]

	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs


def test_squash_diffs_mixed_delete_with_space():
	diffs = [
		(difftrack.ListDiff.INSERT, 1, {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 1, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 1, None),
		(difftrack.ListDiff.DELETE, 2, None),
		(difftrack.ListDiff.DELETE, 1, None)
	]

	out_diffs = [
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 1, [{'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 2, [{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, []),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 2, 3, []),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, [])
	]

	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs


def test_squash_diffs_mixed_delete_with_op_between():
	diffs = [
		(difftrack.ListDiff.INSERT, 1, {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 1, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 1, None),
		(difftrack.ListDiff.INSERT, 1, {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 1, None)
	]

	out_diffs = [
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 1, [{'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 2, [{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, []),
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 1, [{'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, [])
	]

	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs


def test_squash_diffs_mixed_delete_with_wrong_order():
	diffs = [
		(difftrack.ListDiff.INSERT, 1, {'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.REPLACE, 1, {'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}),
		(difftrack.ListDiff.DELETE, 2, None),
		(difftrack.ListDiff.DELETE, 1, None),
		(difftrack.ListDiff.DELETE, 3, None)
	]

	out_diffs = [
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 1, [{'order_count': 3, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 2, [{'order_count': 1, 'price': '41.345', 'orders': [{'paired_order': None, 'quantity': 372, 'id': '80021'}]}]),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 2, 3, []),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, []),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 3, 4, [])
	]

	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs


def test_squash_diffs_general_data():
	diffs = [
		(difftrack.ListDiff.INSERT, 1, 'AAA'),
		(difftrack.ListDiff.INSERT, 2, 'BBB'),
		(difftrack.ListDiff.INSERT, 3, 'CCC'),
		(difftrack.ListDiff.REPLACE, 1, 'DDD'),
		(difftrack.ListDiff.DELETE, 1, None)
	]

	out_diffs = [
		difftrack.SquashResults(difftrack.ListDiff.INSERT, 1, 3, ['AAA', 'BBB', 'CCC']),
		difftrack.SquashResults(difftrack.ListDiff.REPLACE, 1, 2, ['DDD']),
		difftrack.SquashResults(difftrack.ListDiff.DELETE, 1, 2, []),
	]
	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs


def test_empty_squash():
	diffs = []
	out_diffs = []

	assert list(difftrack.squash_difftrack_results(diffs)) == out_diffs
