.. pavao documentation master file, created by
   sphinx-quickstart on Wed Aug 28 01:10:55 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

pavao
=====

**pavao** (from "Pavão", portuguese for *peacock*) is an Python ASGI framework
based on a modular architecture, where each endpoint (module) is placed in its own file
and loaded at runtime. The endpoint's servicing function can accept a set of possible
parameters (which can be extended by user code) and have them automatically injected when
that endpoint is accessed. Alongside HTTP endpoints, pavao also offers support for
tasks (scheduled routines) and services (always on routines) modules.

As an example, here's a simple "/hello" endpoint that returns a "World" string:

.. literalinclude:: codes/hello.py
  :language: python

To start servicing this endpoint, one can simply save it to a file inside a
directory of modules, say "modules/hello.py" and then run pavao on this
directory:

.. code-block:: console

  $ python -m pavao --execute modules

Finally, for a more complex module example, here's **pavao-auth**'s "/logout" endpoint:

.. literalinclude:: codes/logout.py
  :language: python

This last code has a lot going on, but the important tidbit here is
the use of the **pavao_endpoint()** method, which must declare, minimaly,
the endpoint's path, HTTP method and servicing function.

Besides its modular architecture, **pavao** bundles the following features:

- Typed URL path variables and URL parameters
- Schema based YAML configuration with support for environment variables
- Lazy instantiation of user defined module parameters, allowing pre and post-processing
- Endpoint access filtering with parameter injection support
- Facilities for response internationalization
- Asynchronous inter-module communication bus
- Hot-reloading of modules on change
- Typed JSON parsing and serialization
- Server Sent Event (SSE) support

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   sections/declaration
   sections/running
   sections/parameters
   sections/suppliers
   sections/filtering
   sections/json
   sections/broadcasting
   sections/sse
   sections/i18n
   sections/tasks

