# display.py checks without the panel: line placement on two-color panels, highlight styles,
# the whole main loop with fake hardware, and panel retry after a failed start.
# Needs Pillow and DejaVu Sans (see extract.find_font). Run: python3 dev/sim/sim_display.py

import glob
import os
import sys
import tempfile
import threading
import time
import types

from extract import SCRIPTS_DIR, find_font

failures = []
REAL_SLEEP = time.sleep


def check(name, ok, detail=''):
	print(('ok    ' if ok else 'FAIL  ') + name + ('' if ok else f'\n      {detail}'))
	if not ok:
		failures.append(name)


def module(name, **attributes):
	m = types.ModuleType(name)
	m.__dict__.update(attributes)
	sys.modules[name] = m
	return m


# fake hardware and helpers, installed before display.py is imported
sim = tempfile.mkdtemp()
os.makedirs(f'{sim}/content')
panel_frames = []
logs = []
i2c_failures = [0]
driver_failures = [0]


class FakePanel:
	def __init__(self, *args, **kwargs):
		if driver_failures[0]:
			driver_failures[0] -= 1
			raise OSError('[Errno 121] Remote I/O error')
		self.mode = '1'
		self.width = 128
		self.height = 64
		self.persist = False

	def capabilities(self, width, height, rotate, mode):
		self.width, self.height, self.mode = width, height, mode

	def contrast(self, level):
		pass

	def show(self):
		pass

	def display(self, image):
		panel_frames.append(image)


def fake_i2c(**kwargs):
	if i2c_failures[0]:
		i2c_failures[0] -= 1
		raise OSError('[Errno 121] Remote I/O error')
	return object()


module('RPi')
module('RPi.GPIO', cleanup=lambda: None)
sys.modules['RPi'].GPIO = sys.modules['RPi.GPIO']
module('configobj', ConfigObj=dict)
for name in ['luma', 'luma.core', 'luma.core.interface', 'luma.oled', 'luma.lcd']:
	module(name)
module('luma.core.interface.serial', i2c=fake_i2c, spi=None, pcf8574=None)
module('luma.core.interface.parallel', bitbang_6800=None)
module('luma.core.render', canvas=None)
module('luma.oled.device', ssd1306=FakePanel, ssd1309=FakePanel, ssd1322=FakePanel, ssd1331=FakePanel, sh1106=FakePanel)
module('luma.lcd.device', st7735=FakePanel)

sys.path.insert(0, SCRIPTS_DIR)
import lib_setup

conf = {k: v['value'] for k, v in lib_setup.setup._setup__get_config_standard(None).items()}
conf.update({
	'const_DISPLAY_CONTENT_OLD_FILE': f'{sim}/old.txt', 'const_DISPLAY_LINES_LIMIT': 10, 'const_DISPLAY_STATUSBAR_TOGGLE_SEC': 5,
	'const_FONT_PATH': find_font(), 'const_DISPLAY_CONTENT_PATH': f'{sim}/content', 'const_DISPLAY_IMAGE_EXPORT_FILE': f'{sim}/display.png',
	'const_DISPLAY_IMAGE_KEEP_PATH': f'{sim}/keep', 'const_TASKS_PATH': f'{sim}/tasks',
	'conf_DISP': 'display', 'conf_DISP_CONNECTION': 'I2C', 'conf_DISP_DRIVER': 'SSD1306', 'conf_DISP_I2C_ADDRESS': 0x3c,
	'conf_MENU_ENABLED': False, 'conf_DISP_FRAME_TIME': 1, 'conf_DISP_SHOW_STATUSBAR': True,
})
lib_setup.setup = lambda *a, **k: types.SimpleNamespace(get_val=lambda key: conf[key])
module('lib_log', log=lambda: types.SimpleNamespace(message=lambda message, level=10: logs.append(message)))
module('lib_comitup', comitup=lambda: types.SimpleNamespace(get_status=lambda: {'state': 'CONNECTED'}))
module('lib_network')
module('lib_system', get_uptime_sec=lambda: 1.0)
module('displaymenu', MENU_CONTROLLER=lambda: types.SimpleNamespace(terminate=lambda: None), menu=lambda *a: None)


class ContentFiles:
	def __init__(self, setup):
		pass

	def get_next_file_name(self):
		files = sorted(glob.glob(f'{sim}/content/*'))
		return files[0] if files else ''


module('lib_display', display_content_files=ContentFiles)

import display

clock = [1000.0]
display.time = types.SimpleNamespace(time=lambda: clock[0], sleep=lambda s: (clock.__setitem__(0, clock[0] + 1), REAL_SLEEP(0.002)))

from PIL import Image
Image.new('1', (128, 64), 1).save(f'{sim}/white.png')


def put(name, lines):
	path = f'{sim}/content/{name}'
	open(path, 'w').write('\n'.join(lines))
	os.utime(path, (time.time() - 5, time.time() - 5))


