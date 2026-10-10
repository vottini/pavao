
import pavao

# Any number of clients can connect to this endpoint simultaneously.
# Each gets its own sink and receives all messages published on 'notifications'.

@pavao.generates_sse()
async def process(emit, broadcasting):
  sink = broadcasting.open_sink('notifications')
  await emit.headers()

  try:
    while True:
      message = await sink.get_message()
      await emit.event('notification', message)
  finally:
    broadcasting.close_sink(sink)


def pavao_endpoint():
  return {
    'method': 'GET',
    'path': '/notifications/stream',
    'processor': process
  }
