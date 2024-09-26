
import pavao

def pavao_endpoint(db_connection):
	if db_connection is not None:
		pavao.Logger.info("Builtin Authentication is on")

