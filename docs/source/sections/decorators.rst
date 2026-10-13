
Request & Response Decorators
******************************

pavao provides three decorators that can be applied to processor functions to handle
common request/response patterns. Each decorator integrates with the DI system: it adds
the parameters it needs to the function's visible signature so that the framework can
inject them correctly, even when decorators are stacked on the same processor.

accepts_parameters
==================

``@pavao.accepts_parameters`` validates and parses URL query parameters, then injects
them as a ``parameters`` dict. The decorator takes a specification dict that maps
parameter names to their types and optional defaults.

.. literalinclude:: ../codes/search.py
   :language: python

Each entry in the specification dict can be:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Specification
     - Meaning
   * - ``'name': SomeType``
     - Required parameter of that type; returns 400 if absent
   * - ``'name': default_value``
     - Optional parameter; the type is inferred from the default value
   * - ``'name': [SomeType]``
     - Required comma-separated list of that type

If a required parameter is missing or a value cannot be converted to the declared type,
pavao returns a 400 response with a localized error message.

accepts_json
============

``@pavao.accepts_json`` validates an incoming JSON request body against a
`jsonbp <https://github.com/vottini/jsonbp>`_ schema and injects the parsed result as
``parsed_json``. Keys are automatically converted to snake_case and the result is a plain
Python object with attribute access.

.. literalinclude:: ../codes/item_create.py
   :language: python

The schema can be provided inline via ``string_blueprint`` or loaded from a file via
``file_blueprint``. If the request's ``Content-Type`` is not ``application/json``, or if
the body does not match the schema, pavao returns a 400 response with a localized error
description. No code in the processor runs in either case.

Additional options:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Parameter
     - Description
   * - ``with_root``
     - Select a named root type from the schema
   * - ``array_root``
     - Expect a JSON array at the top level
   * - ``min_length`` / ``max_length``
     - Constrain the number of array elements (default 0 / 1024)

generates_json
==============

``@pavao.generates_json`` serializes the processor's return value as a JSON response
body. The processor sets the response status code and returns a plain dict or object;
the decorator serializes it using the schema that matches that status code.

.. literalinclude:: ../codes/item_get.py
   :language: python

When used together with ``@pavao.accepts_json``, ``@pavao.generates_json`` must be the
outermost decorator so it can capture the return value before the framework transmits the
response:

.. code-block:: python

   @pavao.generates_json(string_blueprint=item_schema)
   @pavao.accepts_json(string_blueprint=input_schema)
   async def process(response, parsed_json):
     ...

When a single ``string_blueprint`` or ``file_blueprint`` is provided, it is used for all
non-error status codes. Error status codes automatically use pavao's built-in error schema
(``{ error, description, timestamp }``). Returning ``None`` leaves the response body
empty.

For endpoints that return different shapes for different status codes, the ``dispatchers``
parameter accepts a list of rules:

.. code-block:: python

   @pavao.generates_json(dispatchers=[
     {'status': 200, 'string': success_schema},
     {'status': 404, 'string': not_found_schema},
   ])
   async def process(response, path_variables):
     ...

Each rule requires exactly one of ``status``, ``statuses`` (a list), or ``predicate`` (a
callable that receives the status code and returns a bool), plus a ``string`` or ``file``
schema.

generates_sse
=============

``@pavao.generates_sse`` turns a processor into a Server-Sent Events stream. The
decorated function receives an ``emit`` object and runs alongside two background tasks
that monitor for client disconnection and server shutdown.

.. literalinclude:: ../codes/live_feed.py
   :language: python

``emit`` exposes the following methods:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Method
     - Description
   * - ``await emit.headers(status=200, headers=None)``
     - Flush the HTTP response headers to the client. Called at most once; subsequent
       calls are no-ops. Any first call to ``event()`` or ``message()`` flushes headers
       automatically if not already done.
   * - ``await emit.event(event_type, data=None)``
     - Send a named SSE event, optionally with a data payload. The client receives it via
       ``EventSource.addEventListener(event_type, ...)``.
   * - ``await emit.message(data)``
     - Send an unnamed SSE event (``data:`` field only, no ``event:`` line). The client
       receives it via ``EventSource.onmessage``. Use ``emit.event()`` when the client
       needs to distinguish between different event types.

When the client disconnects unexpectedly, any callback registered with
``emit.on_disconnection(callback)`` is called before the processor task is cancelled.
When the server shuts down, a ``serverShutdown`` event is sent automatically to the client
and the processor task is cancelled.

The decorator accepts three optional parameters:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Parameter
     - Description
   * - ``send_heartbeats``
     - Send periodic ``heartBeat`` events to keep the connection alive (default ``True``)
   * - ``initial_heartbeat_delay_secs``
     - Seconds before the first heartbeat (default 20)
   * - ``heartbeat_interval_secs``
     - Seconds between subsequent heartbeats (default 20)
