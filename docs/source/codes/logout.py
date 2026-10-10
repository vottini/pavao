
import pavao

delete_refresh = pavao.include('queries/delete_refresh.sql')

async def process(server, response, db_connection, auth_data):
  server.authorizer.blacklist(auth_data)

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
