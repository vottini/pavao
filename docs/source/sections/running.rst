
Running & Configuration
***********************

Command line
============

pavao is invoked as a Python module. The only required argument is the path to the
directory of modules to serve:

.. code-block:: console

   $ python -m pavao modules/

Additional options:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Option
     - Description
   * - ``--config-file FILE``
     - Path to the YAML configuration file (default: ``application.yml``)
   * - ``--port PORT``
     - Port to listen on (default: ``8000``)
   * - ``--foundation DIR``
     - Directory containing custom suppliers and filters (see :doc:`foundation`)

Project layout
==============

A typical pavao project has the following structure:

.. code-block:: text

   my_project/
   ├── application.yml      ← configuration
   ├── foundation/          ← custom suppliers and filters (optional)
   │   └── db_supplier.py
   └── modules/             ← endpoint, task, and service modules
       ├── items/
       │   ├── get_item.py
       │   └── create_item.py
       └── shared/
           └── utils.py

The modules directory is added to the Python path, so files can import from each other
using plain ``import`` statements. Note that plain imports do not register a dependency
link — if a shared module changes, only that file is reloaded and its dependents are not.
Use ``pavao.from_module().import_item()`` instead when the reload should propagate (see
:ref:`hot-reload`).

Configuration
=============

pavao reads a YAML file (default: ``application.yml``) at startup. Values support
environment variable substitution with ``${VAR_NAME}`` syntax.

The following keys are recognised:

**Logging**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Key
     - Description
   * - ``pavao.logging.output``
     - Log file path (default: ``"pavao.log"``)
   * - ``pavao.logging.level``
     - One of ``FATAL``, ``ERROR``, ``WARN``, ``INFO``, ``DEBUG`` (default: ``INFO``)
   * - ``pavao.logging.persist``
     - Write logs to a file in addition to stdout (default: ``true``). Set to ``false``
       in containerized environments where stdout is collected externally.

**SQLite** (built-in database supplier)

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Key
     - Description
   * - ``pavao.database.sqlite.enabled``
     - Enable the SQLite supplier (default: ``true``)
   * - ``pavao.database.sqlite.persist``
     - Keep the database file between restarts (default: ``true``)
   * - ``pavao.database.sqlite.filename``
     - Database file path (default: ``"pavao.db"``)
   * - ``pavao.database.sqlite.trace``
     - Log all SQL statements (default: ``false``)

**CORS**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Key
     - Description
   * - ``pavao.http.CORS.origins``
     - List of allowed origins
   * - ``pavao.http.CORS.headers``
     - List of allowed request headers
   * - ``pavao.http.CORS.credentials``
     - Whether to allow credentials (default: ``false``)
   * - ``pavao.http.CORS.max_age``
     - Preflight cache duration in seconds

**Hot-reloading**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Key
     - Description
   * - ``pavao.hot_reload.enabled``
     - Enable file-system watching and hot-reloading (default: ``true``). Set to
       ``false`` in production or CI environments where restarts are controlled
       externally.

**Filters**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Key
     - Description
   * - ``pavao.filters.order``
     - Ordered list of filter class names; listed filters run first

A minimal configuration file:

.. code-block:: yaml

   pavao:
     logging:
       level: INFO
       persist: ${LOG_TO_FILE:-true}
     database:
       sqlite:
         filename: ${DB_PATH:-app.db}
     http:
       CORS:
         origins:
           - https://my-frontend.example.com

.. _hot-reload:

Hot-reloading
=============

The development loop with pavao is intentionally tight: edit a file, save it, and the
new version is live — no restart, no lost state, no waiting. Because each endpoint
already lives in its own file, the reload boundary matches the unit of work exactly.
Only the changed module is reloaded; connection pools, caches, and every other endpoint
keep running undisturbed.

pavao watches the modules directory for file changes using a background file-system
monitor. When a ``.py`` file is created, modified, or deleted, the affected module is
reloaded and its endpoints, tasks, or services are re-registered — without restarting the
process. Hot-reloading is enabled by default and should be disabled in production, where
restarts are controlled externally:

.. code-block:: yaml

   pavao:
     hot_reload:
       enabled: ${HOT_RELOAD:-true}

This allows the flag to be controlled by an environment variable, which is useful for
sharing the same ``application.yml`` across development and production environments.

Dependency links
----------------

Changes to a file only trigger a reload if pavao knows about the dependency. A dependency
link is registered whenever a module calls one of the following:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Call
     - Effect
   * - ``pavao.include(path)``
     - Reads the file content and links it to the calling module. When the file changes,
       the module is reloaded.
   * - ``pavao.path_to(path)``
     - Returns the absolute path and links the referenced file to the calling module.
       Useful for assets (SQL directories, message folders) that are opened lazily at
       request time.
   * - ``pavao.from_module(name).import_item(...)``
     - Imports an item from a sibling module and links that module to the caller. When
       the sibling changes, the caller is reloaded along with it.

Plain Python ``import`` statements do **not** register a dependency link. If module A
does ``import B`` and B changes on disk, A will not be reloaded automatically — only B
will. Use ``pavao.from_module`` instead of ``import`` when you need the reload chain to
propagate to dependents.

.. code-block:: python

   import pavao

   get_user_query = pavao.include('queries/get_user.sql')
   messages_dir   = pavao.path_to('messages')

   pavao.from_module('shared.utils').import_item('format_row')

   async def process(response, db_connection):
     rows = await db_connection.execute(get_user_query, ...)
     ...

If any of ``queries/get_user.sql``, the ``messages`` directory, or ``shared/utils.py``
change on disk, this module will be reloaded automatically.

Custom suppliers and filters are covered in :doc:`foundation`.
