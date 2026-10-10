
async def process(response, broadcasting, path_variables):
  event = path_variables['event']
  await broadcasting.write_message('notifications', event)
  response.set_status(204)


def pavao_endpoint():
  return {
    'method': 'POST',
    'path': '/notify/{event}',
    'processor': process
  }
