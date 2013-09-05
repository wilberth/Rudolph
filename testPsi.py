#!/usr/bin/env python
import root, random, numpy as np
from scipy.stats import norm
 
def test(x):
	return np.random.random() < norm.cdf(x, loc=0.15, scale=0.025)
 
minimizer = root.Psi(0.02,0.28)
stimuli = []
for i in range(20):
	x = minimizer()                 # get the next value
	stimuli.append(x)
	above = test(x)                 # check wether we are above the thresshold or not
	minimizer.addData(above) # tell the minimizer the result
	if above:
		print("{:6.3f}\t{}".format(x, 1))
	else:
		print("{:6.3f}\t{}".format(x, 0))
		
print ("")
#print histogram
n, bins = np.histogram(stimuli)
for i in range(len(n)-1):
	print("{:6.3f} {}".format((bins[i]+bins[i+1])/2, n[i]))
