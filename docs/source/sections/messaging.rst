
Inter-module Messaging
**********************

pavao includes an asynchronous publish/subscribe bus called the **broadcaster**. It lets
any module — endpoint, task, or service — publish messages on a named topic and any other
module subscribe to receive them. The broadcaster is injected as ``broadcasting`` wherever
the parameter is declared.

Core API
========

Opening a sink
--------------

A sink is a per-subscriber queue attached to a topic. Any message published on a topic is
delivered to every sink currently open on it.

.. code-block:: python

   sink = broadcasting.open_sink('topic_name')

A single module can hold multiple sinks open across different topics simultaneously.

Receiving messages
------------------

.. code-block:: python

   message = await sink.get_message()

``get_message()`` is a coroutine that suspends until a message arrives. It returns
messages in the order they were published.

Publishing messages
-------------------

.. code-block:: python

   await broadcasting.write_message('topic_name', payload)

``payload`` can be any Python object. All sinks currently open on ``topic_name`` receive
a reference to it.

Closing a sink
--------------

.. code-block:: python

   broadcasting.close_sink(sink)

A sink must be closed when it is no longer needed. Messages published after closing are
not queued. Forgetting to close a sink causes unconsumed messages to accumulate.

Task state topics
-----------------

For every registered task and service, pavao automatically publishes lifecycle events on
the topic ``taskState:<id>``, where ``<id>`` is the task's integer identifier from the
``task`` table. Three kinds of messages are published:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Message
     - Meaning
   * - ``"STARTED"``
     - The processor has begun executing
   * - ``"OUTPUT:<value>"``
     - The processor yielded a non-``None`` value
   * - ``"FINISHED"``
     - The processor has completed (successfully or not)

Any module can subscribe to these topics to react to task lifecycle events in real time.
To find the numeric ID of a task, query the ``task`` table via ``internal_db``
(see :doc:`background`).

An SSE endpoint that streams live output from a specific task:

.. code-block:: python

   import pavao

   @pavao.generates_sse()
   async def process(emit, broadcasting, path_variables):
     task_id = path_variables['id']
     sink = broadcasting.open_sink(f'taskState:{task_id}')
     await emit.headers()
     try:
       while True:
         message = await sink.get_message()
         await emit.event('taskState', message)
         if message == 'FINISHED':
           break
     finally:
       broadcasting.close_sink(sink)

   def pavao_endpoint():
     return {
       'method': 'GET',
       'path': '/tasks/{id:int}/stream',
       'processor': process
     }

Server shutdown
---------------

pavao publishes a sentinel on the reserved topic ``pavao.SHUTDOWN_TOPIC``
(``"PAVAO.SHUTDOWN"``) before the process stops. Modules that need to react to shutdown
can open a sink on this topic and await it. The ``generates_sse`` decorator does this
automatically, sending a ``serverShutdown`` event to all connected clients.

Examples
========

Endpoint writing to a topic
----------------------------

An HTTP endpoint can publish a message in response to a request. Any subscriber on that
topic receives it immediately.

.. literalinclude:: ../codes/broadcast_endpoint.py
   :language: python

Service listening to a topic
-----------------------------

A background service opens a sink at startup and processes messages as they arrive. The
``on_finish`` callback ensures the sink is closed if the service stops:

.. literalinclude:: ../codes/monitor.py
   :language: python

Bridging to a live SSE stream
------------------------------

The most common pattern is a pipeline: something publishes on a topic, and an SSE
endpoint forwards each message to connected clients.

.. literalinclude:: ../codes/live_feed.py
   :language: python

Multiple clients can connect to the same SSE endpoint simultaneously. Each connection
gets its own sink, so every client receives all messages published on the topic while
they are connected:

.. literalinclude:: ../codes/multi_sse.py
   :language: python

Full pipeline example
---------------------

Combining the above, a scheduled task publishes a heartbeat every minute, and any
connected browser receives it in real time:

.. code-block:: python

   # ticker.py — runs every minute via cron
   async def process(broadcasting):
     await broadcasting.write_message('ticks', 'tick')
     yield

   def pavao_task():
     return {
       'name': 'ticker',
       'schedule': '* * * * *',
       'processor': process
     }

.. code-block:: python

   # live_feed.py — SSE endpoint
   import pavao

   @pavao.generates_sse()
   async def process(emit, broadcasting):
     sink = broadcasting.open_sink('ticks')
     await emit.headers()
     try:
       while True:
         message = await sink.get_message()
         await emit.event('tick', message)
     finally:
       broadcasting.close_sink(sink)

   def pavao_endpoint():
     return {
       'method': 'GET',
       'path': '/live',
       'processor': process
     }

The task and the SSE endpoint are completely decoupled: neither knows the other exists.
New subscribers can be added — logging services, audit trails, other SSE streams — without
modifying the publisher.
