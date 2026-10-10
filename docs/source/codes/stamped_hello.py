
import timestamp

def process(response):
  time_info = timestamp.utc_milliseconds()
  response.set_plain_text(f"World is now at {time_info}")


def pavao_endpoint():
  return {
    'method': 'GET',
    'path': '/hello/stamped',
    'processor': process
  }
