
import pavao

class AuthFilter(pavao.RequestFilter):

  def enabled(self, endpoint_specs):
    return not endpoint_specs.get('public', False)

  def allow(self, request):
    token = request.headers.get('authorization')
    if token is None:
      return False

    claims = self.jwt.validate_token(token)
    return claims is not None

  def __init__(self, jwt):
    self.jwt = jwt
