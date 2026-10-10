
def process(response):
  response.set_plain_text("This endpoint requires no authentication")


def pavao_endpoint():
  return {
    'method': 'GET',
    'path': '/status',
    'processor': process,
    'public': True
  }
