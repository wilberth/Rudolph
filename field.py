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
import sys, math, time, numpy as np, random, serial, ctypes, re
import fpclient, sledclient, sledclientsimulator, root, transforms, shader, conditions#, qtriggerjoystick
from rusocsci import buttonbox

#PyQt
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import *
from PyQt4.phonon import Phonon
#openGL
import OpenGL
OpenGL.ERROR_ON_COPY = True   # make sure we do not accidentally send other structures than numpy arrays
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from OpenGL.arrays import vbo
from OpenGL.GL.shaders import *
from OpenGL.GL.ARB import *

 
 # Coordinate system:
 # The center of the screen is the origin of the model coordinate system.
 # Dimensions are in coherent international units (m, s, m/s, ...).
 # The viewer sits at pViewer. pViewer[2] (the distance to the screen)
 # must not change during the experiment. It is always positive.
 # The x-direction is to the right of the viewer, the y-direction is up.
 # Hence the coordinate system  is right handed.
 # dScreen is the dimension of the screen in m. If the height-width 
 # ratio of the screen is different from the height-width ratio (in 
 # pixels) of the window, then this program will assume that the pixels 
 # are not square.
 # Objects are only drawn if they are between zNear and zFar

	

# field widget
class Field(QGLWidget):
	# space
	pViewer = np.array([0, 0, 1.2])         # m, x,y,z-position of the viewer
	zNear   = 0.5*pViewer[2]                # m  viewable point nearest to viewer, now exp. var
	zFocal  = 0                             # m, position of physical screen, better not change this
	zFar    = -0.5*pViewer[2]               # m, viewable point furthest from viewer, now exp. var
	dEyes   = 0.063                         # m, distance between the eyes, now exp. var
	dScreen = np.array([2.728, 1.02])       # m, size of the screen
	#halfWidthAtNearPlane = .5*dScreen[0] * ( pViewer[2]-zNear ) / ( pViewer[2]-zFocal) 
	#halfHeightAtNearPlane = .5*dScreen[1] * ( pViewer[2]-zNear ) / ( pViewer[2]-zFocal) 
	tMovement = 1.5                         # Movement time reference and comparison movement, in seconds
	tHoming = 2.0                           # Movement time homing movement, in seconds
	
	
	def __init__(self, parent):
		#QGLWidget.__init__(self, parent)
		super(Field, self).__init__(parent)
		self.setMinimumSize(1400, 525)
		
		# GL settings
		fmt = self.format()
		fmt.setDoubleBuffer(True)    # always double buffers anyway (watch nVidia setting, do not do it there also n 120 Hz mode)
		fmt.setSampleBuffers(True)
		fmt.setSwapInterval(1)       # 0: no sync to v-refresh, number of syncs to wait for
		self.setFormat(fmt)          # PyQt
		if self.format().swapInterval()==-1:
			qWarning("Setting swapinterval not possible, expect synching problems");
		if not self.format().doubleBuffer():
			qWarning("Could not get double buffer; results will be suboptimal");
		self.extrapolationTime = 0
		self.fadeFactor = 1.0         # no fade, fully exposed
		self.state = "sleep"
		self.requestSleep = False
		self.lifetime = 60
		
		# audio
		self.mediaObject = Phonon.MediaObject(self)
		self.audioOutput = Phonon.AudioOutput(Phonon.MusicCategory, self)
		Phonon.createPath(self.mediaObject, self.audioOutput)
		self.mediaSourceBeep = Phonon.MediaSource("sound\sound2.wav")
		self.mediaSourceNoise = Phonon.MediaSource("sound\wgn.wav")
		self.mediaObject.setCurrentSource(self.mediaSourceNoise)
