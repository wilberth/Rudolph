#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, pickle
from conditions import * 
def run(n):
	while conditions.iTrial < n:
		print("{}/{}".format(conditions.iTrial, conditions.nTrial))
		x = conditions.trial['x']
		if x < 1.0:
			print("  x: {} ↑".format(x))
		else:
			print("  x: {} ↓".format(x))
		conditions.nextTrial(x > 1.0)
		time.sleep(1)

if __name__ == '__main__':
	if len(sys.argv) < 2:
		print("usage: testPickle.py start/continue/full")
		exit(0)
	if sys.argv[1]=="start":
		conditions = Conditions()
		conditions.load("experiment/pickle.csv")
		run(conditions.nTrial//2)
		conditions.saveFile = None # files cannot be pickled
		s = pickle.dump(conditions, open("data/pickle.dat", "wb"))
	elif sys.argv[1]=="continue":
		conditions = pickle.load(open("data/pickle.dat", "rb"))
		conditions.saveFile = open("/tmp/dump.dat", "wb")
		run(conditions.nTrial)
	elif sys.argv[1]=="full":
		conditions = Conditions()
		conditions.load("experiment/pickle.csv")
		run(conditions.nTrial)
	else:
		print("usage: testPickle.py start/continue/full")
		