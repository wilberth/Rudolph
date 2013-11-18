#!/usr/bin/python -B
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

This class implements a virtual sled. 

It holds a fifo list of moves, the current moves and future moves.

todo: moves with v0 != 0 (like in SledSimulator)
'''

import math, sys, time, numpy as np

class Move(object):
	"Linear move, use this as base class"
	def __init__(self, t0, t1, x0, x1, v0=0, a0=0):
		# public (derived classes have these too)
		self.t0 = t0
		self.x0 = x0
		self.t1 = t1
		self.x1 = x1
		sys.stderr.write(self.__repr__()+"\n")
		self.v0Norm = v0 / ( (self.x1-self.x0)/(self.t1-self.t0) )
		self.a0Norm = a0 / ( (self.x1-self.x0)/(self.t1-self.t0)**2 )
	def __repr__(self):
		return "<{} object t: {} - {}, x: {} - {}>".format(
			self.__class__.__name__,
			self.t0, self.t1, self.x0, self.x1)
	def getX(self, t):
		return self.getXVA(t)[0]
	def getXV(self, t):
		x, v, a = self.getXVA(t)
		return (x, v)
	def getXVA(self, t):
		if t < self.t0:
			return (self.x0, 0, 0)
		if t > self.t1:
			return (self.x1, 0, 0)
		# normalize
		tNorm = (t-self.t0)/(self.t1-self.t0)
		xNorm, vNorm, aNorm = self.sigmoid(tNorm, self.v0Norm, self.a0Norm)
		return (self.x0 + (self.x1-self.x0)*xNorm, 
			(self.x1-self.x0)/(self.t1-self.t0)*vNorm,
			(self.x1-self.x0)/(self.t1-self.t0)**2*aNorm)
	def sigmoid(self, t, v0, a0):
		"""Override this one with a sigmoid that does take v0 and a0 into account 
		to prevent discontinuities"""
		return self.sigmoid(t)
	def sigmoid(self, t):
		"""Any function through 0,0 and 1,1 and its derivative, override this one"""
		return (t, 1, 0)

class ConstantAccelerationMove(Move):
	"""Piecewise constant acceleration move. """
	def sigmoid(self, t):
		" x<.5?2*x**2:1-2*(1-x)**2, x<.5?4*x:4-4*x "
		if t<0.5:
			return (2*t**2, 4*t, 4)
		else:
			return (1-2*(1-t)**2, 4-4*t, -4)

class FiniteAccelerationMove(Move):
	"""Move without discontinuity in velocity."""
	def sigmoid(self, t):
		" 3*x**2-2*x**3 "
		return (3*t**2-2*t**3, 6*t-6*t**2, 6-12*t)
		
class FiniteJerkMove(Move):
	"""Move without discontinuity in acceleration."""
	def sigmoid(self, t):
		" 6*x**5-15*x**4+10*x**3 "
		return 6*t**5 - 15*t**4 + 10*t**3, 30*t**4 - 60 * t**2 + 30 * t**2
	def sigmoid(self, t, v0, a0):
		"""s(t) = a + bt + ct^2 + dt^3 + et^4 + ft^5
		s(0) = 0, s(1) = 1, s'(0) = v0, s'(1)=0, s''(0) = a0, s''(1)=0
		=>
		"""
		a = 0 # = x0
		b = v0
		c = 0.5*a0
		d = 10 - 6*v0 - 1.5*a0
		e = 1.5*a0 + 8*v0 - 15
		f = 6 - 3*v0 - 0.5*a0
		return (a + b*t + c*t**2 + d*t**3 + e*t**4 + f*t**5, 
			b + 2*c*t + 3*d*t**2 + 4*e*t**3 + 5*f*t**4,
			2*c + 6*d*t + 12*e*t**2 + 20*f*t**3)
		
	
class ContinuousMove(Move):
	"Prototype for continuous moves. Note x1-x0 is the full distance, t1-t0 is the halfperiod"
	def __init__(self, t0, t1, x0, x1):
		super(ContinuousMove, self).__init__(t0, t1, x0, x1)
		self.tHalfperiod = self.t1 # end time of the first halfperiod
		self.t1 = float("infinity")
	def getXVA(self, t):
		tNorm = (t - self.t0)/(self.tHalfperiod-self.t0)%2
		vFactor = 1.0
		if tNorm>1:
			tNorm = 2.0 - tNorm
			vFactor = -1.0
			aFactor = -1.0
		xNorm, vNorm, aNorm = self.sigmoid(tNorm)
		return (self.x0 + (self.x1-self.x0)*xNorm, 
			vFactor*(self.x1-self.x0)/(self.tHalfperiod-self.t0)*vNorm,
			aFactor*(self.x1-self.x0)/(self.tHalfperiod-self.t0)**2*aNorm)

class SineMove(ContinuousMove):
	def sigmoid(self, t):
		return ( (1-math.cos(t*math.pi))/2, 
		math.pi*math.sin(t*math.pi)/2,
		math.pi**2*math.cos(t*math.pi)/2 )
		

class SledClientSimulator:
	"Simulatorclient for the Sleelab Sled server"
	def __init__(self, t=None):
		if t==None:
			t=self.time()
		self.x0  = 0.0   # position at start of current move
		
		self.moves = []  # fifo of moves

	def time(self):
		return time.time()
		
 	def getX(self, t=None):
		x, v, a = self.getXVA(t)
		return x
 	def getXV(self, t=None):
		x, v, a = self.getXVA(t)
		return (x, v)
 	def getXVA(self, t=None):
		"""Pop finished moves and return x and v at times t """
		if t == None:
			t = self.time() # real world time
			
		# pop finished moves
		while len(self.moves)>0 and self.moves[0].t1<t:
			self.x0 = self.moves[0].x1
			self.moves.pop(0)
		
		if len(self.moves)>0:
			return self.moves[0].getXVA(t)
		else:
			return (self.x0, 0, 0)
		
	def warpto(self, x):
		"""Goto instantly"""
		self.x0  = x
		self.moves = []
		return 0 # dt
		          
	def gotoAppend(self, x, dt, t=None, MoveClass=FiniteJerkMove):
		"""Append move to list """
		if t == None:
			t = self.time() # real world time

		x0 = self.getX(t) # current position, this will pop finished moves
		
		# append if still unfinished moves present
		if len(self.moves)>0:
			t = self.moves[-1].t1 # end time of last move
			x0 = self.moves[-1].x1 # end position of last move
		
		if x0!=x:
			self.moves.append(MoveClass(t, t+dt, x0, x))
		
		return dt

	def goto(self, x, dt=2.0, t=None, MoveClass=FiniteJerkMove):
		"""Goto immediately"""
		if t == None:
			t = self.time() # real world time

		x0, v0, a0 = self.getXVA(t) # current position, this will pop finished moves
		
		if x0!=x:
			self.moves = [MoveClass(t, t+dt, x0, x, v0=v0, a0=a0)]
		
		return dt
	

	def getPosition(self, t=None):
		"same method as in fpClient"
		if t==None:
			t=self.time()
		return np.array([self.getX(), 0, 0])
	def getX(self, t=None):
		"""return current position"""
		x, v = self.getXV(t)
		return x
		
	def getV(self, t=None):
		"""return current velocity"""
		x, v, a = self.getXV(t)
		return v

	def getA(self, t=None):
		"""return current acceleration"""
		x, v = self.getXVA(t)
		return a

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
	s = SledClientSimulator(t=0)
	#print ("time to finish: {} s".format(s.goto(3)))
	#s.testSequence([0, 1, 4, 6, 9, 12, 13, 18], [3, 3, 0, -2, 0.75, .75, .25])
	#s.goto(1.0, dt=2.0, t=0)
	#s.goto(-1.0, dt=2.0, t=0)
	
	s.goto(1.0, dt=1.0, t=0, MoveClass=FiniteJerkMove)
	for t in np.linspace(0, 2, 201):
		if(t>0.249 and t<0.251):
			s.goto(1.0, dt=0.75, t=t, MoveClass=FiniteJerkMove)
		if(t>0.499 and t<0.501):
			s.goto(1.0, dt=0.5, t=t, MoveClass=FiniteJerkMove)
		x, v, a = s.getXVA(t=t)
		print("{:7.4f}\t{:7.4f}\t{:7.4f}".format(t, x, v))
	
	#m = FiniteJerkMove(0, 1, 0, 1, v0=0, a0=0)
	#for t in np.linspace(0, 1, 101):
		#x, v = m.getXV(t=t)
		#print("{:7.4f}\t{:7.4f}\t{:7.4f}".format(t, x, v))

