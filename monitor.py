#!/usr/bin/env python
import os, pypsignifit

def fit(x, y):
	pass
	## cores (of sigmoid)
	#ab(x, a, b) = (x-a)/b
	## sigmoids
	# logistic(x) = 1/(1+exp(x))
	## 
	# F(x, a, b) = logistic(core(x, a, b))
	## psi (psychometric curve)
	# psi(x, a, b, gamma, lambda) = gamma + (1 - gamma - lambda) * F(x, a, b)
	#
	# where F = 1/(1+exp(x))
	# a = thresshold rate
	# b = slope
	# gamma = guessing rate, or the lower asymptote
	# lambda = lapsing rate, or the upper asymptote



if os.path.isdir('data'):
	directory = 'data/'
else:
	directory = '.'
dataFiles = sorted([ f for f in os.listdir(directory) if f.endswith('dat')])
fileName = dataFiles[-1]
print("Most recent file = %s" % (fileName,))
with open(directory+fileName, 'r') as f:
	print(f.read())
	