##		self.mediaObject.play()		
##		self.homingText = pyttsx.init()
##		self.homingText.say('Homing.')
		#self.beep = pyglet.resource.media('sound\beep-5.wav')
		self.moveString = "Reference"
		
		# shutter glasses
		try:
			self.shutter = buttonbox.Buttonbox() # optionally add port="COM17"
			self.openShutter(False, False)
		except Exception as e:
			print(e)
						
		# experimental conditions
		self.conditions = conditions.Conditions(dataKeys=['swapMoves', 'subject'])

	def __del__(self):
		self.quit()

	def soundBeep(self):
		logging.info("Start playing beep")
		#self.mediaObject.stop() # Stop continuous white noise to play beep
		self.mediaObject.setCurrentSource(self.mediaSourceBeep)
		self.mediaObject.play()
		
	def soundNoise(self):
		logging.info("Start playing white noise")
		self.mediaObject.stop() # Stop beep (if still playing)
		self.mediaObject.setCurrentSource(self.mediaSourceNoise)
		self.mediaObject.play()
		
	def quit(self):
		if hasattr(self, "sledClient") and hasattr(self.sledClient, "stopStream"):
			print("closing sled client") # logger may not exist anymore
			self.sledClient.stopStream()
		if hasattr(self, "positionClient") and hasattr(self.positionClient, "stopStream"):
			print("closing FP client") # logger may not exist anymore
			self.positionClient.stopStream()
			

	def changeState(self):
		""" states: (sleep), fadeIn, referenceMove, trialMove, wait, fadeOut, home
		state chages are triggered by keys or timers. States always heave the same order.
		The sleep state is optional and only occurs if self.requestSleep is true when moving
		out of the home state."""
		if self.state=="home" and self.requestSleep==True:
			self.state = "sleep"
			self.requestSleep = False
			self.parent().toggleText(True)
			self.sledClient.sendCommand("Lights On")
		elif self.state=="sleep" or self.state=="home":
			self.sledClient.sendCommand("Lights Off")
			self.state = "fadeIn"
			self.swapMoves = np.random.uniform()>0.5
			if self.swapMoves:
				self.moveString = "Trial"
			else:
				self.moveString = "Reference"
			self.initializeObjects(self.moveString)
			self.d = self.conditions.trial["d"+self.moveString]
			logging.info("state: fadeIn")
			QTimer.singleShot(350+300, self.changeState) # 350ms for fade in and 300ms to get used to 3D scene
		elif self.state=="fadeIn":
			self.state = "move0Prep" # Additional step to allow for singleshot timer start-noise
			self.soundNoise()
			print("Sled position: ",self.pViewer[0])
			QTimer.singleShot(500, self.changeState)
		elif self.state=="move0Prep":
			self.state = "move0"
			dt = self.sledClientSimulator.goto(self.h+self.d, self.tMovement)
			if self.conditions.trial["mode"+self.moveString] != "visual":
				dt = self.sledClient.goto(self.h+self.d, self.tMovement)
			logging.info("state: move0 ({}): d = {} m, dt = {} s".format(self.moveString, self.d, dt))
			QTimer.singleShot(1000*dt, self.changeState) 
		elif self.state=="move0":
			self.state="move1ReInit"
			if self.swapMoves:
				self.moveString = "Reference"
			else:
				self.moveString = "Trial"
			self.initializeObjects(self.moveString)
			print("Sled position: ",self.pViewer[0])
			QTimer.singleShot(500, self.changeState) # 500ms: The extra milliseconds is to prevent the sled server to overwrite the movement file on the PLC unit while movement is being executed. Furthermore, it prevents perceptual overlap between the comparison and reference (or vice versa) movements.
		elif self.state=="move1ReInit":
			self.state = "move1"
			d = self.conditions.trial["d"+self.moveString]
			ddVes=0 # vestibular reference + trial move
			if self.conditions.trial["modeReference"] != 'visual':
				ddVes +=self.conditions.trial['dReference']
			if self.conditions.trial["modeTrial"] != 'visual':
				ddVes +=self.conditions.trial['dTrial']
			ddAll = self.conditions.trial['dReference']+self.conditions.trial['dTrial']
			dt = self.sledClientSimulator.goto(self.h+ddAll, self.tMovement)
			#if self.conditions.trial["mode"+self.moveString] != "visual":
			dt = self.sledClient.goto(self.h+ddVes, self.tMovement)
			logging.info("state: move1 ({}): d = {} m, dt = {} s".format(self.moveString, d, dt))
			QTimer.singleShot(1000*dt+np.random.uniform(0.1, 0.3), self.changeState) #Wait random time between 100 and 300ms before playing response beep. This to avoid the beep being a motion-stop cue

		elif self.state=="move1":
			self.state="responseBeep"
			logging.info("state: wait (for input)")
			self.soundBeep()
			QTimer.singleShot(350, self.changeState)        # extra timer to make sure that fade out is complete
		elif self.state=="responseBeep":
			self.state="wait"
			self.parent().downAction.setEnabled(True)
			self.parent().upAction.setEnabled(True)
			#self.parent().j.setEnabled(True)
		elif self.state=="wait":
			self.state = "fadeOut"
			logging.info("state: fadeOut")
			#self.parent().j.setEnabled(False)
			QTimer.singleShot(500, self.changeState)
		elif self.state=="fadeOut":
			self.state = "home"
			logging.info("state: home (homing)")
