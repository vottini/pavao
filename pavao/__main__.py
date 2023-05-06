
import asyncio
import uvicorn
import pavao

#	log_level='info',
#	host="0.0.0.0",
#	port=8001)

config = uvicorn.Config(
	app=pavao.app,
	loop=pavao.loop)

server = uvicorn.Server(config)
pavao.loop.run_until_complete(server.serve())

