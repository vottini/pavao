
import pavao

localization_dir = pavao.path_to("localization")
localizer = pavao.ModuleLocalizer("myapp", localization_dir)


async def process(broadcasting):
  await broadcasting.write_message('reports', 'report generated')
  yield 'done'


def pavao_task():
  return {
    'package': localizer.map('PACKAGE'),
    'name': localizer.map('GENERATE_REPORT'),
    'schedule': '0 6 * * *',
    'processor': process
  }
