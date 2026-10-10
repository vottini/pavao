
Suppliers & Filters
*******************

Suppliers extend the set of injectable parameters available to endpoints, tasks, services,
and descriptor functions. The built-in SQLite supplier, for example, makes ``task_store``
and ``stored_settings`` available to any module that declares them.

Custom suppliers and filters are placed in the foundation directory (passed via
``--foundation``) and are loaded before any modules. A supplier is defined by subclassing
``pavao.ParameterSupplier``; a filter by subclassing ``pavao.RequestFilter``.

.. _foundation:

Writing a supplier
==================

A supplier subclasses ``pavao.ParameterSupplier`` and overrides up to four methods:

``configure(self, loaded_settings)``
  Called once at startup. Receives ``loaded_settings`` directly — not through DI. Use
  this to read settings and initialise synchronous shared resources.

``parameters_supplied(self)``
  Returns a dict mapping parameter name to a ``[constructor, destructor]`` pair. The
  constructor is an async callable that returns the value to inject; the destructor is
  called after the request completes, or ``None`` if no cleanup is needed. Returning an
  empty dict disables the supplier entirely — the idiomatic way to make a supplier
  opt out based on configuration (e.g. a missing config block meaning the feature is
  not in use).

``async initialize(self)``
  Called after all suppliers have been configured. Participates in DI: can declare any
  parameter provided by **other suppliers** as arguments — pavao resolves them before
  calling ``initialize()``, respecting inter-supplier dependencies. ``loaded_settings``
  and request-time parameters are **not** available here; use ``configure()`` for settings.

``async shutdown(self)``
  Called when the server is shutting down. No parameters; use instance state set during
  ``configure()`` or ``initialize()``.

Supplier with constructor and destructor
-----------------------------------------

When a parameter represents a resource that must be acquired per-request and released
afterwards — such as a database connection from a pool — the ``parameters_supplied()``
dict accepts a ``[constructor, destructor]`` pair instead of ``[constructor, None]``.
pavao calls the destructor automatically after the request completes, whether it succeeded
or not.

The following supplier (taken verbatim from the ``pavao-postgres`` example) adds
``pg_pool`` (shared across requests) and ``pg_connection`` (acquired and released per
request) to the injectable parameter set:

.. literalinclude:: ../codes/postgres_supplier.py
   :language: python

The ``configure()`` method reads from ``application.yml``:

.. code-block:: yaml

   pavao:
     database:
       postgresql:
         host: localhost
         port: 5432
         database: mydb
         user: myuser
         password: ${DB_PASSWORD}

``pavao.path_to()``
-------------------

``pavao.path_to(name)`` returns the absolute path to a file or directory located next to
the calling module's own file. It is the idiomatic way to reference assets — SQL files,
message directories, templates — that live alongside a supplier or module:

.. code-block:: python

   import pavao

   sql_query = pavao.include(pavao.path_to('queries/get_user.sql'))
   localizer = pavao.ModuleLocalizer('auth', pavao.path_to('messages'))

Reading configuration
=====================

``loaded_settings`` is an injectable available to any descriptor, processor, supplier, or
filter. It exposes a single method:

.. code-block:: python

   value = loaded_settings.get_setting(entry, schema)

``entry`` is a dot-separated key path (e.g. ``'api.v1.enabled'``). ``schema`` describes
the expected type and, if the key is absent, the default value:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Schema form
     - Meaning
   * - ``str``, ``int``, ``bool``, …
     - Required field of that type; raises ``ConfigException`` if absent
   * - ``"default"`` / ``True`` / ``42`` / …
     - Optional field; if absent, returns the schema value itself; type is inferred from it
   * - ``{'key': schema, …}``
     - Nested structure; each key is validated against its own schema
   * - ``[schema]``
     - List of values, each validated against the inner schema

Keys that are absent and have a type (not a value) as schema are treated as required.
Keys that are absent and have a concrete value as schema return that value as the default
and also use it to infer the expected type for when the key *is* present.

Prefer structured blocks over atomic lookups
--------------------------------------------

The recommended style is to fetch an entire configuration block in one call rather than
making individual dotted lookups for each key. This keeps the schema co-located, makes
defaults easy to scan, and results in cleaner YAML:

.. code-block:: yaml

   # application.yml
   myservice:
     url: https://api.example.com
     timeout: 10
     retries: 3

.. code-block:: python

   _schema = {
     'url':     str,
     'timeout': 10,
     'retries': 3,
   }

   class MySupplier(pavao.ParameterSupplier):
     def configure(self, loaded_settings):
       self.config = loaded_settings.get_setting('myservice', _schema)

Avoid spreading related settings across multiple atomic calls:

.. code-block:: python

   # avoid
   self.url     = loaded_settings.get_setting('myservice.url', str)
   self.timeout = loaded_settings.get_setting('myservice.timeout', 10)

The built-in postgres supplier (see above) follows this pattern: it reads the entire
``pavao.database.postgresql`` block in one call and receives a fully validated dict.

Endpoint and task descriptors can also declare ``loaded_settings`` to make registration
conditional on a configuration value, as shown in the logout example on the overview page.

Writing a filter
================

Filters are classes that run before a processor to decide whether a request is allowed to
proceed. A filter is defined by subclassing ``pavao.RequestFilter`` and overriding two
methods:

``enabled(self, endpoint_specs)``
  Called once per endpoint at startup. Return ``True`` if this filter should apply to that
  endpoint. ``endpoint_specs`` is the full descriptor dict, so any custom field (``'public'``,
  ``'roles'``, etc.) can be inspected here.

``allow(self, request)``
  Called on every request that reaches a filtered endpoint. Return ``False`` to stop
  processing and return a 403.

Both methods participate in DI and can declare any injectable parameter as arguments.

.. code-block:: python

   import pavao

   class AuthFilter(pavao.RequestFilter):

     def enabled(self, endpoint_specs):
       return endpoint_specs.get('auth_required', False)

     def allow(self, request):
       token = request.headers.get('authorization')
       return token is not None

Filters are registered by placing them in the foundation directory. Their execution order
is controlled by the ``pavao.filters.order`` key in ``application.yml`` — listed filters
run first in the declared order; any filters not listed run afterwards in discovery order:

.. code-block:: yaml

   pavao:
     filters:
       order:
         - AuthFilter
         - RateLimitFilter

In this example ``AuthFilter`` always runs before ``RateLimitFilter``. Any other filter
present in the foundation directory that is not listed runs after both, in the order it
was discovered.
