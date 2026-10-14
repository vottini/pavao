
# pavao

[![Documentation Status](https://readthedocs.org/projects/pavao/badge/?version=latest)](http://pavao.readthedocs.io/?badge=latest)
[![Upload Python Package](https://github.com/vottini/pavao/actions/workflows/pypi-publish.yml/badge.svg)](https://github.com/vottini/pavao/actions/workflows/pypi-publish.yml)
[![codecov](https://codecov.io/github/vottini/pavao/graph/badge.svg?token=N2H2WJ0SC5)](https://codecov.io/github/vottini/pavao)

**pavao** (from "Pavão", Portuguese for *peacock*) is a Python ASGI framework built
on two ideas that work together.

One is **modularity**: point pavao at a directory of Python files and it discovers and
serves every endpoint module it finds there. Adding a new endpoint means dropping a file
into the directory; removing one means deleting it. Nothing else in the application needs
to change.

The other is **name-based dependency injection**: instead of importing or constructing the
objects your endpoint needs, you just declare them as arguments to your handler function.
pavao uses the names of the parameters to deliver the correct objects where they are requested.
Parameters are instantiated on demand — if a module does not declare `db_connection`,
no database connection is created for it.

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

## Going further

Both pillars extend naturally as an application grows.

On the modularity side, modules can be organised into subdirectories, share helper code through plain Python imports, and be hot-reloaded on change without restarting the server. Because each endpoint lives in its own file, the reload boundary is exactly the unit of work: edit one handler, save, and only that module is reloaded — the rest of the application keeps running. Alongside endpoint modules, the same directory can contain scheduled task modules (`pavao_task()`) and always-on background service modules (`pavao_service()`).

On the injection side, the built-in injectables — `request`, `response`, `path_variables`, `broadcasting`, and others — cover the common cases. The set is open: custom suppliers placed in a foundation directory can introduce new named parameters, making application-specific resources (database connections, caches, auth tokens) available to any module that declares them.

Crucially, injection applies to descriptor functions too, not only to processors. A module can declare a dependency in its `pavao_endpoint()` function and use it to decide whether to register at all, or to configure the endpoint based on runtime state. Each function asks for exactly what it needs — nothing is shared implicitly.

```python
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
```

The descriptor receives `loaded_settings` and checks a configuration flag — if the v1 API is disabled the module is quietly skipped. Otherwise the endpoint is registered, and its processor independently declares `response`, `db_connection`, and `auth_data`. Each function asks for exactly what it needs at the time it needs it.

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

Full documentation is available at [pavao.readthedocs.io](https://pavao.readthedocs.io/en/latest/).

## License

MIT
