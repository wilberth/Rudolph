#!/usr/bin/python
from __future__ import print_function
from PyQt4.QtCore import *
from PyQt4.QtGui import *

import logging, time, sys, os
import pygame

class HideStdout(object):
	'''A context manager that block stdout for its scope, usage:

	with HideStdout():
		os.system('ls -l')
	'''

	def __init__(self, *args, **kw):
		sys.stdout.flush()
		self._origstdout = sys.stdout
		self._oldstdout_fno = os.dup(sys.stdout.fileno())
		self._devnull = os.open(os.devnull, os.O_WRONLY)

	def __enter__(self):
		self._newstdout = os.dup(1)
		os.dup2(self._devnull, 1)
		os.close(self._devnull)
		sys.stdout = os.fdopen(self._newstdout, 'w')

	def __exit__(self, exc_type, exc_val, exc_tb):
		sys.stdout = self._origstdout
		sys.stdout.flush()
		os.dup2(self._oldstdout_fno, 1)

class QTriggerJoystick(QObject):
	up   = pyqtSignal()
	down = pyqtSignal()
	def __init__(self, parent, thresshold=0.1):
		super(QObject, self).__init__(parent)
		self.thresshold = thresshold
		pygame.init()
		pygame.joystick.init()
		if pygame.joystick.get_count():
			self.j = pygame.joystick.Joystick(0)
			self.j.init()
			
			logging.info("QTriggerJoystick: {}".format(self.j.get_name()))
			if self.j.get_numaxes():
				self.val = 0
				self.startTimer(100)
			else:
				logging.error("QTriggerJoystick: Joystick has no axis.")
		else:
			logging.error("QTriggerJoystick: No joystick connected")

	def timerEvent(self, event):
		if not self.j.get_init():
			return
		keys = pygame.event.get()
		with HideStdout():
			val =  self.j.get_axis(0)
		if val > self.thresshold and self.val <= self.thresshold:
			self.up.emit()
		elif val < -self.thresshold and self.val >= -self.thresshold:
			self.down.emit()
		self.val = val
		
def printUp():
	print("Up")
def printDown():
	print("Down")

if __name__ == '__main__':
	# set logging
	logging.basicConfig(level=logging.DEBUG)

	# make Qt app
	a = QApplication(sys.argv)
	a.setApplicationName("Joystick test")
	w = QMainWindow()
	w.show()
	
	# joystick example code
	j = QTriggerJoystick(w)
	j.up.connect(printUp)
	j.down.connect(printDown)
	
	# main loop
	sys.exit(a.exec_())  # enter main loop (the underscore prevents using the keyword)
