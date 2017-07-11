Difftrack
=========

``difftrack`` is a tool for keeping track of changes in data structures.
It makes it possible for multiple "listeners" to see
changes in a dict, a list or any other data structure you want to
observe and support (these structures are called "dispatchers").

``difftrack`` has two main classes:

- ``Dispatcher`` - acts like a data structure you write to but also sends
  all changes (diffs) to all its listeners.
- ``Listener`` - a listener is connected to one dispatcher and applies incomming
  diffs to its internal structure so each listener looks like the original data
  structure after applying all those diffs.

This division allows ``difftrack`` to have multiple listeners in
different stages of applying diffs, and it enables listeners
with special abbilities (e.g. ``difftrack.utils.BoundedListDiffHandler``
implementing a "top N" list: the list never exceeds a certain fixed size
but when some items are deleted, previously invisible elements appear).

Basic usage
-----------

In the following example we are going to create a list dispatcher (you can
write to it as to a list: use operation ``__setitem__``, ``__delitem__``
and ``insert``) and two listeners that will listen for diffs and keep
their own internal state.

.. code:: python

	>>> import difftrack
	>>> dispatcher = difftrack.ListDispatcher()
	>>> listener1 = difftrack.ListListener()
	>>> listener2 = difftrack.ListListener()
	>>> dispatcher.add_listener(listener1)
	>>> dispatcher.add_listener(listener2) # create listeners and add them to dispatcher

	>>> dispatcher.insert(0, 'AAA') # insert string 'AAA' to the first position in list
	>>> listener1.get_snapshot() # Diffs are not applied until get_new_diffs() is called
	[]
	>>> listener1.get_new_diffs() # now we get all diffs that have not been processed yet
	[(difftrack.ListDiff.INSERT, 0, 'AAA')]
	>>> listener1.get_snapshot() # and we see that listener1's snapshot now contains what we expect
	['AAA']
	>>> listener2.get_snapshot() # second listener still hasn't got anything because we haven't read its diffs
	[]

	>>> dispatcher.insert(0, 'BBB') # insert new string to 'BBB'
	>>> listener1.get_new_diffs() # we need to read new diffs to get current state
	[(difftrack.ListDiff.INSERT, 0, 'BBB')]
	>>> listener1.get_snapshot() # we inserted 'BBB' to first position so 'AAA' was moved to second position
	['BBB', 'AAA']

	>>> del dispatcher[0] # remove the first element from th list (now 'BBB')
	>>> listener1.get_new_diffs()
	[(difftrack.ListDiff.DELETE, 0, None)]
	>>> listener1.get_snapshot() # we deleted 'BBB' so only 'AAA' remains
	['AAA']

	>>> dispatcher[0] = 'CCC' # overwrite the first element
	>>> listener1.get_new_diffs()
	[(difftrack.ListDiff.REPLACE, 0, 'CCC')]
	>>> listener1.get_snapshot()
	['CCC'] # the first and only element in list was overwritten

	>>> listener2.get_new_diffs() # finally get all diffs for listener2
	[(<ListDiff.INSERT: 0>, 0, 'AAA'),
	 (<ListDiff.INSERT: 0>, 0, 'BBB'),
	 (<ListDiff.DELETE: 2>, 0, None),
	 (<ListDiff.REPLACE: 1>, 0, 'CCC')]
	>>> listener2.get_snapshot() # listener2 is now also up to date
	['CCC']

Similarly you can use ``difftrack`` with ``DictDispatcher`` and
``DictListener``: you write your changes to an instance of
``DictDispatcher`` and after applying diffs to listeners you can get a
snapshot of the current dictionary state.

Callbacks
---------

``on_change``
~~~~~~~~~~~~~

We can also add a callback to a listener so that we are notified when a diff
comes:

.. code:: python

	import difftrack

	>>> dispatcher = difftrack.ListDispatcher()
	>>> def double_inserted_items(dtype, index, value):
		''' This generates a new diff *while the current one is processed!* '''
		if dtype is difftrack.ListDiff.INSERT:
			dispatcher[index] = value * 2

	>>> listener = difftrack.ListListener(on_change = double_inserted_items) # set function as a callback
	>>> dispatcher.add_listener(listener)
	>>> dispatcher.insert(0, 7) # insert 7 at index 0 and expect that the result will be doubled
	>>> listener.get_new_diffs()
	[
		(difftrack.ListDiff.INSERT, 0, 7),
		(difftrack.ListDiff.REPLACE, 0, 14)
	]
	>>> listener.get_snapshot()
	[14]

In this example we show the ``on_change`` callback and its ability to
work with a dispatcher. Note that we are first using the
``ListDiff.INSERT`` operation but the callback triggers a
``ListDiff.REPLACE`` operation. If it would lead to ``ListDiff.INSERT`` again we
would end in recursion and after 10 tries ``difftrack`` would raise an
exception.

