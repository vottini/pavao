# pavao

**pavao** (from "Pavão", Portuguese for *peacock*) is a Python ASGI framework built on two ideas that work together.

One is **modularity**: point pavao at a directory of Python files and it discovers and serves every endpoint module it finds there. Adding a new endpoint means dropping a file into the directory; removing one means deleting it. Nothing else in the application needs to change.

The other is **name-based dependency injection**: instead of importing or constructing the objects your endpoint needs, you just declare them as arguments to your handler function. pavao uses the names of the parameters to deliver the correct objects where they are requested. Parameters are instantiated on demand — if a module does not declare `db_connection`, no database connection is created for it.

A minimal endpoint:

```python
def process(response):
    response.set_plain_text("World")

def pavao_endpoint():
    return {
        'method': 'GET',
        'path': '/hello',
        'processor': process
    }
```

## Quick start

```console
$ python -m venv .venv
$ source .venv/bin/activate
$ pip install pavao
$ mkdir modules
```

Save the example above as `modules/hello.py`, then:

```console
$ pavao-run modules/
```

Open `http://localhost:8000/hello` and you should see `World`.

## Features

- Point-and-serve module directory: endpoints, tasks, and services auto-discovered at startup
- Dependency injection by parameter name across all modules
- Typed URL path variables and URL query parameters
- Schema-based YAML configuration with environment variable substitution
- Endpoint access filtering with full DI support
- Asynchronous inter-module communication bus
- Scheduled tasks (cron-style) and always-on background services
- Typed JSON parsing and serialization via [jsonbp](https://github.com/vottini/jsonbp)
- Server-Sent Events (SSE) with heartbeat and disconnection support
- Hot-reloading of modules on file change
- Response internationalization
- Extension management via `pavao-pkg`

## Documentation

Full documentation is available at [vottini.github.io/pavao](https://vottini.github.io/pavao).

## License

MIT
