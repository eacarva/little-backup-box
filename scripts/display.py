#!/usr/bin/env python

# Author: Stefan Saam, github@saams.de

#######################################################################
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#######################################################################

# Display messages are read from const_DISPLAY_CONTENT_PATH
#
# format:
# FORMAT-OPTIONS:TEXT
#
# multiple format options can be separated by "," (without spaces)
#
# for standard-format just use ":"
#
## s: style
# s=b: BASIC
# s=h: HIGHLIGHT
# s=a: ALERT
# s=s: statusbar
#
## u: underline
#
## PGBAR
# s=b:PGBAR=20
#
## IMAGE
# IMAGE=PATH
#
#
# To set global parameters you can use a 'set:'-line:
# multiple options can be separated by "," (without spaces)
# set:clear,time=1.5,temp
# clear:	Do not display lines from old page
# time=2:	Display time in seconds (empty for standard config)
# temp:		show previous screen again after this
# hidden:	markertext to write into const_DISPLAY_CONTENT_OLD_FILE
# kill:		terminate display daemon

import os
import RPi.GPIO as GPIO
import pathlib
import shutil
import signal
import subprocess
import sys
import threading
import time

import lib_comitup
import lib_log
import lib_network
import lib_setup
import lib_system

from luma.core.interface.serial import i2c, spi, pcf8574
from luma.core.interface.parallel import bitbang_6800
from luma.core.render import canvas
from luma.oled.device import ssd1306, ssd1309, ssd1322, ssd1331, sh1106
from luma.lcd.device import st7735

from PIL import Image, ImageDraw, ImageFont

import displaymenu
from lib_display import display_content_files

# import lib_debug
# xx	= lib_debug.debug()

WORKING_DIR = os.path.dirname(__file__)

