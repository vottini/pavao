
import pavao

_localizer = pavao.ModuleLocalizer('items', pavao.path_to('messages'))
_not_found = _localizer.map('ITEM_NOT_FOUND')


async def process(response, request, path_variables):
  item_id = path_variables['id']
  item = None  # ... fetch from storage ...

  if item is None:
    priority = request.parse_locale_priority()
    response.set_plain_text(_not_found.localize(priority))
    response.set_status(404)
    return

  response.set_plain_text(str(item))


def pavao_endpoint():
  return {
    'method': 'GET',
    'path': '/items/{id:int}',
    'processor': process
  }
