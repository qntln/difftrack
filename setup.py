import os
from distutils.core import setup



def read(relpath: str) -> str:
	with open(os.path.join(os.path.dirname(__file__), relpath)) as f:
		return f.read()


setup(
	name = 'difftrack',
	version = read('version.txt').strip(),
	description = 'Keep track of changes in data structures.',
	long_description = read('README.rst'),
	author = 'Quantlane',
	author_email = 'code@quantlane.com',
	url = 'https://github.com/qntln/difftrack',
	license = 'Apache 2.0',
	install_requires = [
		'fastenum==0.0.1',
		'attrs==17.2.0',
		'sortedcontainers==1.5.7',
	],
	packages = [
		'difftrack',
	],
	classifiers = [
		'Development Status :: 4 - Beta',
		'License :: OSI Approved :: Apache Software License',
		'Natural Language :: English',
		'Programming Language :: Python :: 3 :: Only',
		'Programming Language :: Python :: 3.5',
	]
)
