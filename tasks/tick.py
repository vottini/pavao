
import asyncio
from datetime import datetime

def proccess():
	print(f"[{datetime.now()}] tick")
	return True


def pavao_task():

	return {
		'package': "Testing",
		'functionality': "Ticks periodicaly",
		'processor': proccess,
		'schedule': '0/1 * * * *'
	}

