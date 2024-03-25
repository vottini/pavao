
import asyncio
from datetime import datetime

async def proccess():
	print(f"[{datetime.now()}] Starting accumulator")
	total = 0

	for i in range(5):
		await asyncio.sleep(18)
		print(f"[{datetime.now()}] Accumulator step [{i+1}/5].")
		total += 15

	print(f"[{datetime.now()}] Accumulator finished")
	return f"Total sum is {total}"


def pavao_task():

	return {
		'package': "Testing",
		'functionality': "Accumulates some values",
		'processor': proccess,
		'schedule': '0/2 * * * *'
	}

