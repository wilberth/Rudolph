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
import shader

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
	#dScreen = np.array([2.728, 1.02])       # m, size of the screen
	dScreen = np.array([0.475, 0.296])       # m, size of the screen
	lifetime = 0
	
	
	
	def __init__(self, parent):
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

		
	def viewerMove(self, x, y=None):
		""" Move the viewer's position """
		logging.info("viewermove: ({}, {})".format(x, y))
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

	def initializeObjects(self):
		# set uniform variables and set up VBO's for the attribute values
		# reference triangles, do not move in model coordinates
		# position of the center
		
		self.nMD  = 10000
		self.nMND = 0
		self.nNMD = 0
		self.nNMND = 0
		
		nPast = 0
		n = self.nMD
		#position = np.random.rand(n, 3) * \
		#	[2*self.dScreen[0], 2*self.dScreen[1], self.zNear-self.zFar] - \
		#	[2*self.dScreen[0]/2, 2*self.dScreen[1]/2 , -self.zFar]
		x = np.array(np.random.randint(-5, 6, size=(n, 1)), dtype='float32')*0.10 # 10 cm intervals
		y = np.array(np.random.randint(-5, 6, size=(n, 1)), dtype='float32')*0.10 # 10 cm intervals
		z = np.zeros((n, 1), dtype='float32')
		position = np.hstack((x, y, z))
		randSeed = np.zeros((n, 3), dtype="uint32"); randSeed.dtype='float32'
		#randSeed = np.array(np.random.randint(0, 0xffff, size=(n,3)), dtype="uint32")
		#randSeed[:,1:3] = 0
		#randSeed.dtype='float32'

		disparityFactor = np.ones((n, 1), dtype='float32')
		#size = np.array(np.random.uniform(0.01, 0.02, (n, 1)), dtype='float32')
		size = 0.010*np.ones((n,1), dtype='float32')
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
		glClearColor(0.3, 0.0, 0.0, 1.0) # black background
		
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

		
		glUniform1f(self.fadeFactorLocation, 1)
		self.initializeObjects()

	def resizeGL(self, width, height):
		print("Resize: {}, {}".format(width, height))
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
		
		## set uniform variables
		if self.nFrameLocation != -1:
			glUniform1i(self.nFrameLocation, self.nFrame)
		else:
			logging.info("no nFrame in shaders")

		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		
		# no stereoscopic view:
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
		
		glUniform1f(self.moveFactorLocation, 0.0)
		
		# draw reference triangles in one color
		glUniform3f(self.colorLocation, intensityLevel*1, intensityLevel*0, intensityLevel*0)
		nPast = 0
		n = self.nMD
		glDrawArrays(GL_POINTS, 0, n)
		
		# draw noise triangles in another color
		glUniform3f(self.colorLocation, intensityLevel*1, intensityLevel*1, intensityLevel*0)
		nPast = n
		n = self.nMND
		glDrawArrays(GL_POINTS, nPast, n)
		
		glUniform3f(self.colorLocation, 0, 1, 1)
		nPast += n
		n = self.nNMD
		glDrawArrays(GL_POINTS, nPast, n)
		
		glUniform3f(self.colorLocation, 0,0,1)
		nPast += n
		n = self.nNMND
		glDrawArrays(GL_POINTS, nPast, n)
		
		# draw fixation cross in white
		glUniform3fv(self.colorLocation, 1, np.array([1,1,1],"f"))
		glUniform1f(self.moveFactorLocation, 1.0)
		
		nPast += n
		glUniform1f(self.xEyeLocation, 0)
		glDrawArrays(GL_POINTS, nPast, 1)
		self.vbo.unbind()
		glDisableClientState(GL_VERTEX_ARRAY)
			

		## schedule next redraw
		self.nFrame += 1
		self.update()

