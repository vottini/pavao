
def process(response):
  response.set_plain_text("World")


def pavao_endpoint():
  return {
    'method': 'GET',
    'path': '/hello',
    'processor': process
  }
