
Background Work
***************

Endpoints are the primary kind of module in a pavao application, but two other module
types fill out the runtime picture: scheduled tasks, which run on a cron schedule, and
background services, which run continuously alongside the endpoint server. Both use the
same descriptor-and-processor pattern as endpoints, and both participate fully in
dependency injection.

Scheduled tasks
===============

A module that defines a ``pavao_task()`` descriptor is registered as a scheduled task. The
descriptor returns a dict with the following keys:

.. list-table::
   :header-rows: 1
   :widths: 20 10 70

   * - Key
     - Required
     - Description
   * - ``name``
     - yes
     - Unique name for the task
   * - ``schedule``
     - yes
     - Cron expression (``"minute hour day month weekday"``)
   * - ``processor``
     - yes
     - Async generator function to run on each scheduled tick
   * - ``package``
     - no
     - Optional grouping label. Stored alongside the task name and useful for organising
       tasks by application area in admin interfaces or execution logs.

The processor is an **async generator** that runs to completion on each scheduled tick.
Each ``yield value`` emits an output: the value is stored in the internal execution log,
published on a per-task broadcasting topic (``taskState:<id>``), and passed to any
registered output callback. Yielding ``None`` (a bare ``yield``) produces no logged output. It is required when the
processor has nothing meaningful to report but still needs the ``yield`` keyword to
satisfy Python's async generator protocol — without at least one ``yield``, the function
is treated as a plain coroutine and rejected at registration. The
``@pavao.silent_generator`` decorator handles this automatically: it wraps a plain
``async def`` and appends the silent ``yield`` on its behalf, so the processor can be
written as a normal coroutine.

The following parameters are available to task processors, in addition to all supplier-provided parameters:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``broadcasting``
     - The application-wide message bus. Publish events or subscribe to topics.

.. literalinclude:: ../codes/ticker.py
   :language: python

Each ``yield value`` also publishes a message on the ``taskState:<id>`` broadcasting
topic, where ``<id>`` is the integer assigned to that task at registration time. The id
can be retrieved via ``await task_store.list_tasks()``, which returns the id alongside
the task's package, name, and enabled state. Subscribing to ``taskState:<id>`` lets any
part of the application react to task output in real time — for example, forwarding it to
a connected SSE client.

Execution metadata — start time, end time, success or failure, and all yielded outputs —
is automatically persisted to the internal SQLite database, giving every task a built-in
audit trail without any extra code.

Localizing task names
---------------------

The ``name`` and ``package`` fields accept either a plain string or a ``LazyLocalizer``
produced by ``ModuleLocalizer.map()``. When pavao displays task information — in the
internal database, in broadcasting messages, or in any admin interface — it calls
``.localize()`` on those fields with the viewer's language priority. This means the same
task can present itself in different languages to different clients without any extra logic
in the processor.

.. literalinclude:: ../codes/localized_task.py
   :language: python

The corresponding ``localization/en_US.ini`` alongside the task file would contain:

.. code-block:: ini

   PACKAGE="My Application"
   GENERATE_REPORT="Generate daily report"

Like endpoint descriptors, ``pavao_task()`` itself can receive injected parameters. This
allows the task's schedule or name to be sourced from configuration at registration time:

.. code-block:: python

   def pavao_task(loaded_settings):
     schedule = loaded_settings.get_setting('mytask.schedule', '0 * * * *')
     return {
       'name': 'my_task',
       'schedule': schedule,
       'processor': process
     }

Background services
===================

A module that defines a ``pavao_service()`` descriptor is registered as a background
service (daemon). The descriptor returns a dict with the following keys:

.. list-table::
   :header-rows: 1
   :widths: 20 10 70

   * - Key
     - Required
     - Description
   * - ``name``
     - yes
     - Unique name for the service
   * - ``processor``
     - yes
     - Async generator function to run continuously
   * - ``package``
     - no
     - Optional grouping label, same as for scheduled tasks.

Unlike scheduled tasks, a service starts once at application startup and is expected to
run indefinitely. If it terminates unexpectedly, pavao restarts it automatically after a
short delay.

The processor is an async generator that runs continuously. ``yield value`` behaves
identically to scheduled tasks: the value is persisted to the execution log and published
on the service's ``taskState:<id>`` broadcasting topic, where ``<id>`` is the same
integer assigned at registration and queryable via ``task_store``. A bare ``yield`` produces no logged output and serves the same purpose as in scheduled
tasks: satisfying the async generator protocol when there is nothing to report. The
``@pavao.silent_generator`` decorator is available here too for services that never need
to emit output. pavao does not pause between yields — the generator drives its own pace.

