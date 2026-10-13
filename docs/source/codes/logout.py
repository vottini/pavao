
import pavao

delete_refresh = pavao.include('queries/delete_refresh.sql')

async def process(response, db_connection, auth_data):
  row = await db_connection.fetchrow(
    "SELECT id FROM pavao.refresh_token WHERE account = $1",
    auth_data.account_id)

  if row is None:
    response.set_status(404)
    return

  await db_connection.execute(
    delete_refresh,
    auth_data.account_id,
    auth_data.token)

  response.add_cookie(
    pavao.http.Cookie('token')
      .set_path('/refresh-token')
      .set_sameSite(pavao.http.SameSite.STRICT)
      .set_to_be_removed()
  )

  response.set_status(204)


def pavao_endpoint(loaded_settings):
  if not loaded_settings.get_setting('api.v1.enabled', True):
    return

  return {
    'method': 'DELETE',
    'path': '/v1/logout',
    'processor': process
  }
