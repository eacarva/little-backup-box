# Pull methods out of a real script so they run without the Raspberry Pi.
# The code under test is read from the file each time, never copied into the tests.

import ast
import os

SCRIPTS_DIR = os.environ.get('LBB_SCRIPTS_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts')


def load_methods(script, class_name, method_names, namespace):
	"""Return a class holding only the named methods of class_name in scripts/<script>.
	Double-underscore attributes keep their name mangling because the class name is the same."""
	path = os.path.join(SCRIPTS_DIR, script)
	src = open(path).read()
	cls = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == class_name)
	bodies = [ast.get_source_segment(src, n) for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in method_names]
	missing = set(method_names) - {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
	assert not missing, f'{script}: {class_name} has no {missing}'
	code = f'class {class_name}:\n' + '\n'.join('\n'.join('\t' + line for line in body.split('\n')) for body in bodies)
	exec(code, namespace)
	return namespace[class_name]


def find_font():
	for path in [
		os.environ.get('DEJAVU_SANS', ''),
		os.path.expanduser('~/Library/Fonts/DejaVuSans.ttf'),
		'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
	]:
		if path and os.path.isfile(path):
			return path
	raise SystemExit('DejaVuSans.ttf not found: install it (macOS: brew install --cask font-dejavu) or set DEJAVU_SANS')