The following parameters are available to service processors, in addition to all supplier-provided parameters:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``broadcasting``
     - The application-wide message bus. Publish events or subscribe to topics.
   * - ``on_finish``
     - A callable that accepts a callback. The callback is invoked when the service
       terminates (whether normally or by error), making it a reliable place for cleanup.

.. literalinclude:: ../codes/monitor.py
   :language: python

Like ``pavao_task()``, ``pavao_service()`` can also declare injected parameters, making
conditional registration or configuration-driven setup possible using the same pattern.

Both tasks and services can publish and subscribe to topics through the ``broadcasting``
parameter. See :doc:`messaging` for the full inter-module messaging API.

Internal database
=================

pavao maintains an internal database used to track task and service execution. It is
accessed through two injectables:

- ``task_store`` — an instance of ``pavao.TaskStore``, used by the framework to record
  runs and available to user modules for querying execution history
- ``stored_settings`` — an instance of ``pavao.StoredSettings``, a typed key-value store
  for persisting small pieces of application state across restarts

The default implementation uses SQLite (``pavao.db``). SQLite requires no external
infrastructure and is a good fit for single-process deployments, development, and
applications that do not already operate a database server.

Replacing the backend
---------------------

Both ``task_store`` and ``stored_settings`` are backed by abstract base classes
(``pavao.TaskStore`` and ``pavao.StoredSettings``) rather than the SQLite connection
directly. To swap the backend — for example to consolidate with an existing PostgreSQL
database, or to support horizontal scaling across multiple processes — disable the
built-in supplier and register your own:

.. code-block:: yaml

   pavao:
     database:
       sqlite:
         enabled: false

Then write a supplier that subclasses both ABCs and registers them under the same
parameter names:

.. code-block:: python

   import pavao

   class MyTaskStore(pavao.TaskStore):
     async def register_task(self, name, package): ...
     async def start_execution(self, task_id, started_at): ...
     async def record_output(self, execution_id, instant, content, is_error): ...
     async def finish_execution(self, execution_id, ended_at, success): ...
     async def list_tasks(self): ...
     async def get_executions(self, task_id, day=None): ...
     async def get_outputs(self, execution_id): ...

   class MyStoredSettings(pavao.StoredSettings):
     async def get(self, key): ...
     async def set(self, key, value): ...

   class MyBackendSupplier(pavao.ParameterSupplier):
     async def init(self, loaded_settings):
       self.store = MyTaskStore(...)
       self.settings = MyStoredSettings(...)

     def parameters_supplied(self):
       return {
         'task_store':       [lambda: self.store, None],
         'stored_settings':  [lambda: self.settings, None],
       }

Place this file in the foundation directory and the framework will use it in place of
SQLite automatically.

Schema
------

The default SQLite backend uses three tables:

**task** — one row per registered task or service.

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Column
     - Description
   * - ``id``
     - Integer primary key; also used as the task's broadcasting topic suffix
   * - ``package``
     - Optional grouping label set in the descriptor dict
   * - ``name``
     - The name declared in the descriptor dict
   * - ``enabled``
     - Whether the task is currently enabled (can be toggled at runtime)

**task_execution** — one row per run.

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Column
     - Description
   * - ``id``
     - Integer primary key
   * - ``task``
     - Foreign key to ``task.id``
   * - ``execution_start``
     - Timestamp when the run began
   * - ``execution_end``
     - Timestamp when the run finished
   * - ``success``
     - Boolean; ``False`` if the processor raised an exception or was cancelled

**task_output** — one row per yielded value.

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Column
     - Description
   * - ``execution``
     - Foreign key to ``task_execution.id``
   * - ``instant``
     - Timestamp of the yield
   * - ``error``
     - Boolean; ``True`` when the row records an exception rather than a yield
   * - ``content``
     - String representation of the yielded value

Querying execution history
--------------------------

``task_store`` is a standard injectable, so any endpoint can query execution history
through it. Three read methods are available:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Method
     - Description
   * - ``await task_store.list_tasks()``
     - All registered tasks: ``id``, ``package``, ``name``, ``enabled``
   * - ``await task_store.get_executions(task_id, day=None)``
     - Completed executions for a task: ``id``, ``success``, ``execution_start``,
       ``execution_end``. Pass a ``datetime.date`` to filter by day.
   * - ``await task_store.get_outputs(execution_id)``
     - Output rows for one execution: ``instant``, ``error``, ``content``

The following endpoint returns the full run history and output for a named task:

.. literalinclude:: ../codes/task_history.py
   :language: python

Persisted settings
------------------

The ``stored_settings`` injectable provides a typed key-value store backed by the same
database, useful for persisting small pieces of application state across restarts:

.. code-block:: python

   async def process(stored_settings):
     await stored_settings.set('last_run_count', 42)
     count = await stored_settings.get('last_run_count')  # returns int 42
