#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Copyright © 2013, W. van Ham, Radboud University Nijmegen
This file is part of Sleelab.

Sleelab is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Sleelab is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Sleelab.  If not, see <http://www.gnu.org/licenses/>.
'''

from __future__ import print_function
import logging, signal, numpy as np
import OpenGL
OpenGL.ERROR_ON_COPY = True   # make sure we do not accidentally send other structures than numpy arrays
# PyQt (package python-qt4-gl on Ubuntu)
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import * 

# project files
from testField import *
import utils

class Main(QMainWindow):
	def __init__(self):
		super(Main, self).__init__()
		self.initUI()

	def initUI(self):
		#contents
		self.field = Field(self)
		self.setCentralWidget(self.field)

		exitAction = QAction(QIcon('icon/quit.png'), '&Exit', self)
		exitAction.setShortcut('Ctrl+Q')
		exitAction.setStatusTip('Quit application')
		exitAction.triggered.connect(qApp.quit)
		
		self.fullIcon = QIcon('icon/full.png')
		self.fullAction = QAction(self.fullIcon, '&Full Screen', self)
		self.fullAction.setShortcut('ctrl+F')
		self.fullAction.setStatusTip('Toggle Full Screen')
		self.fullAction.triggered.connect(self.toggleFullScreen)

		# populate the menu bar
		menubar = self.menuBar()
		fileMenu = menubar.addMenu('&File')
		fileMenu.addAction(exitAction)

		viewMenu = menubar.addMenu('&View')
		viewMenu.addAction(self.fullAction)
		self.addAction(self.fullAction)
		
		self.addAction(exitAction)

		self.statusBar().showMessage('Ready')
		self.setWindowTitle('testImage')
		self.show()

	def toggleFullScreen(self, event=None):
		if(self.isFullScreen()):
			self.showNormal()
			self.menuBar().setVisible(True)
			self.statusBar().setVisible(True)
			self.setCursor(QCursor(Qt.ArrowCursor))
		else:
			self.showFullScreen()
			self.menuBar().setVisible(False)
			self.statusBar().setVisible(False)
			#self.setCursor(QCursor(Qt.BlankCursor))

def main(): 
	# make application and main window
	a = QApplication(sys.argv)
	w = Main()
	a.lastWindowClosed.connect(a.quit) # make upper right cross work
	# main loop
	sys.exit(a.exec_())  # enter main loop (the underscore prevents using the keyword)

if __name__ == '__main__':
	logging.basicConfig(level=logging.DEBUG)
	main()   