class DISPLAY(object):

	def __init__(self):
		# Register the shutdown/reboot signals
		signal.signal(signal.SIGTERM, self.terminate)  # Signal for shutdown
		signal.signal(signal.SIGINT, self.terminate)   # Interrupt signal

		self.loop_continue	= True

		# cleanup pins
		GPIO.cleanup()

		# objects
		self.__setup							= lib_setup.setup()
		self.__log								= lib_log.log()
		self.__display_content_files			= display_content_files(self.__setup)

		# setup
		self.__conf_DISP_CONNECTION					= self.__setup.get_val('conf_DISP_CONNECTION')
		self.__conf_DISP_DRIVER						= self.__setup.get_val('conf_DISP_DRIVER')
		self.__conf_DISP_I2C_ADDRESS				= self.__setup.get_val('conf_DISP_I2C_ADDRESS')
		self.__conf_DISP_SPI_PORT					= self.__setup.get_val('conf_DISP_SPI_PORT')
		self.__conf_DISP_RESOLUTION_X				= self.__setup.get_val('conf_DISP_RESOLUTION_X')
		self.__conf_DISP_RESOLUTION_Y				= self.__setup.get_val('conf_DISP_RESOLUTION_Y')
		self.__conf_DISP_OFFSET_X					= self.__setup.get_val('conf_DISP_OFFSET_X')
		self.__conf_DISP_OFFSET_Y					= self.__setup.get_val('conf_DISP_OFFSET_Y')
		self.__conf_DISP_ROTATE						= self.__setup.get_val('conf_DISP_ROTATE')
		self.__conf_DISP_CONTRAST					= self.__setup.get_val('conf_DISP_CONTRAST')
		self.__conf_DISP_COLOR_BGR					= self.__setup.get_val('conf_DISP_COLOR_BGR')
		self.__conf_DISP_COLOR_INVERSE				= self.__setup.get_val('conf_DISP_COLOR_INVERSE')
		self.__conf_DISP_COLOR_MODEL				= self.__setup.get_val('conf_DISP_COLOR_MODEL')
		self.__conf_DISP_COLOR_TEXT					= self.__setup.get_val('conf_DISP_COLOR_TEXT')
		self.__conf_DISP_COLOR_HIGH					= self.__setup.get_val('conf_DISP_COLOR_HIGH')
		self.__conf_DISP_COLOR_ALERT				= self.__setup.get_val('conf_DISP_COLOR_ALERT')
		self.__conf_DISP_COLOR_BACKGROUND			= self.__setup.get_val('conf_DISP_COLOR_BACKGROUND')
		self.__conf_DISP_FONT_SIZE					= self.__setup.get_val('conf_DISP_FONT_SIZE')
		self.__conf_DISP_BAND_TOP					= self.__setup.get_val('conf_DISP_BAND_TOP')
		self.__conf_DISP_HIGHLIGHT_STYLE			= self.__setup.get_val('conf_DISP_HIGHLIGHT_STYLE')
		self.__conf_DISP_FRAME_TIME					= self.__setup.get_val('conf_DISP_FRAME_TIME')
		self.__conf_DISP_SHOW_STATUSBAR				= self.__setup.get_val('conf_DISP_SHOW_STATUSBAR')
		self.__conf_DISP_BACKLIGHT_PIN				= self.__setup.get_val('conf_DISP_BACKLIGHT_PIN')
		self.__conf_DISP_BACKLIGHT_ENABLED			= self.__setup.get_val('conf_DISP_BACKLIGHT_ENABLED')
		self.__conf_MENU_ENABLED					= self.__setup.get_val('conf_MENU_ENABLED')
		self.__conf_DIPLAY_IMAGES_KEEP				= self.__setup.get_val('conf_DIPLAY_IMAGES_KEEP')

		self.__const_DISPLAY_CONTENT_OLD_FILE		= self.__setup.get_val('const_DISPLAY_CONTENT_OLD_FILE')
		self.__const_DISPLAY_LINES_LIMIT			= self.__setup.get_val('const_DISPLAY_LINES_LIMIT')
		self.__const_DISPLAY_STATUSBAR_TOGGLE_SEC	= self.__setup.get_val('const_DISPLAY_STATUSBAR_TOGGLE_SEC')
		self.__const_FONT_PATH						= self.__setup.get_val('const_FONT_PATH')
		self.__const_DISPLAY_CONTENT_PATH			= self.__setup.get_val('const_DISPLAY_CONTENT_PATH')
		self.__const_DISPLAY_IMAGE_EXPORT_FILE		= self.__setup.get_val('const_DISPLAY_IMAGE_EXPORT_FILE')
		self.__const_DISPLAY_IMAGE_KEEP_PATH		= self.__setup.get_val('const_DISPLAY_IMAGE_KEEP_PATH')
		self.__const_TASKS_PATH						= self.__setup.get_val('const_TASKS_PATH')

		#define colors
		color = {}
		color['blue']		= (0,	0,		255)
		color['green']		= (0,	255,	0)
		color['red']		= (255,	0,		0)
		color['yellow']		= (255,	255,	0)
		color['orange']		= (255,	94,		14)
		color['white']		= (255,	255,	255)
		color['black']		= (0,	0,		0)
		color['lightgrey']	= (127,	127,	127)
		color['grey']		= (70,	70,		70)

		if self.__conf_DISP_COLOR_MODEL == '1':
			self.color_text = 255
			self.color_high = 255
			self.color_alert = 255
			self.color_bg = 0
		else:
			self.color_text 	= color[self.__conf_DISP_COLOR_TEXT]
			self.color_high 	= color[self.__conf_DISP_COLOR_HIGH]
			self.color_alert 	= color[self.__conf_DISP_COLOR_ALERT]
			self.color_bg 		= color[self.__conf_DISP_COLOR_BACKGROUND]

			if self.__conf_DISP_COLOR_MODEL == 'RGBA':
				# add alpha-channel
				self.color_text		= (*self.color_text, 255)
				self.color_high		= (*self.color_high, 255)
				self.color_alert	= (*self.color_alert, 255)
				self.color_bg		= (*self.color_bg, 255)

		self.__init_hardware()

		# define font
		self.FONT = ImageFont.truetype(self.__const_FONT_PATH, self.__conf_DISP_FONT_SIZE)

		# calculate line dimensions
		self.calculate_LineSize()

		# create folders
		## ensure const_DISPLAY_CONTENT_PATH exists
		if not os.path.isdir(self.__const_DISPLAY_CONTENT_PATH):
			pathlib.Path(self.__const_DISPLAY_CONTENT_PATH).mkdir(parents=True, exist_ok=True)

		if self.__conf_DIPLAY_IMAGES_KEEP:
			## ensure const_DISPLAY_IMAGE_KEEP_PATH exists
			if not os.path.isdir(self.__const_DISPLAY_IMAGE_KEEP_PATH):
				pathlib.Path(self.__const_DISPLAY_IMAGE_KEEP_PATH).mkdir(parents=True, exist_ok=True)

			## create SessionID by subfolders of const_DISPLAY_IMAGE_KEEP_PATH
			self.SessionID = sum(
				os.path.isdir(os.path.join(self.__const_DISPLAY_IMAGE_KEEP_PATH, Finding))
				for Finding in os.listdir(self.__const_DISPLAY_IMAGE_KEEP_PATH)
			) + 1

			## ensure const_DISPLAY_IMAGE_KEEP_PATH/SessionID exists
			if not os.path.isdir(os.path.join(self.__const_DISPLAY_IMAGE_KEEP_PATH, str(self.SessionID))):
				pathlib.Path(self.__const_DISPLAY_IMAGE_KEEP_PATH, str(self.SessionID)).mkdir(parents=True, exist_ok=True)
		else:
			self.SessionID	= 0

		## start display menu
		self.menu_controller	= displaymenu.MENU_CONTROLLER()

		if self.__conf_MENU_ENABLED:
			# start displaymenu as iternal background process
			try:
				thread	= threading.Thread(target=displaymenu.menu, args=(self.maxLines -1 if self.__conf_DISP_SHOW_STATUSBAR else self.maxLines, self.__setup, self.menu_controller))
				thread.start()
			except:
				pass

	def __init_hardware(self):
		# fork: also called again from main() while the panel does not answer, e.g. I2C not ready right after boot
		self.hardware_ready	= True

		serial	= None
		try:
			if self.__conf_DISP_CONNECTION == 'I2C':
				serial = i2c(port=1, address=self.__conf_DISP_I2C_ADDRESS)
			elif self.__conf_DISP_CONNECTION == 'SPI':
				if self.__conf_DISP_DRIVER == 'ST7735':
					serial = spi(port=self.__conf_DISP_SPI_PORT, device=0, bus_speed_hz=40000000)
				elif self.__conf_DISP_DRIVER == 'ST7735 WAVESHARE LCD display HAT':
					serial = spi(port=self.__conf_DISP_SPI_PORT, device=0, bus_speed_hz=40000000, gpio_DC=25, gpio_RST=27)
				else:
					serial = spi(port=self.__conf_DISP_SPI_PORT, device=0)
			else:
				print('Error: No valid connection type for display',file=sys.stderr)
				if self.__conf_DISP_DRIVER != 'none':
					raise Exception('Error: No valid connection type for display')
		except Exception as e:
			self.hardware_ready	= False
			self.__log.message(f'Display connection to {self.__conf_DISP_CONNECTION} could not be enabled. ({e})')

		try:
			if self.__conf_DISP_DRIVER == 'none' or serial is None:
				self.device	= self.__display_dummy()
				self.hardware_ready	= False
			elif self.__conf_DISP_DRIVER == 'SSD1306':
				self.device	= ssd1306(serial_interface=serial, h_offset=self.__conf_DISP_OFFSET_X, v_offset=self.__conf_DISP_OFFSET_Y)
			elif self.__conf_DISP_DRIVER == 'SSD1309':
				self.device	= ssd1309(serial_interface=serial, h_offset=self.__conf_DISP_OFFSET_X, v_offset=self.__conf_DISP_OFFSET_Y)
			elif self.__conf_DISP_DRIVER == 'SSD1322':
				self.device	= ssd1322(serial_interface=serial, h_offset=self.__conf_DISP_OFFSET_X, v_offset=self.__conf_DISP_OFFSET_Y)
			elif self.__conf_DISP_DRIVER == 'SSD1331':
				self.device	= ssd1331(serial_interface=serial, h_offset=self.__conf_DISP_OFFSET_X, v_offset=self.__conf_DISP_OFFSET_Y)
			elif self.__conf_DISP_DRIVER == 'SH1106':
				self.device	= sh1106(serial_interface=serial, h_offset=self.__conf_DISP_OFFSET_X, v_offset=self.__conf_DISP_OFFSET_Y)
			elif self.__conf_DISP_DRIVER == 'ST7735':
				self.device	= st7735(serial_interface=serial, h_offset=self.__conf_DISP_OFFSET_X, v_offset=self.__conf_DISP_OFFSET_Y, gpio_LIGHT=(self.__conf_DISP_BACKLIGHT_PIN if self.__conf_DISP_BACKLIGHT_PIN > 0 else 18), bgr=self.__conf_DISP_COLOR_BGR, inverse=self.__conf_DISP_COLOR_INVERSE) # pin: GPIO Backlight
				self.device.backlight(self.__conf_DISP_BACKLIGHT_ENABLED)
			elif self.__conf_DISP_DRIVER == 'ST7735 WAVESHARE LCD display HAT':
				self.device	= st7735(serial_interface=serial, h_offset=self.__conf_DISP_OFFSET_X, v_offset=self.__conf_DISP_OFFSET_Y, gpio_LIGHT=(self.__conf_DISP_BACKLIGHT_PIN if self.__conf_DISP_BACKLIGHT_PIN > 0 else 18), bgr=self.__conf_DISP_COLOR_BGR, inverse=self.__conf_DISP_COLOR_INVERSE) # pin: GPIO Backlight
				self.device.backlight(self.__conf_DISP_BACKLIGHT_ENABLED)
			else:
				print('Error: No valid display driver', file=sys.stderr)
		except Exception as e:
			self.hardware_ready	= False
			self.device			= self.__display_dummy() # keeps running (web mirror, retry) when the panel does not answer
			self.__log.message(f'Display driver {self.__conf_DISP_DRIVER} could not be enabled. ({e})')

		if self.hardware_ready:
			self.device.capabilities(width=self.__conf_DISP_RESOLUTION_X, height=self.__conf_DISP_RESOLUTION_Y, rotate=self.__conf_DISP_ROTATE, mode=self.__conf_DISP_COLOR_MODEL)

			self.device.contrast(self.__conf_DISP_CONTRAST)

			self.device.persist	= False

		self.hardware_init_time	= time.time()

	def calculate_LineSize(self):
		# calculate size of text

		# create image and draw onject
		image	= Image.new(self.device.mode, (self.device.width, self.device.height), self.color_bg)
		draw	= ImageDraw.Draw(image)

		# write test text "gG"
		(left, top, right, bottom) = draw.textbbox((0,0),"gG",font=self.FONT)

		self.line_height = bottom - top

		# fork: two-color panels get the first line inside the top band and the others below it, so no line crosses the color border
		self.band_top	= self.__conf_DISP_BAND_TOP if self.line_height <= self.__conf_DISP_BAND_TOP <= self.device.height - self.line_height else 0

		if self.band_top:
			self.maxLines = 1 + int((self.device.height - self.band_top) / self.line_height)
		else:
			self.maxLines = int(self.device.height / self.line_height)

		if self.maxLines > self.__const_DISPLAY_LINES_LIMIT:
			self.maxLines = self.__const_DISPLAY_LINES_LIMIT

	def get_statusbar(self):
		# fork: only what needs attention, otherwise no statusbar line at all
		if not self.__conf_DISP_SHOW_STATUSBAR:
			return(None)

		# tasks running in the background
		try:
			TaskFilesList	= [TaskFile for TaskFile in os.listdir(self.__const_TASKS_PATH) if TaskFile.endswith('.txt')]
		except:
			TaskFilesList	= []

		Tasks	= []
		for TaskFile in TaskFilesList:
			try:
				with open(os.path.join(self.__const_TASKS_PATH, TaskFile)) as f:
					Tasks.append(f.readline().strip())
			except:
				continue

		if Tasks:
			return(['|'.join(Tasks)])

		statusbar	= []

		# hotspot active: connect to it
		if lib_comitup.comitup().get_status()['state'] == 'HOTSPOT':
			statusbar.append('HOT')

		# temperature, from 70 °C on
		try:
			temp_c	= float(subprocess.check_output(['/usr/bin/cat', '/sys/class/thermal/thermal_zone0/temp']).decode()) / 1000
			if temp_c >= 70:
				statusbar.append(f'{temp_c:.0f}°C')
		except:
			pass

		return(statusbar if statusbar else None)

	def show(self, Lines, statusbar=None, new_content=True):
		# fill line count to const_DISPLAY_LINES_LIMIT
		while len(Lines) < self.__const_DISPLAY_LINES_LIMIT:
			Lines.append("s=b:")

		if ":IMAGE=" in Lines[0]:
			# PRINT IMAGE FROM FILE
			# Only the first line can be interpreted as image. In This case no further text will be printed.
			# FORMAT: "IMAGE=filename"

			Formatstring, Content = Lines[0].split(':',1)

			ImageLine = Content.split("=",1)
			ImageFilename = ImageLine[1]

			try:
				image = Image.open(ImageFilename).convert(self.device.mode).resize((self.device.width, self.device.height))
			except:
				return()

			# display image
			self.__display_image(image)

			# save image to file
			self.__save_image(image=image, new_content=new_content)

		else:
			# Write lines

			if statusbar is not None:
				Lines[self.maxLines-1] = f's=s:STATUSBAR'

			# create image and draw onject
			image	= Image.new(self.device.mode, (self.device.width, self.device.height), self.color_bg)
			draw	= ImageDraw.Draw(image)

			x = 0
			y_shift = 0

			y_space = 0
			if self.maxLines > 1:
				Spare_Y = self.device.height - self.maxLines * self.line_height
				y_space = int(Spare_Y / (self.maxLines - 1))

			# draw background
			draw.rectangle((0, 0, self.device.width, self.device.height), outline=self.color_bg, fill=self.color_bg)

			for n in range(0, self.maxLines):
				Line = Lines[n]

				# basic color settings
				fg_fill = self.color_text
				bg_fill = self.color_bg

				# basic text decoration settings
				underline = False
				frame = False

				Formatstring, Content = Line.split(':',1)
				Formats = Formatstring.split(',')

				for Format in Formats:
					if '=' in Format:
						FormatType, FormatValue = Format.split('=',1)
					else:
						FormatType	= Format
						FormatValue	= ''

					if FormatType == 's':
						if self.device.mode == '1':
							# monochrome
							# fork: highlight style is a setting, lit bars wear OLED panels and reveal burn-in
							if FormatValue == 'h': # highlight
								if self.__conf_DISP_HIGHLIGHT_STYLE == 'frame':
									frame = True
								elif self.__conf_DISP_HIGHLIGHT_STYLE == 'underline':
									underline = True
								elif self.__conf_DISP_HIGHLIGHT_STYLE != 'plain':
									fg_fill = self.color_bg
									bg_fill = self.color_text
							elif FormatValue == 'a': # alert
								underline = True
							elif FormatValue == 's' and self.__conf_DISP_HIGHLIGHT_STYLE in ['', 'bar']: # statusbar
								fg_fill = self.color_bg
								bg_fill = self.color_text
						else:
							# RGB(A)
							if FormatValue in ['h', 'hc']: # highlight or highlight color
								fg_fill = self.color_high
							elif FormatValue == 'a': # alert
								if self.color_alert not in [self.color_text, self.color_high]:
									fg_fill = self.color_alert
								elif self.color_alert != self.color_high:
									fg_fill = self.color_alert
									bg_fill = self.color_high
								else:
									underline = True
							elif FormatValue == 's': # statusbar
								fg_fill = self.color_bg
								bg_fill = self.color_text

					if FormatType == 'u':
						underline = True

				if self.band_top:
					Spare_Y_band	= self.device.height - self.band_top - (self.maxLines - 1) * self.line_height
					y	= int((self.band_top - self.line_height) / 2) - 1 if n == 0 else self.band_top + (n - 1) * self.line_height - 1 + int(Spare_Y_band / 2)
				else:
					y	= (n) * self.line_height + y_shift - 1 + y_space

				# Draw a filled box in case of inverted output
				if bg_fill != self.color_bg:
					draw.rectangle(
						(x, y + 2, self.device.width, min(y + self.line_height + 1, self.device.height)),
						outline=bg_fill, fill=bg_fill)

				if frame:
					draw.rectangle(
						(x, y + 2, self.device.width - 1, min(y + self.line_height + 1, self.device.height - 1)),
						outline=self.color_text, fill=self.color_bg)

				if Content.startswith("IMAGE="):
					Content	= ''

				if Content.startswith("PGBAR="):
					try:
						progress	= float(Content[6:])
					except ValueError:
						progress	= 0

					progress	= int(progress * 10 + 0.5) / 10 if progress < 100 else int(progress + 0.5)

					# define text to print
					Content = "{}%".format(str(progress if progress <= 100 else '100+'))

					(left, top, right, bottom) = draw.textbbox((0,0), "100%::", font=self.FONT)
					pgbar_text_length = right - left

					# draw progressbar
					pg_space = 2
					pgbar_x_l = x + pgbar_text_length
					pgbar_x_r = self.device.width - pg_space
					pgbar_y_u = y + pg_space
					pgbar_y_d = y + self.line_height - pg_space

					## draw outer frame
					draw.rectangle((pgbar_x_l, pgbar_y_u, pgbar_x_r, pgbar_y_d), outline=fg_fill, fill=bg_fill)

					## draw inner frame
					pgbar_x_l	+= 1
					pgbar_x_r	-= 1
					pgbar_y_u	+= 1
					pgbar_y_d	-= 1

					pgbar_x_r = pgbar_x_l + (pgbar_x_r - pgbar_x_l) * (100 if progress >= 100 else progress) / 100

					draw.rectangle((pgbar_x_l, pgbar_y_u, pgbar_x_r, pgbar_y_d), outline=bg_fill, fill=fg_fill)

				# Write text
				## status bar
				if FormatType == 's' and FormatValue == 's':

					i	= 0
					for item in statusbar:

						if (i < len(statusbar) - 1) or (i == 0):
							# left bound
							x	= int(i * self.device.width / len(statusbar))
						else:
							# right bound
							(left, top, right, bottom) = draw.textbbox((0,0), item, font=self.FONT)
							pgbar_text_length = right - left
							x	= self.device.width - pgbar_text_length - 1

						draw.text((x + 1, y), item, font=self.FONT, fill=fg_fill)

						i += 1
				else:
					## regular text
					draw.text((x + (3 if frame else 1), y), Content, font=self.FONT, fill=fg_fill)

				if underline:
					(left, top, right, bottom) = draw.textbbox((0, 0), Content, font=self.FONT)
					draw.line(
						(x + 1, y + self.line_height + y_space, x + 1 + right - left, y + self.line_height + y_space),
						fill=fg_fill, width=1)

			# display image
			self.__display_image(image)

			# save image to file
			self.__save_image(image=image, new_content=new_content)

	def __display_image(self, image):
		if self.hardware_ready:
			self.device.show() # re-enable panel, an exiting display.py switches it off via luma cleanup
			self.device.display(image)

	def __save_image(self, image, new_content=True):

		### <<< KEEP IMAGES FOR DOCUMENTATION
		if self.__conf_DIPLAY_IMAGES_KEEP and new_content:
			if os.path.exists(self.__const_DISPLAY_IMAGE_EXPORT_FILE):
				uptime_seconds	= f'{lib_system.get_uptime_sec():0>12.2f}'

				FileNameTimed	= f'{uptime_seconds}-{os.path.basename(self.__const_DISPLAY_IMAGE_EXPORT_FILE)}'
				try:
					os.rename(self.__const_DISPLAY_IMAGE_EXPORT_FILE, os.path.join(self.__const_DISPLAY_IMAGE_KEEP_PATH, str(self.SessionID), FileNameTimed))
				except:
					pass
		### >>> KEEP IMAGES FOR DOCUMENTATION

		try:
			image.save(self.__const_DISPLAY_IMAGE_EXPORT_FILE)
		except:
			pass


	def terminate(self, signum=None, frame=None):
		# stop menu
		self.menu_controller.terminate()
		time.sleep(1) # wait until menu is stopped

		# exit function
		self.loop_continue	= False

		print('display.py process killed.')

	def main(self):
		display_time	= time.time()
		Lines 			= []

		# start endless loop to display content
		while(self.loop_continue):
			# fork: the panel did not answer: try again every 30 s and redraw the current screen once it does
			if not self.hardware_ready and self.__conf_DISP_DRIVER != 'none' and time.time() - self.hardware_init_time >= 30:
				self.__init_hardware()
				if self.hardware_ready:
					self.__log.message('Display answers again.')
					self.calculate_LineSize()
					if Lines:
						self.show(Lines=Lines, statusbar=self.get_statusbar(), new_content=False)

			import_old_file 		= False # fork: one message per screen, no older lines pushed below
			temp_screen				= False
			hidden_info				= ''

			# re-check for new files earlier than conf_DISP_FRAME_TIME, if no message was found
			FrameTime = self.__conf_DISP_FRAME_TIME / 4

			ContentFile	= self.__display_content_files.get_next_file_name()

			if ContentFile:

				if not os.path.isfile(ContentFile):
					continue

				# file could be in writing process, wait for minimal file age
				if time.time() - os.stat(ContentFile).st_mtime < 0.2:
					time.sleep(0.2)

				Lines = []
				FrameTime = self.__conf_DISP_FRAME_TIME

				# read content file
				try:
					CF	= open(ContentFile, 'r')
				except:
					continue

				for Line in CF:

					Line = Line.strip()

					# skip empty lines
					if not Line:
						continue

					if Line[0:4] == 'set:': # global settings line

						settingStr = Line[4:]
						settings = settingStr.split(',')

						for setting in settings:

							if '=' in setting:
								SettingType, SettingValue = setting.split('=',1)
								SettingValue	= SettingValue.strip()
							else:
								SettingType	= setting
								SettingValue	= ''

							if SettingType == 'kill':
								# remove content file
								os.remove(ContentFile)

								self.terminate()
								return()

							if SettingType == 'clear':
								import_old_file	= False

							if SettingType == 'temp':
								temp_screen		= True

							if SettingType == 'hidden':
								hidden_info		= SettingValue

							if SettingType == 'time' and float(SettingValue) >= 0:
								FrameTime		= float(SettingValue)

					elif len (Lines) < self.__const_DISPLAY_LINES_LIMIT: # content line

						if (Line[0:1] == ':'):
								Line = "s=h{}".format(Line)
						elif ":" not in Line:
							Line = "s=h:{}".format(Line)

						Lines.append(Line)

				CF.close()

				# read old lines
				if import_old_file:
					if len(Lines) < self.__const_DISPLAY_LINES_LIMIT and os.path.isfile(self.__const_DISPLAY_CONTENT_OLD_FILE):
						with open(self.__const_DISPLAY_CONTENT_OLD_FILE, 'r') as oCF:
							for Line in oCF:

								Line = Line.strip()

								if len(Lines) < self.__const_DISPLAY_LINES_LIMIT:
									Line = Line.split(':',1)[-1]
									if Line:
										if not Line.startswith('set:'):
											Line = "s=b:{}".format(Line)
											Lines.append(Line)

			else:
				# no new content file:
				# reload last displayed content if Lines is empty
				if not Lines and os.path.isfile(self.__const_DISPLAY_CONTENT_OLD_FILE):

					with open(self.__const_DISPLAY_CONTENT_OLD_FILE, 'r') as oCF:
						for Line in oCF:

							Line = Line.strip()

							if not Line or Line.startswith('set:'):
								continue

							Lines.append(Line)

			# absolute fallback against empty screens
			if not Lines:
				Lines = ["s=b:"]

			if ContentFile:
				# remove content file
				try:
					os.remove(ContentFile)
				except:
					pass

				# display temp only:
				if temp_screen and os.path.isfile(self.__const_DISPLAY_CONTENT_OLD_FILE):
					shutil.copyfile(self.__const_DISPLAY_CONTENT_OLD_FILE, f'{ContentFile}')

					if hidden_info:
						with open(ContentFile, 'a') as newCF:
							newCF.write(f"\nset:hidden={hidden_info}")

				# move lines to old lines file
				if not temp_screen:
					with open(self.__const_DISPLAY_CONTENT_OLD_FILE, 'w') as oCF:
						oCF.write("\n".join(Lines))

						if hidden_info:
							oCF.write(f"\nset:hidden={hidden_info}")

				self.show(Lines=Lines, statusbar=self.get_statusbar(), new_content=True)
				display_time	= time.time()
			else:
				# statusbar
				if (
					self.__conf_DISP_SHOW_STATUSBAR and
					time.time() - display_time >= self.__const_DISPLAY_STATUSBAR_TOGGLE_SEC
					):
					self.show(Lines=Lines, statusbar=self.get_statusbar(), new_content=False)
					display_time	= time.time()

			time.sleep(FrameTime)

	class __display_dummy(object):

		def __init__(self):
			self.persist = False
			self.width	= 128
			self.height	= 64
			self.mode	= 'RGB'

		def capabilities(self, *args, **kwargs):
			return()

		def contrast(self, *args, **kwargs):
			return()

		def display(self, *args, **kwargs):
			return()

if __name__ == "__main__":
	# fork: only one display.py may drive the panel. lib_display starts it after a pgrep check that is not atomic,
	# so two could start together and interleave their frames on the bus. Take the lock before touching the panel.
	import fcntl
	pathlib.Path(WORKING_DIR, 'tmp').mkdir(parents=True, exist_ok=True)
	lock_file	= open(os.path.join(WORKING_DIR, 'tmp', 'display.lock'), 'w')
	for attempt in range(20): # a restarting display.py may still be shutting down
		try:
			fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
			break
		except BlockingIOError:
			time.sleep(0.5)
	else:
		sys.exit() # another display.py drives the panel

	# fork: 'sudo pkill -USR1 -f display.py' writes where every thread is right now into tmp/display-stack.txt
	import faulthandler
	faulthandler.register(signal.SIGUSR1, file=open(os.path.join(WORKING_DIR, 'tmp', 'display-stack.txt'), 'w'), all_threads=True)

	# fork: a crash used to vanish, the display just went dark. Put the traceback into the Little Backup Box log.
	try:
		display	= DISPLAY()
		display.main()
	except Exception:
		import traceback
		lib_log.log().message(f'display.py crashed:\n{traceback.format_exc()}')
		raise

	sys.exit()

