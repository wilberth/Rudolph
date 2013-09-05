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

import time
from sledclientsimulator import SledClientSimulator

s = SledClientSimulator()
print("#t(s)\tx(m)\tv(m/s)")
s.goto(1.0, t=0)
for i in range(16):
	t = 0.2*i
	print("{:6.3f}\t{:6.3f}\t{:6.3f}".format(t, s.getX(t=t), s.getXV(t=t)[1]))
	
print()
	
tStart = time.time()
print ("expected duration: {}".format(s.goto(2.0, t=tStart)))
for i in range(16):
	t=time.time()
	print("{:6.3f}\t{:6.3f}\t{:6.3f}".format(t-tStart, s.getX(t=t), s.getXV(t=t)[1]))
	time.sleep(.2)
	
print()
	
tStart = time.time()
print ("expected duration: {}".format(s.goto(3.0)))
for i in range(16):
	t=time.time()
	print("{:6.3f}\t{:6.3f}\t{:6.3f}".format(t-tStart, s.getX(), s.getXV()[1]))
	time.sleep(.2)
	
print()
	
tStart = time.time()
print ("expected duration: {}".format(s.goto(4.0)))
for i in range(21):
	t=time.time()
	print("{:6.3f}\t{:6.3f}\t{:6.3f}".format(t-tStart, s.getX(), s.getXV()[1]))
	if i == 5:
		print ("expected duration: {}".format(s.goto(5.0)))
	time.sleep(.2)
	
	

	
