
import pavao

item_schema = """
root {
  name: String,
  price: Float
}
"""

@pavao.accepts_json(string_blueprint=item_schema)
async def process(response, parsed_json):
  name = parsed_json.name
  price = parsed_json.price
  # ... persist item ...
  response.set_status(201)
  response.set_plain_text(f"Created '{name}' at {price:.2f}")


def pavao_endpoint():
  return {
    'method': 'POST',
    'path': '/items',
    'processor': process
  }
