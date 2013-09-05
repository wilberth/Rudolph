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
import fpclient, sledclient, sledclientsimulator, root, transforms, shader, conditions

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
	zNear   = 0.5*pViewer[2]                # m  viewable point nearest to viewer
	zFocal  = 0                             # m, position of physical screen, better not change this
	zFar    = -0.5*pViewer[2]               # m, viewable point furthest from viewer
	dEyes   = 0.063                         # m, distance between the eyes
	dScreen = np.array([2.728, 1.02])       # m, size of the screen
	halfWidthAtNearPlane = .5*dScreen[0] * ( pViewer[2]-zNear ) / ( pViewer[2]-zFocal) 
	halfHeightAtNearPlane = .5*dScreen[1] * ( pViewer[2]-zNear ) / ( pViewer[2]-zFocal) 
	tMovement = 1.5	                #Movement time reference and comparison movement, in seconds
	tHoming = 2.0 	                #Movement time homing movement, in seconds
	
	
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
						
		# experimental conditions
		self.conditions = conditions.Conditions(dataKeys=['swapMoves'])

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
		elif self.state=="sleep" or self.state=="home":
			self.state = "fadeIn"
			self.swapMoves = random.random()>0.5
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
			QTimer.singleShot(500, self.changeState) # 500ms: The extra milliseconds is to prevent the sled server to overwrite the movement file on the PLC unit while movement is being executed. Furthermore, it prevents perceptual overlap between the comparison and reference (or vice versa) movements.
		elif self.state=="move1ReInit":
			self.state = "move1"
			d = self.conditions.trial["d"+self.moveString]
			dd = self.conditions.trial['dReference']+self.conditions.trial['dTrial']
			dt = self.sledClientSimulator.goto(self.h+dd, self.tMovement)
			if self.conditions.trial["mode"+self.moveString] != "visual":
				dt = self.sledClient.goto(self.h+dd, self.tMovement)
			logging.info("state: move1 ({}): d = {} m, dt = {} s".format(self.moveString, d, dt))
			QTimer.singleShot(1000*dt+(0.1+0.3*np.random.random_sample()), self.changeState) #"0.1+0.3*np.random.random_sample()": Wait random time between 100 and 300ms before playing response beep. This to avoid the beep being a motion-stop cue
		elif self.state=="move1":
			self.state="responseBeep"
			logging.info("state: wait (for input)")
			self.soundBeep()
			QTimer.singleShot(350, self.changeState)        # extra timer to make sure that fade out is complete
		elif self.state=="responseBeep":
			self.state="wait"
			self.parent().downAction.setEnabled(True)
			self.parent().upAction.setEnabled(True)
		elif self.state=="wait":
			self.state = "fadeOut"
			logging.info("state: fadeOut")
			QTimer.singleShot(500, self.changeState)
		elif self.state=="fadeOut":
			self.state = "home"
			logging.info("state: home (homing)")
