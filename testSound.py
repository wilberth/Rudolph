#!/usr/bin/python

import sys
from PyQt4 import QtGui, QtCore
from PyQt4.phonon import Phonon

"""make a sound """
	
class Window(QtGui.QPushButton):
	def __init__(self):
		QtGui.QPushButton.__init__(self, 'Play')
		self.clicked.connect(self.play)
		# make a MediaSource for this sound
		self.mediaObject = Phonon.MediaObject()
		self.audioOutput = Phonon.AudioOutput(Phonon.MusicCategory)
		Phonon.createPath(self.mediaObject, self.audioOutput)
		self.mediaSource = Phonon.MediaSource("sound/sound.wav")
		
	def play(self, event):
		if self.mediaObject.state() == Phonon.PlayingState:
			print("stop")
			self.mediaObject.stop()
		else:
			print("play")
			self.mediaObject.setCurrentSource(self.mediaSource)
			self.mediaObject.play()
	
if __name__ == '__main__':
	app = QtGui.QApplication(sys.argv)
	app.setApplicationName('Phonon')
	win = Window()
	win.resize(200, 100)
	win.show()
	sys.exit(app.exec_())