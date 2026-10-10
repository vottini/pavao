
async def process(broadcasting, on_finish):
  sink = broadcasting.open_sink('commands')
  on_finish(lambda: broadcasting.close_sink(sink))

  while True:
    command = await sink.get_message()
    await broadcasting.write_message('results', f"executed: {command}")
    yield


def pavao_service():
  return {
    'name': 'command_monitor',
    'processor': process
  }
