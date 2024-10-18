
message = """Grettings {name}!
You are now {age} years old.
In two years, you'll be {next_age} years old.
"""

def process(response, path_variables):
  next_age = path_variables['age'] + 2
  output = message.format(**path_variables, next_age=next_age)
  response.set_plain_text(output)


def pavao_endpoint():
  return {
    'method': 'GET',
    'path': '/greet/{name}/{age:int}',
    'processor': process
  }

