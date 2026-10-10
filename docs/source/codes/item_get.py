
import pavao

item_schema = """
root {
  id: Integer,
  name: String,
  price: Float
}
"""

@pavao.generates_json(string_blueprint=item_schema)
async def process(response, path_variables):
  item_id = path_variables['id']
  # ... fetch item from storage ...
  found = item_id == 1
  if not found:
    response.set_status(404)
    return None

  return {'id': item_id, 'name': 'Widget', 'price': 9.99}


def pavao_endpoint():
  return {
    'method': 'GET',
    'path': '/items/{id:int}',
    'processor': process
  }
