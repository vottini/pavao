
async def process(response, task_store, path_variables):
  task_name = path_variables['name']

  tasks = await task_store.list_tasks()
  task = next((t for t in tasks if t['name'] == task_name), None)

  if task is None:
    response.set_status(404)
    return

  executions = await task_store.get_executions(task['id'])
  lines = []

  for execution in executions:
    start = execution['execution_start']
    end = execution['execution_end']
    ok = 'ok' if execution['success'] else 'fail'
    outputs = await task_store.get_outputs(execution['id'])

    for output in outputs:
      lines.append(f"{start} → {end} ({ok}): [{output['instant']}] {output['content']}")

  response.set_plain_text('\n'.join(lines) if lines else 'No executions found')


def pavao_endpoint():
  return {
    'method': 'GET',
    'path': '/tasks/{name}/history',
    'processor': process
  }
