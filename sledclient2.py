import fpclient

class SledClient(fpclient.FpClient):
	def __init__(self):
		"""just call the superclass constructor with default arguments"""
		#super(SledClient, self).__init__()
		fpclient.FpClient(self).__init__()
	#def connect(self, host="localhost", port=3375):
	def connect(self, host="localhost", port=3020):
		"""same as in superclass, but with a different port"""
		#super(SledClient, self).connect(host, port)
		fpclient.FpClient(self).connect(host, port)
	def goto(self, dx):
		"""Oder the sled to a certain position and return the time it will take in seconds"""
		self.sledClient.sendCommand("Profile 40 Set Table 2 Abs 0.1 {}".format(dx))
		self.sledClient.sendCommand("Profile 40 Execute")
		return 2.0
