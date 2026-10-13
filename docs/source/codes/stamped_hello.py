
import pavao

utc_milliseconds = pavao.from_module('timestamp').import_item('utc_milliseconds')

def process(response):
  time_info = utc_milliseconds()
  response.set_plain_text(f"World is now at {time_info}")


def pavao_endpoint():
  return {
    'method': 'GET',
    'path': '/hello/stamped',
    'processor': process
  }