``on_finalize_batch``
~~~~~~~~~~~~~~~~~~~~~

Let's say that you are receiving batches of changes and you apply them
on by one. Now when you want to be noted for new changes you may use
``on_change`` callback but it would be triggered every time you perform
an operation on the dispatcher. We may want to be notified only when we
apply all changes in our batch to the dispatcher. There is
another callback for this, ``on_finalize_batch``:

.. code:: python

	>>> import difftrack
	>>> dispatcher = difftrack.DictDispatcher()
	>>> def finalize():
			print('FINALIZED')

	>>> def on_change(*args):
			print('CHANGE')

	>>> listener = difftrack.DictListener(on_change = on_change, on_finalize_batch = finalize)
	>>> dispatcher.add_listener(listener)
	>>> with dispatcher: # use the dispatcher as a context manager
			dispatcher[0] = 0
			dispatcher[1] = 1
			dispatcher[2] = 2

	CHANGE
	CHANGE
	CHANGE
	FINALIZED

We can see that the ``on_change`` callback is called every time but
``on_finalize_batch`` only when we exit the context manager.

Utilities
---------

There are several utilities that you might find useful.

``data_mapper``
~~~~~~~~~~~~~~~

Data mapper applies a function to every data field:

.. code:: python

	>>> import difftrack
	>>> def mapper(data: str) -> str:
			return data.lower()
	>>> dispatcher = difftrack.ListDispatcher()
	>>> listener = difftrack.ListListener()
	>>> dispatcher.add_listener(difftrack.data_mapper(mapper)(listener))

	>>> dispatcher.insert(0, 'AAA')
	>>> dispatcher.insert(0, 'BBB')
	>>> listener.get_new_diffs()
	[
		(difftrack.ListDiff.INSERT, 0, 'aaa'),
		(difftrack.ListDiff.INSERT, 0, 'bbb')
	]
	>>> listener.get_snapshot()
	['bbb', 'aaa']

``compact_dict_diffs``
~~~~~~~~~~~~~~~~~~~~~~

When you update a dict item several times or even delete it you
sometimes don't want to send all the changes. Only those that are
applicable now:

.. code:: python

	>>> diffs = [
		(difftrack.DictDiff.SET, 'x', 123),
		(difftrack.DictDiff.SET, 'y', 456),
		(difftrack.DictDiff.SET, 'y', 9999),
		(difftrack.DictDiff.DELETE, 'x', None),
	]
	>>> difftrack.compact_dict_diffs(diffs)
	[
		(difftrack.DictDiff.SET, 'y', 9999),
		(difftrack.DictDiff.DELETE, 'x', None),
	]

``BoundedListDiffHandler``
~~~~~~~~~~~~~~~~~~~~~~~~~~

If we want to keep our list bounded we can use
``difftrack.BoundedListDiffHandler``

.. code:: python

	>>> import difftrack
	>>> listener = difftrack.ListListener()
	>>> dispatcher = difftrack.ListDispatcher()
	>>> dispatcher.add_listener(difftrack.BoundedListDiffHandler(listener, 2)) # bound listener to 2 elements

	>>> dispatcher.insert(0, 'a')
	>>> dispatcher.insert(1, 'b')
	>>> dispatcher.insert(2, 'c')
	>>> dispatcher.insert(3, 'd')
	>>> listener.get_new_diffs()
	[
		(difftrack.ListDiff.INSERT, 0, 'a'),
		(difftrack.ListDiff.INSERT, 1, 'b'),
	]
	>>> listener.get_snapshot()
	['a', 'b']

	>>> del dispatcher[0]
	>>> listener.get_new_diffs() # 'a' is deleted and 'c' moves to the empty index 1
	[
		(<ListDiff.DELETE: 2>, 0, None),
		(<ListDiff.INSERT: 0>, 1, 'c')
	]
	>>> listener.get_snapshot()
	['b', 'c']

``squash_difftrack_results``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This function groups consecutive diffs.

.. code:: python

	>>> import difftrack
	>>> diffs = [
		(difftrack.ListDiff.INSERT, 1, 'A'),
		(difftrack.ListDiff.INSERT, 2, 'B'),
		(difftrack.ListDiff.INSERT, 3, 'C'),
		(difftrack.ListDiff.REPLACE, 1, 'D'),
		(difftrack.ListDiff.DELETE, 1, [])
	]
	>>> list(difftrack.squash_difftrack_results(diffs))
	[
		SquashResults(operation=<difftrack.ListDiff.INSERT: 0>, start=1, stop=3, payload=['A', 'B', 'C']),
		SquashResults(operation=<difftrack.ListDiff.REPLACE: 1>, start=1, stop=2, payload=['D']),
		SquashResults(operation=<difftrack.ListDiff.DELETE: 2>, start=1, stop=2, payload=[])
	]

You can see that the three consecutive inserts are squashed into a single message. Note that the result
is no longer a difftrack diff.
