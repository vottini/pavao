
import pavao
from datetime import datetime, timezone, timedelta

login_schema = """
root {
  username: String,
  password: String
}
"""

@pavao.accepts_json(string_blueprint=login_schema)
async def process(response, jwt, parsed_json):
  # verify credentials against storage here
  valid = parsed_json.username == 'alice' and parsed_json.password == 'secret'

  if not valid:
    response.set_status(401)
    return

  now = datetime.now(timezone.utc)
  claims = {
    'sub': parsed_json.username,
    'iat': now.timestamp(),
    'exp': (now + timedelta(minutes=30)).timestamp()
  }

  token = jwt.generate_token(claims)
  response.set_plain_text(token)
  response.set_status(200)


def pavao_endpoint(jwt):
  if jwt is None:
    return

  return {
    'method': 'POST',
    'path': '/login',
    'processor': process
  }
