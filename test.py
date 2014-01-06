#!/usr/bin/python
from psychopy import core, data 
def test(x):
	return x>0

s = dataStairHandler(5)
for i in range(20):
	x = s()
	print(x)
	
	s.addData(text(x))
	