##			self.homingText.runAndWait()
			self.initializeObjects() # redraw of new random field of stars
			self.h =  -self.conditions.trial['dReference']+np.random.uniform(low=-0.1, high=0.02)
			dt = self.sledClientSimulator.goto(self.h, self.tHoming)	# Homing to -reference position
			if self.conditions.trial["mode"+self.moveString] != "visual":
				dt = self.sledClient.goto(self.h, self.tHoming)	# Homing to -reference position
			logging.info("state: homing: d = {} m, dt = {} s".format(self.h, dt))
			QTimer.singleShot(1000*(dt), self.changeState)
			self.parent().downAction.setEnabled(False)
			self.parent().upAction.setEnabled(False)
		else:
			logging.warning("state unknown: {}".format(self.state))
			
	def addData(self, data):
		if self.state=="wait":
			logging.info("received while waiting: {}".format(data))
			if self.conditions.iTrial < self.conditions.nTrial-1:
				if self.swapMoves:
					self.conditions.trial['swapMoves'] = True
					data = not data
				else:
					self.conditions.trial['swapMoves'] = False
				self.conditions.nextTrial(data = data)
			else:
				# last data
				self.conditions.addData(data)
				self.requestSleep = True
			self.changeState()
		else:
			logging.info("ignoring input: {}".format(data))
	
	views = ('ALL',)
	def toggleStereo(self, on):
		if on or len(self.views)==1:
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
		
	def viewerMove(self, x, y):
		""" Move the viewer's position """
		self.pViewer[0] = x
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
		self.sledClientSimulator.goto(self.h) # homing sled at -reference
	
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
			self.positionClient.connect(server)                  # connect the client to the First Principles server
			self.positionClient.startStream()                    # start the synchronization stream. 
			time.sleep(2)


	def initializeObjects(self, moveString="Reference"):
		# set uniform variables and set up VBO's for the attribute values
		# reference triangles, do not move in model coordinates
		# position of the center
		
		self.nMD  = self.conditions.getNumber('nMD'+moveString)
		self.nMND = self.conditions.getNumber('nMND'+moveString)
		self.nNMD = self.conditions.getNumber('nNMD'+moveString)
		self.nNMND = self.conditions.getNumber('nNMND'+moveString)
		
		n = self.nMD
		pReference = np.random.rand(n, 3) * \
			[2*self.dScreen[0], 2*self.dScreen[1], self.zNear-self.zFar] - \
			[2*self.dScreen[0]/2, 2*self.dScreen[1]/2 , -self.zFar]
		
		# Fixation point triangle in origin
		#pReference[0] = np.matrix([0,0,0])
		randSeed = np.zeros((pReference.shape[0], 3))
		disparityFactor = np.ones((pReference.shape[0], 1))
		size = np.random.uniform(0.01,0.05,[n, 1])
		# generate vertex array from position arrays
		# each vertex has:
		# 3 dimensions (x, y, z)
		# 3 randSeeds (one for each dimension), these are 0 for non random
		# 1 disparityFactor, this is 1 if disparity is used
		referenceVertices = np.reshape(np.hstack([
			pReference, 
			randSeed,
			disparityFactor,
			size,
			]), [ pReference.shape[0], 8 ]) 
		
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
		
		# triangle positions,
		n = self.nMND
		pNoise = np.random.rand(n, 3) * \
			[2*self.dScreen[0], 2*self.dScreen[1], self.zNear-self.zFar] - \
			[2*self.dScreen[0]/2, 2*self.dScreen[1]/2 , -self.zFar]
		randSeed = np.zeros((pNoise.shape[0], 3))
		#disparityFactor = np.zeros((pNoise.shape[0], 1))#np.transpose(np.matrix(np.linspace(-1,1,trial['nMND'])))
                #disparityFactor = np.reshape(np.arange(2,n+2), [n, 1])
                #disparityFactor = np.reshape(np.linspace(2,12,n), [n, 1])
		disparityFactor = np.random.uniform(-1,1,[n, 1])
		size = np.random.uniform(0.01,0.05,[n, 1])
		# noise vertices
		movNonDispVertices = np.hstack([
			pNoise, 
			randSeed,
			disparityFactor,
			size,
		])
		
		# NonMovDisp:
		#************
		# randSeeds: array of predetermined numbers (random movement)
		# disparityFactor: 1 (disparity)		

		# triangle positions, 
		n = self.nNMD
		pNoise = np.zeros([n, 3])
		randSeed = np.reshape(np.arange(1,.1+3*n), [n, 3])
		disparityFactor = np.ones([n, 1])
		size = np.random.uniform(0.01,0.05,[n, 1])
		nonMovDispVertices = np.hstack([
			pNoise, 
			randSeed,
			disparityFactor,
			size,
		])
		
		# NonMovNonDisp:
		#***************
		# randSeeds: array of predetermined numbers (random movement)
		# disparityFactor: 0 (no disparity)		

		# triangle positions, 
		n = self.nNMND
		pNoise = np.zeros([n, 3])
		randSeed = np.reshape(np.arange(1000,999.1+3*n), [n, 3])
		disparityFactor = np.zeros((pNoise.shape[0], 1))#np.transpose(np.matrix(np.linspace(-1,1,trial['nMND'])))#np.zeros((pNoise.shape[0], 1))
		size = np.random.uniform(0.01,0.05,[n, 1])
		nonMovNonDispVertices = np.hstack([
			pNoise, 
			randSeed,
			disparityFactor,
			size,
		])
		#print(np.shape(nonMovNonDispVertices))
		
		# fixation cross
		fixationCrossVertices = np.array(
		[
			[0,0,0, 0,0,0, 1, 0.03],
		]
		)

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
		#glUniform1f(self.sizeLocation, 0.03)

		
	def initializeGL(self):
		glEnable(GL_DEPTH_TEST)          # painters algorithm without this
		glEnable(GL_MULTISAMPLE)         # anti aliasing
		glClearColor(0.0, 0.0, 0.0, 1.0) # set to black in production version
		
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
		#self.sizeLocation = glGetUniformLocation(self.program, "size")              # star linear size in m
		#subroutine uniforms
		#self.MVPLocation = glGetSubroutineUniformLocation(self.program, GL_VERTEX_SHADER, "MVPFunc")
		#self.MVPIndex = glGetSubroutineIndex(self.program, GL_VERTEX_SHADER, "MVP")
		#self.MVP2Index = glGetSubroutineIndex(self.program, GL_VERTEX_SHADER, "MVP2")
		#print("####MVP: {}, {} {}".format(self.MVPIndex, self.MVP2Index))
		# attributes
		self.positionLocation = glGetAttribLocation(self.program, 'position')
		self.randSeedLocation = glGetAttribLocation(self.program, 'randSeed')
		self.disparityFactorLocation = glGetAttribLocation(self.program, 'disparityFactor')
		self.sizeLocation = glGetAttribLocation(self.program, "size")              # star linear size in m

		
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
		
		
		# set uniform variables
		if self.nFrameLocation != -1:
			glUniform1i(self.nFrameLocation, self.nFrame)
		if self.fadeFactorLocation != -1:
			glUniform1f(self.fadeFactorLocation, self.fadeFactor)
			if self.state=="fadeIn" and self.fadeFactor < 0.999:
				self.fadeFactor=min(1.0, self.fadeFactor + 0.05)
			elif self.state=="responseBeep" and self.fadeFactor > 0.001:
				self.fadeFactor=max(0.0, self.fadeFactor - 0.05)
		
		if hasattr(self, "positionClient"): # only false if mouse is used
			mode = self.conditions.getString('mode'+self.moveString)
			if mode=='combined':
				#pp = self.client.getPosition()         # get marker positions
				pp = self.positionClient.getPosition(self.positionClient.time()+5./60)          # get marker positions
				p = np.array(pp).ravel().tolist()       # python has too many types
				x = 2*p[0]
				if self.moveString=="Trial":
					x *= (self.conditions.getNumber("dTrial")+self.conditions.getNumber("dVisualDelta"))/self.conditions.getNumber("dTrial")
				self.viewerMove(x, 2*p[1])         # use x- and y-coordinate of first marker
			elif mode=='visual':
				pp = self.sledClientSimulator.getPosition()
				p = np.array(pp).ravel().tolist()
				self.viewerMove(2*p[0], 2*p[1])
			elif mode=='vestibular':
				self.viewerMove(self.h)         # use x- and y-coordinate of first marker
			else:
				logging.error("mode not recognized: "+mode)
				


		
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		for eye in self.views:
			## setup view, change the next 5 lines for different type of stereo view
			if eye == 'LEFT':
				glViewport(0, 0, self.width/2, self.height)
				glUniform1f(self.xEyeLocation, -self.dEyes/2)
				intensityLevel = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1][self.stereoIntensityLevel-10]
			elif eye == 'RIGHT':
				glViewport(self.width/2, 0, self.width/2, self.height)
				glUniform1f(self.xEyeLocation, self.dEyes/2)
				intensityLevel = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0][self.stereoIntensityLevel-10]
			else:
				glViewport(0, 0, self.width, self.height)
				glUniform1f(self.xEyeLocation, 0)
				intensityLevel = 1.0
				
			glUniform1f(self.xLocation, self.pViewer[0]) # xEye is added by the shader
			glUniform1f(self.yLocation, self.pViewer[1])
			glUniform1f(self.moveFactorLocation, 0.0)

			## draw, from buffer
			self.vbo.bind() # get data from vbo with vertices
			
			#enable the three components in the VBO
			glEnableClientState(GL_VERTEX_ARRAY)
			glEnableVertexAttribArray(self.positionLocation)
			glVertexAttribPointer(self.positionLocation, 3, GL_FLOAT, GL_FALSE, 32, self.vbo) # index, num per vertex, type, normalize, stride, pointe
			glEnableVertexAttribArray(self.randSeedLocation)
			glVertexAttribPointer(self.randSeedLocation, 3, GL_FLOAT, GL_FALSE, 32, self.vbo+12) # index, num per vertex, type, normalize, stride, pointe
			glEnableVertexAttribArray(self.disparityFactorLocation)
			glVertexAttribPointer(self.disparityFactorLocation, 1, GL_FLOAT, GL_FALSE, 32, self.vbo+24) # index, num per vertex, type, normalize, stride, pointe
			glEnableVertexAttribArray(self.sizeLocation)
			glVertexAttribPointer(self.sizeLocation, 1, GL_FLOAT, GL_FALSE, 32, self.vbo+28) # index, num per vertex, type, normalize, stride, pointe

			# draw reference triangles in one color
			glUniform3fv(self.colorLocation, 1, intensityLevel*self.conditions.getColor('cMD'))
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
			glUniform1f(self.moveFactorLocation, 1.0)
			nPast += n
			glUniform1f(self.xEyeLocation, 0)
			glDrawArrays(GL_POINTS, nPast, 1)
			self.vbo.unbind()
			

		## schedule next redraw
		if not self.state == "sleep":
			self.nFrame += 1
			self.update()

