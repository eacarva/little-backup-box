# Backup loop checks without hardware: which source is copied next (normal and station mode),
# run()/finish() control flow, and the per-source error check. Run: python3 dev/sim/sim_backup_loop.py

import os
import types

from extract import SCRIPTS_DIR, load_methods

failures = []


def check(name, got, want):
	ok = got == want
	print(('ok    ' if ok else 'FAIL  ') + name + ('' if ok else f'\n      got  {got}\n      want {want}'))
	if not ok:
		failures.append(name)


# source selection: the real lines of backup.backup() from "SourceStorageType = self.SourceStorageType" to the wait "continue"
def source_selection_code():
	lines = open(os.path.join(SCRIPTS_DIR, 'backup.py')).read().split('\n')
	start = next(i for i, l in enumerate(lines) if l.strip().startswith('SourceStorageType') and 'self.SourceStorageType' in l)
	end = next(i for i in range(start, len(lines)) if lines[i].strip() == 'continue')
	block = '\n'.join(lines[start:end + 1])
	# stand-in for the copy: remember the source, then continue like backup() does
	return ('class backup:\n\tdef sel(self, processed):\n' + block +
		'\n\t\t\tprocessed.append((SourceStorageType, Identifier))\n\t\t\tIdentifier_OLD\t= Identifier\n'
		'\t\t\tif not dynamicSources:\n\t\t\t\tbreak\n\t\treturn(True)\n')


class Waiting(Exception):
	pass


def run_batches(source, station, usb, cams=(), events=None, batches=4, max_wait=5):
	world = {'usb': list(usb), 'cams': list(cams), 'tick': 0, 'waits': 0}
	events = dict(events or {})

	def sleep(seconds):
		world['tick'] += 1
		world['waits'] += 1
		for action, device in events.pop(world['tick'], []):
			target = world['usb'] if action.endswith('usb') else world['cams']
			(target.append if action.startswith('plug') else target.remove)(device)
		if world['waits'] > max_wait:
			raise Waiting()

	namespace = {
		'time': types.SimpleNamespace(sleep=sleep),
		'lib_storage': types.SimpleNamespace(
			get_available_cameras=lambda: list(world['cams']),
			get_available_partitions=lambda StorageType, TargetDeviceIdentifier, excludePartitions=[]:
				[d for d in world['usb'] if d != TargetDeviceIdentifier and d not in excludePartitions]),
	}
	exec(source_selection_code(), namespace)
	b = namespace['backup'].__new__(namespace['backup'])
	b.SourceStorageType = source
	b.SourceService = ''
	b.DeviceIdentifierPresetSource = ''
	b._backup__StationMode = station
	b._backup__completedSources_usb = []
	b._backup__completedSources_camera = []
	b.TargetDevice = types.SimpleNamespace(DeviceIdentifier='SSD')
	b._backup__lan = types.SimpleNamespace(l=lambda k: k)
	b._backup__display = types.SimpleNamespace(message=lambda m: None)

	result = []
	for _ in range(batches):
		processed = []
		world['waits'] = 0
		try:
			b.sel(processed)
			result.append(processed)
		except Waiting:
			result.append(processed + ['WAITING'])
			break
	return result


print('source selection')
check('normal: copies what is plugged, then ends',
	run_batches('anyusb', False, ['SSD', 'A', 'B'], batches=1), [[('usb', 'A'), ('usb', 'B')]])
check('normal: waits for a source, copies it, ends',
	run_batches('usb', False, ['SSD'], events={2: [('plug_usb', 'A')]}, batches=1), [[('usb', 'A')]])
check('station: plugged card not copied again, unplugged forgotten, plugged again copied again',
	run_batches('anyusb', True, ['SSD', 'A', 'B'], events={2: [('unplug_usb', 'A'), ('plug_usb', 'C')], 5: [('plug_usb', 'A')]}),
	[[('usb', 'A'), ('usb', 'B')], [('usb', 'C')], [('usb', 'A')], ['WAITING']])
