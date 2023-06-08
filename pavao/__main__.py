
import asyncio
import pavao

#	log_level='info',
#	host="0.0.0.0",
#	port=8001)

handler = pavao.Handler(
	'application.yml',
	'./endpoints'
)

import uvicorn
asgi_config = uvicorn.Config(
	app=handler.get_app(),
	loop=handler.loop)

asgi_server = uvicorn.Server(asgi_config)
handler.loop.run_until_complete(asgi_server.serve())

