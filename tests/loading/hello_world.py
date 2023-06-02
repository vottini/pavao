
import hello
import world
import submodule1.submodule11.whatever as whatever

def pavao_endpoint():
	return f"{hello.pavao_endpoint()} {world.pavao_endpoint()}!... {whatever.pavao_endpoint()}"