check('station: camera, card, then a new camera',
	run_batches('anyusb', True, ['SSD', 'A'], cams=['CAM1'], events={1: [('unplug_cam', 'CAM1'), ('plug_cam', 'CAM2')]}, batches=3),
	[[('camera', 'CAM1'), ('usb', 'A')], [('camera', 'CAM2')], ['WAITING']])
check('station: the target is never a source',
	run_batches('usb', True, ['SSD', 'A'], events={2: [('unplug_usb', 'A')]}, batches=3), [[('usb', 'A')], ['WAITING']])


print('run() and finish()')
calls = []


class Lan:
	def l(self, key):
		return {'box_backup_complete': 'Backup complete', 'box_backup_source_failed_1': 'COPY ERROR',
			'box_backup_source_failed_2': 'Do not format', 'box_backup_failed_attempts': 'failed attempts'}.get(key, key)


namespace = {
	'lib_system': types.SimpleNamespace(rpi_leds=lambda **k: None),
	'lib_storage': types.SimpleNamespace(umount=lambda *a: None),
	'lib_poweroff': types.SimpleNamespace(poweroff=lambda action, summary: types.SimpleNamespace(poweroff=lambda: calls.append(('summary', summary)))),
}
Backup = load_methods('backup.py', 'backup', ['run', 'finish'], namespace)


def run_scenario(station, backup_results, fail_on_call=None, summary=(':Backup complete.', ':3 of 3 files copied', ':0 failed attempts', ':Duration: 0:01:00')):
	calls.clear()
	b = Backup.__new__(Backup)
	results = iter(backup_results)
	count = [0]
	b._backup__StationMode = station
	b._backup__SourcesFailed = 0
	b._backup__TIMSCopied = False
	b._backup__setup = None
	b._backup__lan = Lan()
	b._backup__cleanup = lambda: None
	b.backup_combination_possible = lambda: True
	b.TargetDevice = object()
	b.SourceStorageType = 'anyusb'
	b.TransferMode = 'rsync'
	b.DoRenameFiles = False
	b.ForceSyncDatabase = True
	b.DoUpdateEXIF = False
	b.DoGenerateThumbnails_primary = True
	b.SecondaryBackupFollows = False
	b.PowerOff = False
	b.syncDatabase = lambda: calls.append('db')
	b.generateThumbnails = lambda Device: calls.append('thumbnails')

	class Reporter:
		def prepare_display_summary(self):
			self.display_summary = list(summary)
	b._backup__reporter = Reporter()

	def backup():
		count[0] += 1
		if fail_on_call == count[0]:
			b._backup__SourcesFailed += 1
		return next(results, None)
	b.backup = backup
	b.run()
	return count[0], [c[1] for c in calls if isinstance(c, tuple)][0]


check('normal, all fine: one batch, "complete"',
	run_scenario(False, [True]), (1, [':Backup complete.', ':3 of 3 files copied', ':0 failed attempts', ':Duration: 0:01:00']))
check('normal, first card failed (last one fine): never "complete", 5 lines',
	run_scenario(False, [True], fail_on_call=1), (1, ['s=a:COPY ERROR', ':Do not format', ':3 of 3 files copied', ':Duration: 0:01:00']))
check('station: two clean batches, then an aborted one stops the station',
	run_scenario(True, [True, True, None])[0], 3)
check('station: a failure stops the station after that batch',
	run_scenario(True, [True, True, True], fail_on_call=2)[0], 2)


print('reporter.has_errors()')
Reporter = load_methods('lib_backup.py', 'reporter', ['has_errors'], {})


def has_errors(reports):
	r = Reporter.__new__(Reporter)
	r._reporter__BackupReports = reports
	return r.has_errors()


check('no tries: no error', has_errors({}), False)
check('error only in an earlier try: no error', has_errors({'/': [{'Errors': ['x']}, {'Errors': []}]}), False)
check('error in the last try of any folder: error', has_errors({'/': [{'Errors': []}], 'DCIM': [{'Errors': ['missing']}]}), True)

raise SystemExit(f'{len(failures)} failed' if failures else 0)
