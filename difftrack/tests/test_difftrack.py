from unittest import mock

import difftrack



def test_list():
	dispatcher = difftrack.ListDispatcher()
	listener = difftrack.ListListener()
	dispatcher.add_listener(listener)

	# Insert 1
	dispatcher.insert(0, 'AAA')
	assert listener.get_snapshot() == [], 'Diffs are not applied until get_new_diffs is called'
	assert listener.get_new_diffs() == [(difftrack.ListDiff.INSERT, 0, 'AAA'),]
	assert listener.get_snapshot() == ['AAA',]
	# Insert 2
	dispatcher.insert(0, 'BBB')
	assert listener.get_new_diffs() == [(difftrack.ListDiff.INSERT, 0, 'BBB'),]
	assert listener.get_new_diffs() == []
	assert listener.get_snapshot() == ['BBB', 'AAA',]
	# Delete
	del dispatcher[0]
	assert listener.get_snapshot() == ['BBB', 'AAA',], 'Diffs are not applied until get_new_diffs is called'
	assert listener.get_new_diffs() == [(difftrack.ListDiff.DELETE, 0, None),]
	assert listener.get_snapshot() == ['AAA',]
	# Replace
	dispatcher[0] = 'CCC'
	assert listener.get_snapshot() == ['AAA',], 'Diffs are not applied until get_new_diffs is called'
	assert listener.get_new_diffs() == [(difftrack.ListDiff.REPLACE, 0, 'CCC'),]
	assert listener.get_snapshot() == ['CCC',]



def test_mapper():
	def mapper(data: str) -> str:
		return data.lower()
	dispatcher = difftrack.ListDispatcher()
	listener = difftrack.ListListener()
	dispatcher.add_listener(difftrack.data_mapper(mapper)(listener))

	dispatcher.insert(0, 'AAA')
	dispatcher.insert(0, 'BBB')
	assert listener.get_new_diffs() == [
		(difftrack.ListDiff.INSERT, 0, 'aaa'),
		(difftrack.ListDiff.INSERT, 0, 'bbb'),
	]
	assert listener.get_snapshot() == ['bbb', 'aaa']



def test_dict():
	dispatcher = difftrack.DictDispatcher()
	listener = difftrack.DictListener()
	dispatcher.add_listener(listener)

	dispatcher['x'] = 123
	dispatcher['y'] = 456
	assert listener.get_snapshot() == {}, 'Diffs are not applied until get_new_diffs is called'
	assert listener.get_new_diffs() == [
		(difftrack.DictDiff.SET, 'x', 123),
		(difftrack.DictDiff.SET, 'y', 456),
	]
	assert listener.get_snapshot() == {'x': 123, 'y': 456}

	dispatcher['y'] = 9999
	del dispatcher['x']
	assert listener.get_new_diffs() == [
		(difftrack.DictDiff.SET, 'y', 9999),
		(difftrack.DictDiff.DELETE, 'x', None),
	]
	assert listener.get_snapshot() == {'y': 9999}



def test_yield_new_diffs():
	dispatcher = difftrack.DictDispatcher()
	listener = difftrack.DictListener()
	dispatcher.add_listener(listener)

	dispatcher['x'] = 123
	dispatcher['y'] = 456
	generator = listener.yield_new_diffs()
	assert listener.get_snapshot() == {}, 'Diffs are not applied until yield_new_diffs is iterated'
	assert next(generator) == (difftrack.DictDiff.SET, 'x', 123)
	assert listener.get_snapshot() == {'x': 123}
	assert next(generator) == (difftrack.DictDiff.SET, 'y', 456)
	assert listener.get_snapshot() == {'x': 123, 'y': 456}

	dispatcher['y'] = 9999
	del dispatcher['x']
	assert next(generator) == (difftrack.DictDiff.SET, 'y', 9999)
	assert next(generator) == (difftrack.DictDiff.DELETE, 'x', None)
	assert listener.get_snapshot() == {'y': 9999}



def test_on_change():
	cb = mock.Mock()
	listener = difftrack.DictListener(on_change = cb)
	listener(difftrack.DictDiff.SET, 'x', 123)
	cb.assert_called_once_with(difftrack.DictDiff.SET, 'x', 123)



def test_diff_recursion():
	dispatcher = difftrack.ListDispatcher()

	def double_inserted_items(dtype, index, value):
		''' This generates a new diff *while the current one is processed!* '''
		if dtype is difftrack.ListDiff.INSERT:
			dispatcher[index] = value * 2

	listener1 = difftrack.ListListener(on_change = double_inserted_items)
	listener2 = difftrack.ListListener()
	dispatcher.add_listener(listener1)
	dispatcher.add_listener(listener2)

	dispatcher.insert(0, 7)
	assert listener1.get_new_diffs() == [
		(difftrack.ListDiff.INSERT, 0, 7),
		(difftrack.ListDiff.REPLACE, 0, 14),
	]
	assert listener2.get_new_diffs() == [
		(difftrack.ListDiff.INSERT, 0, 7),
		(difftrack.ListDiff.REPLACE, 0, 14),
	]



def test_finalize():
	cb = mock.Mock()
	dispatcher = difftrack.ListDispatcher()
	listener = difftrack.ListListener(on_finalize_batch = cb)
	dispatcher.add_listener(listener)

	with dispatcher:
		dispatcher.insert(0, 'AAA')
		dispatcher.insert(0, 'BBB')
		del dispatcher[0]
		dispatcher[0] = 'CCC'

		cb.assert_not_called()

	cb.assert_called_once_with()



def test_finalize_function_listener():
	'''
	Test that we don't care that listener does not have `.finalize_batch()`
	'''
	function_listener_counter = 0
	def function_listener(*_args):
		nonlocal function_listener_counter
		function_listener_counter += 1

	dispatcher = difftrack.ListDispatcher()
	dispatcher.add_listener(function_listener)

	with dispatcher:
		dispatcher.insert(0, 'AAA')
		dispatcher.insert(0, 'BBB')
		del dispatcher[0]
		dispatcher[0] = 'CCC'

		assert function_listener_counter == 4
	# no error after finalize_batch is called



def test_finalize_no_callback():
	'''
	Test that `finalize_batch` on listner without cb has no effect
	'''
	dispatcher = difftrack.ListDispatcher()
	listener_wo_on_finalize_cb = difftrack.ListListener()
	dispatcher.add_listener(listener_wo_on_finalize_cb)

	with dispatcher:
		dispatcher.insert(0, 'AAA')
		dispatcher.insert(0, 'BBB')
		del dispatcher[0]
		dispatcher[0] = 'CCC'



def test_do_not_call_finalize_if_not_needed():
	cb = mock.Mock()
	dispatcher = difftrack.ListDispatcher()
	listener = difftrack.ListListener(on_finalize_batch = cb)
	dispatcher.add_listener(listener)

	with dispatcher:
		pass
	cb.assert_not_called()

	with dispatcher:
		dispatcher.insert(0, 'AAA')
	cb.assert_called_once_with()
	cb.reset_mock()

	with dispatcher:
		pass
	cb.assert_not_called()