def run_main(setup_messages, run_seconds=8):
	for f in glob.glob(f'{sim}/content/*'):
		os.remove(f)
	if os.path.exists(f'{sim}/old.txt'):
		os.remove(f'{sim}/old.txt')
	d = display.DISPLAY()
	start_ready = d.hardware_ready
	setup_messages()
	start = clock[0]

	def kill_later():
		while clock[0] < start + run_seconds:
			REAL_SLEEP(0.01)
		put('999', ['set:kill'])

	threading.Thread(target=kill_later).start()
	d.main()
	return d, start_ready


def lit_rows(image):
	px = image.load()
	return [y for y in range(image.height) if any(px[x, y] for x in range(image.width))]


print('two-color panel and highlight styles')
for style in ['bar', 'frame', 'underline', 'plain']:
	conf.update({'conf_DISP_BAND_TOP': 16, 'conf_DISP_HIGHLIGHT_STYLE': style})
	panel_frames.clear()
	run_main(lambda: put('001', [':Pronto', ':Insira o destino']))
	rows = set(lit_rows(panel_frames[0])) if panel_frames else {15}
	check(f'band 16, {style}: nothing lit on the color border (rows 15-16)', not rows & {15, 16}, f'lit rows {sorted(rows & {15, 16})}')

conf['conf_DISP_HIGHLIGHT_STYLE'] = 'bar'
for band, want_lines in [(0, 5), (16, 5)]:
	conf['conf_DISP_BAND_TOP'] = band
	d = display.DISPLAY()
	check(f'band {band}: {want_lines} lines with font 12', d.maxLines == want_lines, f'maxLines {d.maxLines}')


print('main loop')
for band in (0, 16):
	for style in ['bar', 'frame', 'underline', 'plain']:
		conf.update({'conf_DISP_BAND_TOP': band, 'conf_DISP_HIGHLIGHT_STYLE': style})
		panel_frames.clear()
		logs.clear()

		def messages():
			put('001', [':Pronto', ':Insira o destino'])
			put('002', ['set:clear,time=0.1', 's=hc:Arm. interno', 's=hc:Backup de Armaz. USB', 's=hc:1.243 de 3.980', 's=hc:Tempo: 00:14', 's=hc:PGBAR=31.2'])
			put('003', ['set:time=0.1,temp', f':IMAGE={sim}/white.png'])
			put('004', ['set:time=0.1', 's=a:ERRO NA CÓPIA', ':Não formate o cartão'])
			os.makedirs(f'{sim}/tasks', exist_ok=True)
			open(f'{sim}/tasks/t.txt', 'w').write('DB\n')

		error = None
		try:
			run_main(messages)
		except Exception as e:
			error = repr(e)
		os.remove(f'{sim}/tasks/t.txt')
		check(f'band {band}, {style}: runs through messages, progress, image, alert, task', error is None and len(panel_frames) >= 4, error or f'{len(panel_frames)} frames')


print('temporary messages')
conf.update({'conf_DISP_BAND_TOP': 16, 'conf_DISP_HIGHLIGHT_STYLE': 'bar'})
panel_frames.clear()


def saved_after_ready():
	put('001', [':Pronto', ':Insira o destino'])
	put('002', ['set:temp,time=3', 'Configurações', 'salvas.'])


run_main(saved_after_ready, run_seconds=12)
old_text = open(f'{sim}/old.txt').read()
check('"settings saved" is temporary: the waiting message is kept as the current screen', 'Pronto' in old_text and 'salvas' not in old_text, old_text)
check('the screen goes back to the waiting message', len(panel_frames) >= 3 and panel_frames[-1].tobytes() == panel_frames[0].tobytes(),
	f'{len(panel_frames)} frames')


print('panel retry')
conf.update({'conf_DISP_BAND_TOP': 16, 'conf_DISP_HIGHLIGHT_STYLE': 'underline'})
panel_frames.clear()
logs.clear()
i2c_failures[0] = 1
d, start_ready = run_main(lambda: put('001', [':Pronto', ':Insira o destino']), run_seconds=45)
check('I2C fails at start: runs without the panel first', start_ready is False)
check('panel answers on retry within 30 s and gets the screen', d.hardware_ready and len(panel_frames) >= 1, f'ready {d.hardware_ready}, frames {len(panel_frames)}')
check('both events are in the log', [l.split(' (')[0] for l in logs] == ['Display connection to I2C could not be enabled.', 'Display answers again.'], logs)

# the panel is missing from the bus: the bus opens, the SSD1306 driver fails (seen on a real box, crashed in a loop before)
panel_frames.clear()
logs.clear()
driver_failures[0] = 1
error = None
try:
	d, start_ready = run_main(lambda: put('001', [':Pronto', ':Insira o destino']), run_seconds=45)
except Exception as e:
	error = repr(e)
check('driver fails at start: no crash, runs without the panel', error is None and start_ready is False, error)
check('panel answers later: gets the screen', error is None and d.hardware_ready and len(panel_frames) >= 1, error or f'ready {d.hardware_ready}')
check('the driver error text is logged', error is None and 'Remote I/O error' in logs[0], logs)

raise SystemExit(f'{len(failures)} failed' if failures else 0)
