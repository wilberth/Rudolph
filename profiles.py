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

profile names for ball movement
'''

def linear(t):
	"""
	s(0) = 0, s(1) = 1
	"""
	if t<0:
		return 0.0
	if t>1:
		return 1.0
	return t

def minacc(t):
	"""
	s(0) = 0, s(1) = 1, s'(0) = 0, s'(1)=0
	"""
	if t<0:
		return 0.0
	if t>1:
		return 1.0
	return 3.0*t**2 - 2*t**3

def minjerk(t):
	"""
	s(0) = 0, s(1) = 1, s'(0) = 0, s'(1)=0, s''(0) = 0, s''(1)=0
	"""
	if t<0:
		return 0.0
	if t>1:
		return 1.0
	return 10.0*t**3 - 15*t**4 + 6*t**5
	