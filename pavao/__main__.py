
import uvicorn
import pavao

uvicorn.run(pavao.app,
	log_level='info',
	host="0.0.0.0",
	port=8000)

