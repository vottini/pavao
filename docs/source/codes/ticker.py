
async def process(broadcasting):
  await broadcasting.write_message('ticks', 'tick')
  yield


def pavao_task():
  return {
    'name': 'ticker',
    'schedule': '* * * * *',
    'processor': process
  }
