
import sys
import inspect
import os

def include(filename):
	callerFrame = inspect.stack()[1]
	callerPath = os.path.abspath(callerFrame.filename)
	callerDir = os.path.dirname(callerPath)

	filePath = os.path.join(callerDir, filename)
	with open(filePath) as fd:
		return fd.read()


__all__ = [
	"include"
]

