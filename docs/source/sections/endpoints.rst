
Endpoints & the DI Model
************************

Module files
============

pavao receives a directory of Python scripts to serve. It adds that directory to the Python
search path and then scans it recursively, executing every script it finds. Files that
define a function named ``pavao_endpoint()`` and return a non-``None`` dict are registered
as HTTP endpoints. Files without that function, or whose descriptor returns ``None``, are
simply available for import by other modules — they are part of the same application but do
not expose any routes.

A minimal module directory might look like this:

.. code-block:: text

   modules/
   ├── hello.py
   ├── stamped_hello.py
   └── timestamp.py

``timestamp.py`` contains shared logic. ``hello.py`` and ``stamped_hello.py`` each declare
an endpoint:

.. literalinclude:: ../codes/timestamp.py
   :language: python

.. literalinclude:: ../codes/stamped_hello.py
   :language: python

Because pavao adds the modules directory to the Python path, ``timestamp`` can be imported
directly. If ``timestamp.py`` is modified on disk, ``stamped_hello.py`` will be reloaded
along with it — see :ref:`hot-reload` for details.

The descriptor function
=======================

The descriptor function must be named ``pavao_endpoint()`` and must return a dict
containing at least the following keys:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Key
     - Description
   * - ``method``
     - HTTP method (``'GET'``, ``'POST'``, ``'PUT'``, ``'DELETE'``, etc.)
   * - ``path``
     - URL path, optionally containing typed wildcards (see below)
   * - ``processor``
     - Function to call when this endpoint is accessed

Any additional keys in the dict are passed through untouched and become accessible to
filters as ``endpoint_specs`` (see :ref:`filters`). This is how application-level concerns
like visibility or required permissions are attached to an endpoint without the framework
needing to know about them.

The descriptor function itself participates in dependency injection. It can declare any
injectable parameter as an argument, and pavao will resolve it before calling the function.

The following parameters are available to descriptor functions:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``loaded_settings``
     - The parsed ``application.yml``. Always available. Use it to make registration
       conditional on a configuration value or to read settings at startup time.
   * - *(supplier params)*
     - Every parameter registered by a supplier (``task_store``, ``stored_settings``,
       custom suppliers, etc.) is available.

Note that request-time parameters (``request``, ``response``, ``path_variables``, etc.)
are **not** available to descriptor functions — they do not exist until a request arrives.

Missing and unavailable dependencies
--------------------------------------

It is important to understand how pavao handles dependencies that cannot be satisfied,
because the behaviour differs between descriptors and processors.

If a parameter has **no registered supplier at all**, pavao raises an error before the
descriptor is ever called. For descriptor functions this causes the module to be silently
skipped with a warning in the log. For processor functions the same check happens at
startup: the endpoint is disabled and a warning is logged. In neither case does the
function receive a value — it is simply never invoked.

The ``if db_connection is None: return None`` pattern seen in the ``/logout`` example on
the overview page is a **different** scenario. There, a supplier *is* registered for
``db_connection``, but it is designed to return ``None`` when the underlying resource is
unavailable — for example, when the database is not configured in ``application.yml``.
The descriptor receives ``None``, checks for it explicitly, and returns ``None`` to
opt out of registration. This is a deliberate design choice in the supplier, not an
automatic framework behaviour.

In summary:

- Unknown parameter (no supplier) → module/endpoint disabled, warning logged, function never called
- Supplier returns ``None`` → function is called with ``None``, can handle it explicitly

A supplier that wants to allow graceful opt-out should return ``None`` from its
constructor when the resource is not available, rather than omitting the parameter
entirely. Omitting it causes a hard skip; returning ``None`` gives the descriptor a
chance to decide.

Custom fields and public endpoints
-----------------------------------

Extra keys in the descriptor dict are not interpreted by pavao — they are preserved and
forwarded to every filter's ``enabled()`` method as part of ``endpoint_specs``. This
makes the descriptor dict the natural place to express endpoint-level policy.

A common pattern is a ``'public'`` flag that marks endpoints that should bypass
authentication:

.. literalinclude:: ../codes/public_endpoint.py
   :language: python

A filter can then check for this flag in ``enabled()`` and opt out entirely for public
endpoints:

.. literalinclude:: ../codes/auth_filter.py
   :language: python

Any field works — ``'roles'``, ``'rate_limit'``, ``'deprecated'`` — as long as the
filters that care about them know the key name. Fields that no filter reads are silently
ignored.

Path variables
==============

A path can contain one or more wildcards. Each wildcard is a name enclosed in braces,
optionally followed by a colon and a Python built-in type:

.. code-block:: text

   /greet/{name}/{age:int}

pavao will try to convert each wildcard segment to the declared type. If the conversion
fails, that endpoint is skipped during routing and a 404 is returned if no other endpoint
matches:

.. code-block:: text

   GET /greet/Mary/Jane    → 404 (Jane cannot be converted to int)
   GET /greet/Mary/23.55   → 404 (23.55 cannot be converted to int)
   GET /greet/Mary/6       → 200 OK

All matched wildcards are collected into the ``path_variables`` dict and injected into
the processor function:

.. literalinclude:: ../codes/greet.py
   :language: python

The processor function
======================

The processor function handles each incoming request. It can be a regular function or an
``async`` function if it needs to use ``await``. It declares its dependencies by parameter
name; pavao injects the matching objects at request time.

The following parameters are always available in endpoint processors:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``request``
     - Parsed HTTP request: headers, cookies, source/destination addresses, query
       parameters.
   * - ``response``
     - Response helper: set status code, write cookies, send plain text or JSON. pavao
       transmits the response automatically when the processor returns.
   * - ``receive``
     - The raw ASGI `receive callable
       <https://asgi.readthedocs.io/en/latest/specs/www.html#request-receive-event>`_,
       for reading a streaming request body.
   * - ``path_variables``
     - Dict of wildcard values extracted from the URL path, converted to their declared
       types. Empty dict if the path has no wildcards.
   * - ``broadcasting``
     - The application-wide message bus. See :doc:`messaging` for the full API.
   * - ``endpoint_specs``
     - The full descriptor dict returned by ``pavao_endpoint()``, including any custom
       fields. Useful when a processor needs to read its own metadata.
   * - ``server``
     - The running ``pavao.Server`` instance, for accessing application-level state.

In addition, every parameter registered by a supplier (``task_store``, ``stored_settings``,
and any custom supplier) is available to endpoint processors.

.. _filters:

Filters
=======

Filters are classes that run before a processor to decide whether a request is allowed to
proceed. They receive the same dependency injection as processors, and they can inspect
``endpoint_specs`` — the full descriptor dict — to decide whether they apply to a given
endpoint at all.

A filter is defined by subclassing ``pavao.RequestFilter`` and overriding two methods:

.. code-block:: python

   import pavao

   class AuthFilter(pavao.RequestFilter):

     def enabled(self, endpoint_specs):
       return endpoint_specs.get('auth_required', False)

     def allow(self, request):
       token = request.headers.get('authorization')
       return token is not None

``enabled()`` is called once per endpoint at startup to decide whether this filter applies
to that endpoint at all. ``allow()`` is called on every request that reaches a filtered
endpoint; returning ``False`` stops processing and returns a 403. Both methods participate
in DI and can declare any injectable parameter as arguments.

Filters are registered by placing them in a foundation directory and configuring their
order in ``application.yml``. See :ref:`foundation` for setup details.
