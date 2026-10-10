
import pavao

@pavao.accepts_parameters({'query': str, 'limit': 10})
async def process(response, parameters):
  query = parameters['query']
  limit = parameters['limit']
  response.set_plain_text(f"Searching '{query}', up to {limit} results")


def pavao_endpoint():
  return {
    'method': 'GET',
    'path': '/search',
    'processor': process
  }
