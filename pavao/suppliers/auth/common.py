
import pavao

auth_schema = {
	"enabled": False
}

enabled = False
def process_config(loaded_settings):
	global enabled
	if enabled:
		return

	auth_settings = loaded_settings.get_setting("pavao.auth", auth_schema)
	if auth_settings is not None and auth_settings['enabled']:
		pavao.Logger.info("Pavão auth system enabled")
		enabled = True

