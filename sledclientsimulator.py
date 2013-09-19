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

This class implements a virtual sled. it has a maximum speed and acceleration.
'''

import math, sys, time, numpy as np

class SledClientSimulator:
	"Simulatorclient for the Sleelab Sled server"
	vMax = 1   # m/s
	aMax = 0.5 # m/s^2
	
	def __init__(self, t=None):
		self.x0  = 0.0    # position at start of current interval
		if t==None:
			t=self.time()
		self.t0 = t      # time at start of current interval
		self.v0 = 0.0    # velocity at start of current interval
		self.dt = []      # duration of interval
		self.a = []       # acceleration during interval

	def time(self):
		return time.time()
		
	def gotoAfter(self, x, t=None):
		""" Goto given position after the current move has finished """
		if t==None:
			t=self.time()
		dt = self.dt
		a = self.a
		self.goto(x)
		self.dt = dt+self.dt
		self.a = a+self.a
		return sum(self.dt) + self.t0 - t
		
	def gotoFixedTime(self, x, dt):
		"""Go from here to x in a fixed time dt, to x at speed 0, , assume standstill at start
		return time it will take"""
		dx = x-self.x0         # requested move
		self.t0 = self.time()
		self.dt = [0.5*dt, 0.5*dt]
		self.a = [4.0*dx/dt**2, -4.0*dx/dt**2]
		return dt
		
		
	def warpto(self, x):
		self.x0  = x
		self.v0 = 0.0
		self.dt = []
		self.a = []
                
	def goto(self, x, dt=None, t=None):
		"""Calculate fastest way to get from here at speed v0, to x at speed 0, return time it will take"""
		if dt!=None:
			return self.gotoFixedTime(x, dt)
		if t==None:
			t=self.time()
		# self.getXV(t=t) # WvH: something like this, but not quite this
		self.x0 = self.getX(t) # current position
		dx = x-self.x0         # requested move
		
		self.v0 = self.getV(t) # current velocity
		self.t0 = t            # current time
		
		#for i in range(len(self.a)):
			#print("removing phase dt: {}, a: {}".format(self.dt[i], self.a[i]), file=sys.stderr)
		self.dt = []
		self.a = []
		
		# distance traveled during acceleration to vMax and decelaration to 0
		# note that this is independent of the sign of v0
		dxAcc = (self.vMax**2 -.5 * self.v0**2)/self.aMax # no sign
		# distance travelled in case of immediate stop
		dxStop = math.copysign(0.5*self.v0**2/self.aMax, self.v0) # with sign
		
		#print("goto, t: {}, x: {}, dx: {}, dxAcc: {}, dxStop: {}, x0: {}, v0: {}".format(t, x, dx, dxAcc, dxStop, self.x0, self.v0), file=sys.stderr)
		
		# acceleration phase
		self.a += [math.copysign(self.aMax, dx-dxStop)]

		if abs(dx) > dxAcc:
			# move with constant speed part
			self.dt += [(self.vMax-math.copysign(1, dx)*self.v0)/self.aMax]
			# constant velocity phase
			self.a += [0]
			self.dt += [(abs(dx)-dxAcc)/self.vMax]
		else:
			# move without constant speed part
			if abs(dx) > abs(dxStop): 
				# distance of full move, from standstill to standstill
				dxFull = dx + dxStop
			else:
				# break overshoot, after a full stop direction must be reversed
				dxFull = dx - dxStop
			self.dt += [math.sqrt(dxFull/self.a[0]) - self.v0/self.a[0]]
				
		# deceleration phase
		self.dt += [abs(self.v0+self.dt[0]*self.a[0])/self.aMax] # if there was a constant speed phase, this is vMax/aMax
		self.a += [-self.a[0]]

		#print("  dt: {}, a:{}".format(self.dt, self.a), file=sys.stderr)
		return sum(self.dt) + self.t0 - t # time to finish
			
		
			
	def getXV(self, t=None):
		"""return current position and velocity"""
		#time since t0
		if t == None:
			dt = self.time() - self.t0 # time since last goto
		else:
			dt = t - self.t0 # time since last goto
		

		# apply completed  movement phases
		while len(self.dt)>0 and dt>self.dt[0]:
			self.x0 += self.v0*self.dt[0] + 0.5*self.a[0]*self.dt[0]**2
			self.v0 += self.a[0]*self.dt[0]
			self.t0 += self.dt[0]
			dt -= self.dt[0]
			#print("finishing phase: dt: {}, new x0: {}, new v0: {}".format(self.dt[0], self.x0, self.v0), file=sys.stderr)
			self.dt.pop(0)
			self.a.pop(0)
			
		# no more accelerations to be made
		if len(self.dt) == 0:
			return [self.x0, 0]
		#print("####getXV: dt={}, x={}".format(dt, self.x0+self.v0*dt+0.5*self.a[0]*dt**2))

		return [self.x0+self.v0*dt+0.5*self.a[0]*dt**2, self.v0+self.a[0]*dt]

	def getPosition(self, t=None):
		"same method as in fpClient"
		if t==None:
			t=self.time()
		return np.array([self.getX(), 1.0, 0])
	def getX(self, t=None):
		"""return current position"""
		if t==None:
			t=self.time()
		[x, v] = self.getXV(t)
		return x
		
	def getV(self, t=None):
		"""return current velocity"""
		if t==None:
			t=self.time()
		[x, v] = self.getXV(t)
		return v

	def testSequence(self, tList, xList):
		""" t is a list of times, x is a list of destinations 
		    xList is one item longer than tList """
		ttOld = tList[0]
		print("#t(s)\tx(m)\tv(m/s)")
		while(len(xList)):
			tt = tList.pop(0)
			xx = xList.pop(0)
			s.goto(xx, t=tt)
			for i in range(int(100*int(tt)), 100*int(tList[0])):
				t = i*0.01
				[x,v] = s.getXV(t=t)
				print("{:7.3f}\t{:7.3f}\t{:7.3f}".format(t, x, v))
			ttOld = tt

		
if __name__ == '__main__':
	s = SledClientSimulator()
	#print ("time to finish: {} s".format(s.goto(3)))
	s.testSequence([0, 1, 4, 6, 9, 12, 13, 18], [3, 3, 0, -2, 0.75, .75, .25])
	
