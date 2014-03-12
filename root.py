#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Copyright � 2013-2014, W. van Ham, Radboud University Nijmegen
Copyright � 2013-2014, A.C. ter Horst, Radboud University Nijmegen
Copyright � 2013, I. Clemens, Radboud University Nijmegen,for the Kontsevich class
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

The functions and functors in the module can be used in Sleelab experiment
files. 
'''

from __future__ import print_function
import math, numpy as np, re, random
try:
	import pypsignifit as psi
except:
	pass
import time, threading
""" Psychometric root finding find the mu value of a psychometric curve.
Use the function object call ( __call__() ) to get the current stimulus value.
If the stimulus value is considered beyond the tresshold by the testee, 
call addData(True). If it is considered not beyond the tresshold, call addData(False).
"""

class Bisect(object):
        """root finding functor, determine what x-value to probe next"""
        def __init__(self, min, max):
                self.min = min
                self.max = max
                self.x = 0.5*(min+max)
                
        def __call__(self):
                return self.x
                
        def addData(self, m):
                if m:
                        self.max = self.x
                        self.x = 0.5*(self.min+self.max)
                else:
                        self.min = self.x
                        self.x = 0.5*(self.min+self.max)

                
class Random(object):
        """Return random values betwen min and max."""
        def __init__(self, min, max):
                self.min = min
                self.max = max
                
        def __call__(self):
                return self.min + (self.max-self.min)*random.random()
                
        def addData(self, m):
                pass

class Step(object):
        """non converging root finding functor"""
        nValue=10
        def __init__(self, min, max):
                self.values = np.linspace(min, max, self.nValue)
                self.iValue = self.nValue//2
                
        def __call__(self):
                return self.values[self.iValue]

        def addData(self, m):
                if m and self.iValue > 0:
                        self.iValue -= 1
                elif self.iValue < self.nValue-1:
                        self.iValue += 1

class List(object):
        """Uses set list of stimuli, given by user"""
        def __init__(self, x):
                self.x = x
                self.i = 0
                
        def __call__(self):
                return self.x[self.i]
                
        def addData(self, response):
                self.i = (self.i+1)%len(self.x)

                        
class Interval(object):
        """n fixed interval values from min to max"""
        def __init__(self, min=0, max=0.8, nx=11, ):
                self.x = np.linspace(min, max, nx)
                self.i = 0
                
        def __call__(self):
                return self.x[self.i]
                
        def addData(self, response):
                self.i = (self.i+1)%len(self.x)


class IntervalPse(object):
        """n fixed interval values from min to max"""
        def __init__(self, min=0, max=0.8, nxInit=11, nInit=10, nxPost=20):
                self.y = []
                self.x = np.linspace(min, max, nx)
                self.i = 0
                self.nxInit = nxInit
                self.nInit = nInit
                
        def __call__(self):
                if i < self.nxInit*self.nInit:
                        return self.x[self.i%self.nxInit]
                else:
                        return self.x[(self.i-self.nxInit*self.nInit)%len(self.x)]
                        
                
        def addData(self, response):
                self.y.append(response)
                self.i += 1
                if i==self.nxInit*self.nInit:
                        B = psi.BootstrapInference(self.y, core='ab', sigmoid='gauss', priors=('unconstrained', 'unconstrained', 'Uniform(0.0399,0.0401)', 'Uniform(0.0399,0.0401)'), nafc=1)
                        self.x = random.shuffle(np.linspace(B.estimate-4*B.deviance, B.estimate+4*B.deviance, nxPost))
                        
        
class IntervalShuffle(Interval):
        """n fixed interval values from min to max in random order"""
        def __init__(self, min=0, max=0.8, nx=11):
                super(IntervalShuffle, self).__init__(min, max, nx)
                self._shuffle()
                
        def addData(self, response):
                super(IntervalShuffle, self).addData(False)
                if self.i==0:
                        self._shuffle()
                
        def _shuffle(self):
                random.shuffle(self.x)
        
class Staircase(object):
        """never ending staircase handler"""
        def __init__(self, startVal, stepSizes=None, stepSizesUp=None, stepSizesDown=None, nUp=1, nDown=1, nInitMode=1, minVal=float("-inf"), maxVal=float("inf")):
                """
                :Parameters:

                        startVal:
                                The initial value for the staircase.

                        stepSizes:
                                The size of steps as a single value or a list (or array). For a single value the step
                                size is fixed. For an array or list the step size will progress to the next entry
                                at each reversal.

                        nUp:
                                The number of consecutive 'incorrect' (or 0) responses before the staircase level increases.

                        nDown:
                                The number of consecutive 'correct' (or 1) responses before the staircase level decreases.

                        minVal: *None*, or a number
                                The smallest legal value for the staircase, which can be used to prevent it
                                reaching impossible contrast values, for instance.

                        maxVal: *None*, or a number
                                The largest legal value for the staircase, which can be used to prevent it
                                reaching impossible contrast values, for instance.

                """
                self.val = startVal
                self.lastReversal = 0 # -1 for down, +1 for up
                self.nReversal = 0
                self.iDown = 0; self.iUp = 0
                self.nUp = nUp; self.nDown = nDown
                self.iStep = 0 # index of next step
                self.minVal = minVal; self.maxVal = maxVal
                self.nInitMode = nInitMode

                if stepSizes != None:
                        if type(stepSizes) in [int, float]: 
                                self.stepUp = [stepSizes]
                                self.stepDown = [stepSizes]
                        else:
                                self.stepUp = stepSizes
                                self.stepDown = stepSizes
                else:
                        if type(stepSizesUp) in [int, float]: 
                                self.stepUp = [stepSizesUp]
                        else:
                                self.stepUp = stepSizesUp
                        if type(stepSizesDown) in [int, float]: 
                                self.stepDown = [stepSizesDown]
                        else:
                                self.stepDown = stepSizesDown
                
        def __call__(self):
                return self.val
                        
        def addData(self, response):
                #print("r: {}, iUp: {}/{}, iDown: {}/{}, nReverse: {}".
                        #format(response, self.iUp, self.nUp, self.iDown, self.nDown, self.nReversal))
                if response:
                        self.iDown += 1
                        self.iUp = 0
                        if self.iDown == self.nDown or self.nReversal<2*self.nInitMode:
                                self.iDown = 0
                                self.val -= self.stepDown[min(self.iStep, len(self.stepDown)-1)]
                                if self.lastReversal != -1:
                                        self.nReversal += 1
                                        self.lastReversal = -1
                                        if self.nReversal%2 == 0  and self.nReversal != 0:
                                                self.iStep += 1
                else: 
                        self.iUp += 1
                        self.iDown = 0
                        if self.iUp == self.nUp or self.nReversal<2*self.nInitMode:
                                self.iUp = 0
                                self.val += self.stepUp[min(self.iStep, len(self.stepUp)-1)]
                                if self.lastReversal != 1:
                                        self.nReversal += 1
                                        self.lastReversal = 1
                                        if self.nReversal%2 == 0  and self.nReversal != 0:
                                                self.iStep += 1
                                                
                self.val = max(self.minVal, min(self.val, self.maxVal))
                
        def next(self):
                return self.__call__()
        def iter(self):
                return self
        
                
                
from scipy.stats import norm
class Psi:
        """Implements Kontsevich adaptive estimation of psychometric slope and threshold. """
        # x is the vector of possible stimuli
        # mu is the vector of possible 'mean values' in the psychometric curve
        # sigma is the vector of possible 'slopes' in the psychometric curve 
        def __init__(self, xMin=None, xMax=None, x=None, mu = None, sigma = np.linspace(0.004, 0.10, 49), lapseRate = 0.04, initStimuli=[], initData=[]):
                """Setup adaptive psychometric procedure
                
                Keyword arguments:
                options -- dictionary with settings, the following keys are supported:
                        - x -- Possible stimuli
                        - mu -- Sampling points for mu in p(mu, sigma)
                        - sigma -- Sampling points for sigma in p(mu, sigma)
                """
                ## handle input values
                # possible stimulus values
                if x != None:
                        self.x = x
                elif xMin != None and xMax != None:
                        self.x = np.linspace(xMin, xMax, 101)
                else:
                        self.x = np.linspace(0, 100, 101)

                # values of mu for which we compute p(mu, sigma | responses)
                if mu == None:
                        self.mu = self.x
                else:
                        self.mu = mu
                
                # values of sigma for which we compute p(mu, sigma | responses)
                self.sigma = sigma
                
                # number of responses on this x stimules
                self.hist = np.zeros(np.shape(self.x), dtype="int")  
                
                # number of True responses for this x stimulus
                self.y = np.zeros(np.shape(self.x), dtype="int")     

                # assumed lapse rate lambda (equals guess rate)
                self.lapseRate = lapseRate
                
                self.initStimuli = initStimuli
                
                ## initial settings and calculations
                self.iData = 0                 # number of data values send to this Psi object
                self.nMu = len(self.mu)
                self.nSigma = len(self.sigma)
                self.nx = len(self.x)

                # Number of theta values (all combinations of mu and sigma)
                self.nTheta = self.nMu * self.nSigma

                # Initialize lookup tables to speed up computation during experiment
                self.lookup = np.zeros((self.nx, self.nTheta))
                                
                for i in range(0, self.nTheta):
                        self.lookup[:, i] = self.lapseRate + \
                                (1 - 2 * self.lapseRate) * norm.cdf(self.x, self.mu[i / self.nSigma], self.sigma[i % self.nSigma])
                # Reset p(mu, sigma) of curve to prior
                self.pTheta = np.ones(self.nTheta) / self.nTheta
                self.calcNextStim()
                
                # optionally initiallize the theta landscape with a set of datapoints 
                if len(initData)> len(self.initStimuli):
                        logging.error("More init data values than init Stimuli values in Psi")
                for i in range (len(initData)):
                        self.addData(bool(initData[i]))
                        self.calcNextStim()
                
        def addData(self, response, stimulus=None):
                """Updates p(mu, sigma) of curve given new data."""
                
                self.iData += 1
         
                if stimulus == None:
                 stimulus = self.stim
                self.stim = None # this remains None until calcNextStim has finished in the background
                
                # Find nearest x
                ix = np.argmin(abs(self.x - stimulus))
                prx = self.lookup[ix, 0:self.nTheta] # probability of this x
                
                # Update probability depending on response
                self.hist[ix] += 1
                if(response == False):
                        self.pTheta *= (1 - prx)
                else:
                        self.y[ix] += 1
                        self.pTheta *= prx

                # Normalize
                self.pTheta /= sum(self.pTheta)
                
                # schedule calculation
                #self.calcNextStim()
                threading.Thread(target = self.calcNextStim).start()
                
        def getData(self):
                """ return x, y, number of occurences (the way psignifit likes the data) 
                Note that this function and functions like this one should not be used in production code.
                Data must be saved to file after each measurement to prevent data loss when the experiment 
                is aborted.
                """
                iNotNan = self.hist != 0
                return np.c_[self.x[iNotNan], 1.0*self.y[iNotNan]/self.hist[iNotNan], self.hist[iNotNan]]


        def __call__(self):
                # the next two lines are really a thread.join
                while(self.stim==None):
                        time.sleep(.1)

                if self.iData<len(self.initStimuli):
                        return self.initStimuli[self.iData]
                else:
                        return self.stim
                
        def calcNextStim(self):
                """Finds best stimulus to present next, usually runs in the background."""
                H = np.zeros(self.nx)
                                
                for x in range(0, self.nx):
                        pttrx_l = self.pTheta * (1 - self.lookup[x, 0:self.nTheta])
                        pttrx_r = self.pTheta * (self.lookup[x, 0:self.nTheta])
                        
                        ptrx_l = sum(pttrx_l)
                        ptrx_r = sum(pttrx_r)

                        pttrx_l = pttrx_l / ptrx_l
                        pttrx_r = pttrx_r / ptrx_r
                        
                        H_l = -sum(pttrx_l * np.log(pttrx_l + 1e-10))
                        H_r = -sum(pttrx_r * np.log(pttrx_r + 1e-10))
                        
                        H[x] = ptrx_l * H_l + ptrx_r * H_r

                self.stim = self.x[np.argmin(H)]

        

def test(x):
        return x*x-2
        
if __name__ == '__main__':
        # attempt to find root if test function with root finder on command line 
        # the root is at sqrt(2).
        import sys
        
        # get minimizer
        thisModule = sys.modules[__name__]
        
        # read alternative function from command line
        if len(sys.argv) > 1:
                m = re.match('(\w+)\(([\d\-\+\.Ee]+)\,\s*([\d\-\+\.Ee]+)\)', sys.argv[1])
                if m:
                        functionString = m.group(1)
                        min = float(m.group(2))
                        max = float(m.group(3))
                        init = getattr(thisModule, functionString)
                        minimizer = init(min, max)
                else:
                        functionString = sys.argv[1]
                        init = getattr(thisModule, functionString)
                        minimizer = init(0, 2)
        else:
                minimizer = Psi(0,2)
        print("using: {}".format(minimizer))
        
        # loop
        for i in range(20):
                t = time.time()
                x = minimizer()
                dt = time.time()-t
                if test(x) < 0:
                        print("x: {} ?".format(minimizer()))
                        minimizer.addData(False)
                else:
                        print("x: {} ?".format(minimizer()))
                        minimizer.addData(True)
                print ("  get: {:6.3f} ms, set: {:6.3f} ms".format(1000*dt, 1000*(time.time()-t-dt)))
                #time.sleep(1) # without this sleep "x = minimizer()" (get) will be slow
