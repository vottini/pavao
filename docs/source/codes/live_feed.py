
import pavao

@pavao.generates_sse()
async def process(emit, broadcasting):
  sink = broadcasting.open_sink('ticks')
  await emit.headers()

  try:
    while True:
      message = await sink.get_message()
      await emit.event('tick', message)
  finally:
    broadcasting.close_sink(sink)


def pavao_endpoint():
  return {
    'method': 'GET',
    'path': '/live',
    'processor': process
  }
