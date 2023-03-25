
import asyncio
import uvicorn

from starlette.applications import Starlette
from starlette.routing import Route
from sse_starlette.sse import EventSourceResponse

async def retriever(source):
	while True:
		obtained = await source.get()
		yield dict(event="lele", data=obtained)

async def inserter(sink):
	while True:
		await asyncio.sleep(5)
		sink.put_nowait("lala")

async def sse(request):
	queue = asyncio.Queue()
	generator = retriever(queue)
	asyncio.create_task(inserter(queue))
	return EventSourceResponse(generator)

routes = [
    Route("/", endpoint=sse)
]

app = Starlette(debug=True, routes=routes)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level='info')