##			self.homingText.runAndWait()
			self.initializeObjects() # redraw of new random field of stars
			self.h =  -self.conditions.trial['dReference']+np.random.uniform(low=-0.1, high=0.02)
			self.sledClientSimulator.warpto(self.h)	# Homing to -reference position
			dt = self.sledClient.goto(self.h, self.tHoming)	# Homing to -reference position
			logging.info("state: homing: d = {} m, dt = {} s".format(self.h, dt))
			QTimer.singleShot(1000*(dt), self.changeState)
			self.parent().downAction.setEnabled(False)
			self.parent().upAction.setEnabled(False)
		else:
			logging.warning("state unknown: {}".format(self.state))
			
	def addData(self, data):
		if self.state=="wait":
			self.conditions.trial['subject'] = self.subject # not very useful to store for each trial, but it has to go somewere
			logging.info("received while waiting: {}".format(data))
			if self.swapMoves:
				self.conditions.trial['swapMoves'] = True
				data = not data
			else:
				self.conditions.trial['swapMoves'] = False
			if self.conditions.iTrial < self.conditions.nTrial-1:
				if self.conditions.nextTrial(data = data):
					self.parent().startStop()
			else:
				# last data
				self.conditions.addData(data)
				self.requestSleep = True
			self.changeState()
		else:
			logging.info("ignoring input: {}".format(data))
	
	views = ('ALL',)
	def toggleStereo(self, on, sim=False):
		if on or len(self.views)==1:
			if sim:
				self.views = ('LEFTSIM', 'RIGHTSIM')
			else:
				self.views = ('LEFT', 'RIGHT')
			self.parent().leftAction.setEnabled(True)
			self.parent().rightAction.setEnabled(True)
		else:
			self.views = ('ALL',)
			self.parent().leftAction.setEnabled(False)
			self.parent().rightAction.setEnabled(False)
		self.update()
		
	stereoIntensityLevel = 0 # integer -9 -- 9
	def stereoIntensity(self, level=None, relative=None):
		"""change the relative intensity of the left eye and right eye image"""
		if(level!=None):
			self.stereoIntensityLevel = level
		elif abs(self.stereoIntensityLevel + relative) < 10:
			self.stereoIntensityLevel += relative
		self.parent().statusBar().showMessage("Stereo intensity: {}".format(self.stereoIntensityLevel))
		self.update()
		
	def viewerMove(self, x, y=None):
		""" Move the viewer's position """
		#print("viewermove: ({}, {})".format(x, y))
		self.pViewer[0] = x
		self.pViewer[1] = 0
		if y != None:
			self.pViewer[1] = y
		self.update()
	
	
	def mouseMoveEvent(self, event):
		""" React to a moving mouse right button down in the same way we would react to a moving target. """
		if event.buttons() & Qt.RightButton:
			self.viewerMove(
				self.dScreen[0]*(event.posF().x()/self.size().width()-.5), 
				self.dScreen[1]*(.5-event.posF().y()/self.size().height()) # mouse y-axis is inverted
				)

	def connectSledServer(self, server=None):
		logging.debug("requested sled server: " + str(server))
		self.sledClientSimulator = sledclientsimulator.SledClientSimulator() # for visual only mode
		if not server:
			self.sledClient = sledclientsimulator.SledClientSimulator()
		else:
			self.sledClient = sledclient.SledClient() # derived from FPClient
			self.sledClient.connect(server)
			self.sledClient.startStream()
			time.sleep(2)
		self.h = -self.conditions.trial['dReference']
		self.sledClient.goto(self.h) # homing sled at -reference
		self.sledClientSimulator.warpto(self.h) # homing sled at -reference
	
	def connectPositionServer(self, server=None):
		""" Connect to a First Principles server which returns the viewer position in the first marker position.
		Make sure this function is called after connectSledServer so that the fall back option is present. """
		logging.debug("requested position server: " + str(server))
		if not server:
			self.positionClient = self.sledClient
		elif server=="mouse":
			return
		else:
			self.positionClient = fpclient.FpClient()            # make a new NDI First Principles client
			#self.positionClient.connect(server)                  # connect the client to the First Principles server
			self.positionClient.startStream()                    # start the synchronization stream. 
			time.sleep(2)

	def openShutter(self, left=False, right=False):
		"""open shutter glasses"""
		try:
			self.shutter.setLeds([left, right, False, False, False, False, False, False])
		except:
			pass

	def initializeObjects(self, moveString="Reference"):
		# set uniform variables and set up VBO's for the attribute values
		# reference triangles, do not move in model coordinates
		# position of the center
		self.dEyes = self.conditions.getNumber('dEyes')
		self.zNear = self.conditions.getNumber('zNear')
		self.zFar = self.conditions.getNumber('zFar')

		
		self.nMD  = self.conditions.getNumber('nMD'+moveString)
		self.nMND = self.conditions.getNumber('nMND'+moveString)
		self.nNMD = self.conditions.getNumber('nNMD'+moveString)
		self.nNMND = self.conditions.getNumber('nNMND'+moveString)
		
		if self.nMND+self.nNMND > 0:
			# there are non-disparity objects: close right shutter
			self.openShutter(False, True)
		elif self.conditions.getString("mode"+self.moveString) == 'vestibular':
			# Mode is vestibular only: close both shutters
			self.openShutter(True, True)
		else:
			# there are no non-disparity objects: open both shutters
			self.openShutter(False, False)

		nPast = 0
		n = self.nMD
		#position = np.random.rand(n, 3) * \
		#	[2*self.dScreen[0], 2*self.dScreen[1], self.zNear-self.zFar] - \
		#	[2*self.dScreen[0]/2, 2*self.dScreen[1]/2 , -self.zFar]
		position = np.zeros((n, 3), dtype='float32')
		#randSeed = np.reshape(np.arange(1+3*nPast, 1+3*(nPast+n), dtype="uint32"), (n, 3))
		randSeed = np.array(np.random.randint(0, 0xffff, size=(n,3)), dtype="uint32")
		randSeed.dtype='float32'
		disparityFactor = np.ones((n, 1), dtype='float32')
		size = np.array(np.random.uniform(0.01, 0.02, (n, 1)), dtype='float32')
		#size = 0.015*np.ones((n,1), dtype='float32')
		lifetime = self.lifetime*np.ones((n, 1), dtype='uint32'); lifetime.dtype='float32'

		# each vertex has:
		# 3 dimensions (x, y, z)
		# 3 randSeeds (one for each dimension), these are 0 for non random
		# 1 disparityFactor, this is 1 if disparity is used
		referenceVertices = np.hstack([
			position, 
			randSeed,
			disparityFactor,
			size,
			lifetime,
		])
		
		#******************
		# Noise triangles *
		#******************
		# Types of noise triangles:
		# - Congruent movement, no disparity: MovNonDisp
		# - Random 'movement', with disparity: NonMovDisp
		# - Random movement, no disparity: NonMovNonDisp

		# MovNonDisp:
		#************
		# randSeeds: 0 (Non random movement)
		# disparityFactor: linspace(0,1,nMND) (no disparity)]
		nPast += n
		n = self.nMND
		position = np.zeros((n, 3), dtype='float32')
		#randSeed = np.reshape(np.arange(1+3*nPast, 1+3*(nPast+n), dtype="uint32"), (n, 3))
		randSeed = np.array(np.random.randint(0, 0xffff, size=(n,3)), dtype="uint32")
		randSeed.dtype='float32'
		disparityFactor = np.zeros((position.shape[0], 1), dtype='float32')
		size = np.array(np.random.uniform(0.01, 0.02, (n, 1)), dtype='float32')
		lifetime = self.lifetime*np.ones((n, 1), dtype='uint32'); lifetime.dtype='float32'
		# noise vertices
		movNonDispVertices = np.hstack([
			position, 
			randSeed,
			disparityFactor,
			size,
			lifetime,
		])
		
		# NonMovDisp:
		#************
		# randSeeds: array of predetermined numbers (random movement)
		# disparityFactor: 1 (disparity)		
		nPast += n
		n = self.nNMD
		position = np.zeros((n, 3), dtype='float32')
		#randSeed = np.reshape(np.arange(1+3*nPast, 1+3*(nPast+n), dtype="uint32"), (n, 3))
		randSeed = np.array(np.random.randint(0, 0xffff, size=(n,3)), dtype="uint32")
		randSeed.dtype='float32'
		disparityFactor = np.ones((n, 1), dtype='float32')
		size = np.array(np.random.uniform(0.01, 0.02, (n, 1)), dtype='float32')
		lifetime = np.ones((n, 1), dtype='uint32'); lifetime.dtype='float32'
		nonMovDispVertices = np.hstack([
			position, 
			randSeed,
			disparityFactor,
			size,
			lifetime,
		])
		
		# NonMovNonDisp:
		#***************
		# randSeeds: array of predetermined numbers (random movement)
		# disparityFactor: 0 (no disparity)		
		nPast += n
		n = self.nNMND
		position = np.zeros((n, 3), dtype='float32')
		#randSeed = np.reshape(np.arange(1+3*nPast, 1+3*(nPast+n), dtype="uint32"), (n, 3))
		randSeed = np.array(np.random.randint(0, 0xffff, size=(n,3)), dtype="uint32")
		randSeed.dtype='float32'
		disparityFactor = np.zeros((n, 1), dtype='float32')
		size = np.array(np.random.uniform(0.01, 0.02, (n, 1)), dtype='float32')
		lifetime = np.ones((n, 1), dtype='uint32'); lifetime.dtype='float32'
		nonMovNonDispVertices = np.hstack([
			position, 
			randSeed,
			disparityFactor,
			size,
			lifetime,
		])
		#print(np.shape(nonMovNonDispVertices))
		
		# fixation cross
		nPast += n
		xFixation = 0.0
		if self.conditions.getString("mode"+self.moveString) == 'visual':
			try:
				#xFixation = self.pViewer[0]
				pp = self.positionClient.getPosition()          # get marker positions
				p = np.array(pp).ravel().tolist()       # python has too many types
				xFixation = 2*p[0]
			except:
				pass
			
			
		position = np.array([xFixation, 0, 0], dtype='float32')
		randSeed = np.array([0, 0, 0], dtype='uint32'); randSeed.dtype = 'float32'
		disparityFactor = np.array(1.0, dtype='float32')
		size = np.array(0.02, dtype='float32')
		lifetime = np.array(0, dtype='uint32'); lifetime.dtype='float32'

		fixationCrossVertices = np.hstack([
			position, 
			randSeed,
			disparityFactor,
			size,
			lifetime,
		])

		assert (referenceVertices.dtype=='float32')
		assert (movNonDispVertices.dtype=='float32')
		assert (nonMovDispVertices.dtype=='float32')
		assert (nonMovNonDispVertices.dtype=='float32')
		assert (fixationCrossVertices.dtype=='float32')
		# send the whole array to the video card
		self.vbo = vbo.VBO(
			np.vstack([
				np.array(referenceVertices, "f"), 
				np.array(movNonDispVertices, "f"), 
				np.array(nonMovDispVertices, "f"), 
				np.array(nonMovNonDispVertices, "f"), 
				np.array(fixationCrossVertices, "f")]), 
			usage='GL_STATIC_DRAW')

		# uniforms
		glUniform1f(self.widthLocation, self.dScreen[0])
		glUniform1f(self.heightLocation, self.dScreen[1])
		glUniform1f(self.nearLocation, self.pViewer[2]-self.zNear)
		glUniform1f(self.focalLocation, self.pViewer[2]-self.zFocal)
		glUniform1f(self.farLocation, self.pViewer[2]-self.zFar)

		
	def initializeGL(self):
		glEnable(GL_DEPTH_TEST)          # painters algorithm without this
		glEnable(GL_MULTISAMPLE)         # anti aliasing
		glClearColor(0.0, 0.0, 0.0, 1.0) # blac k background
		
		# set up the shaders
		self.program = shader.initializeShaders(shader.vs, shader.fs, geometryShaderString=shader.gs)
		# constant uniforms
		self.widthLocation = glGetUniformLocation(self.program, "width")
		self.heightLocation = glGetUniformLocation(self.program, "height")
		self.nearLocation = glGetUniformLocation(self.program, "near")
		self.focalLocation = glGetUniformLocation(self.program, "focal")
		self.farLocation = glGetUniformLocation(self.program, "far")
		# dynamic uniforms
		self.xLocation = glGetUniformLocation(self.program, "x")
		self.yLocation = glGetUniformLocation(self.program, "y")
		self.xEyeLocation = glGetUniformLocation(self.program, "xEye")
		self.nFrameLocation = glGetUniformLocation(self.program, "nFrame")
		self.fadeFactorLocation = glGetUniformLocation(self.program, "fadeFactor")
		self.moveFactorLocation = glGetUniformLocation(self.program, "moveFactor")
		self.colorLocation = glGetUniformLocation(self.program, "color")
		#subroutine uniforms
		#self.MVPLocation = glGetSubroutineUniformLocation(self.program, GL_VERTEX_SHADER, "MVPFunc")
		#self.MVPIndex = glGetSubroutineIndex(self.program, GL_VERTEX_SHADER, "MVP")
		#self.MVP2Index = glGetSubroutineIndex(self.program, GL_VERTEX_SHADER, "MVP2")
		#print("####MVP: {}, {} {}".format(self.MVPIndex, self.MVP2Index))
		# attributes
		self.positionLocation = glGetAttribLocation(self.program, 'position')
		self.randSeedLocation = glGetAttribLocation(self.program, 'randSeed')
		self.disparityFactorLocation = glGetAttribLocation(self.program, 'disparityFactor')
		self.sizeLocation = glGetAttribLocation(self.program, "size") # star linear size in m
		self.lifetimeLocation = glGetAttribLocation(self.program, "lifetime") # star lifetime in frames

		
		glUniform3f(self.colorLocation, 1,0,1)
		self.initializeObjects()

	def resizeGL(self, width, height):
		logging.info("Resize: {}, {}".format(width, height))
		self.width = width
		self.height = height
		
	
	nFramePerSecond = 0 # number of frame in this Gregorian second
	nFrame = 0 # total number of frames
	nSeconds = int(time.time())
	def paintGL(self):
		if int(time.time()) > self.nSeconds:
			self.nSeconds = int(time.time())
			#print("fps: {}, extrapolation time: {:.3f} s".format(self.nFramePerSecond, self.extrapolationTime), end='\r')
			#print("fps: {}".format(self.nFramePerSecond), end='\r')
			sys.stdout.flush()
			self.nFramePerSecond = 0
		self.nFramePerSecond += 1
		
		
		if hasattr(self, "positionClient"): # only false if mouse is used
			mode = self.conditions.getString('mode'+self.moveString)
			if mode=='visual':
				pp = self.sledClientSimulator.getPosition()
				p = np.array(pp).ravel().tolist()
				self.viewerMove(p[0], p[1])
			elif mode=='combined' or mode=='vestibular':
				pp = self.positionClient.getPosition(self.positionClient.time()+5./60)          # get marker positions
				p = np.array(pp).ravel().tolist()       # python has too many types
				x = p[0]
				if self.moveString=="Trial":
					x *= (self.conditions.getNumber("dTrial")+self.conditions.getNumber("dVisualDelta"))/self.conditions.getNumber("dTrial")
				self.viewerMove(x, p[1])         # use x- and y-coordinate of first marker
			else:
				logging.error("mode not recognized: "+mode)
				
		## set uniform variables
		if self.nFrameLocation != -1:
			glUniform1i(self.nFrameLocation, self.nFrame)
		if self.fadeFactorLocation != -1:
			if self.state=="fadeIn" and self.fadeFactor < 0.999:
				self.fadeFactor=min(1.0, self.fadeFactor + 0.1)
			elif self.state=="responseBeep" and self.fadeFactor > 0.001:
				self.fadeFactor=max(0.0, self.fadeFactor - 0.1)
			if mode=='vestibular':
				glUniform1f(self.fadeFactorLocation, 0.0)  # no stars, no fixation
			else:
				glUniform1f(self.fadeFactorLocation, self.fadeFactor)
		else:
			logging.error("Could not set fadeFactor, vestibular condition unavailable")

		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		for eye in self.views:
			## setup view, change the next 5 lines for different type of stereo view
			if eye == 'LEFT':
				glViewport(0, 0, self.width/2, self.height)
				glUniform1f(self.xEyeLocation, -self.dEyes/2)
				intensityLevel = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1][self.stereoIntensityLevel-10]
			elif eye == 'LEFTSIM':
				glViewport(0, 0, self.width, self.height)
				glUniform1f(self.xEyeLocation, -self.dEyes/2)
				intensityLevel = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1][self.stereoIntensityLevel-10]
			elif eye == 'RIGHT':
				glViewport(self.width/2, 0, self.width/2, self.height)
				glUniform1f(self.xEyeLocation, self.dEyes/2)
				intensityLevel = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0][self.stereoIntensityLevel-10]
			elif eye == 'RIGHTSIM':
				glViewport(0, 0, self.width, self.height)
				glUniform1f(self.xEyeLocation, self.dEyes/2)
				intensityLevel = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0][self.stereoIntensityLevel-10]
			else:
				glViewport(0, 0, self.width, self.height)
				glUniform1f(self.xEyeLocation, 0)
				intensityLevel = 1.0
				
			glUniform1f(self.xLocation, self.pViewer[0]) # xEye is added by the shader
			glUniform1f(self.yLocation, self.pViewer[1])
			glUniform1f(self.moveFactorLocation, 0.0)

			glEnableClientState(GL_VERTEX_ARRAY)
			# enable stuff from float VBO
			self.vbo.bind() # get data from vbo with vertices
			glEnableVertexAttribArray(self.positionLocation)
			glVertexAttribPointer(self.positionLocation, 3, GL_FLOAT, GL_FALSE, 36, self.vbo)
			glEnableVertexAttribArray(self.randSeedLocation)
			glVertexAttribIPointer(self.randSeedLocation, 3, GL_UNSIGNED_INT, 36, self.vbo+12)
			glEnableVertexAttribArray(self.disparityFactorLocation)
			glVertexAttribPointer(self.disparityFactorLocation, 1, GL_FLOAT, GL_FALSE, 36, self.vbo+24)
			glEnableVertexAttribArray(self.sizeLocation)
			glVertexAttribPointer(self.sizeLocation, 1, GL_FLOAT, GL_FALSE, 36, self.vbo+28)
			glEnableVertexAttribArray(self.lifetimeLocation)
			glVertexAttribIPointer(self.lifetimeLocation, 1, GL_UNSIGNED_INT, 36, self.vbo+32)
			
			if mode!='visual':
				glUniform1f(self.moveFactorLocation, 0.0)
			else:
				glUniform1f(self.moveFactorLocation, -1.0) # countermove of fixation cross
			
			# draw reference triangles in one color
			glUniform3fv(self.colorLocation, 1, intensityLevel*self.conditions.getColor('cMD'))
			nPast = 0
			n = self.nMD
			glDrawArrays(GL_POINTS, 0, n)
			
			# draw noise triangles in another color
			glUniform3fv(self.colorLocation, 1, intensityLevel*self.conditions.getColor('cMND'))
			nPast = n
			n = self.nMND
			glDrawArrays(GL_POINTS, nPast, n)
			
			glUniform3fv(self.colorLocation, 1, intensityLevel*self.conditions.getColor('cNMD'))
			nPast += n
			n = self.nNMD
			glDrawArrays(GL_POINTS, nPast, n)
			
			glUniform3fv(self.colorLocation, 1, intensityLevel*self.conditions.getColor('cNMND'))
			nPast += n
			n = self.nNMND
			glDrawArrays(GL_POINTS, nPast, n)
			
			# draw fixation cross in white
			glUniform3fv(self.colorLocation, 1, intensityLevel*np.array([1,1,1],"f"))
			if mode!='visual':
				glUniform1f(self.moveFactorLocation, 1.0)
			else:
				glUniform1f(self.moveFactorLocation, 0.0)
			nPast += n
			glUniform1f(self.xEyeLocation, 0)
			glDrawArrays(GL_POINTS, nPast, 1)
			self.vbo.unbind()
			glDisableClientState(GL_VERTEX_ARRAY)
			

		## schedule next redraw
		if not self.state == "sleep":
			self.nFrame += 1
			self.update()

