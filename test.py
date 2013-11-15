#!/usr/bin/python
class A(object):
	def __init__(self):
		print("init A")
		self.aa = 1
class B(A):
	def __init__(self):
		super(B, self).__init__()
		print("init B")
		self.aa = 2
	

if __name__ == '__main__':
	a = A()
	print(a.aa)
	b = B()
	print(b.aa)
