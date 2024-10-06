
Module Declaration
******************

*pavao* receives a directory of Python scripts to execute, some
of these scripts actually declare endpoints, while others can simply contain
auxiliar code. In fact, *pavao* will include this directory in the python
search path, then proceed to execute all Python scripts inside it, recursively scanning
all the subdirectories. The scripts that have the method **pavao_endpoint()**
which effectively return a dictionary specifying an endpoint will be the ones
that *pavao* will serve to the outside.

To successfuly specify an endpoint, the dictionary returned from **pavao_endpoint()**
must include minimally the following fields:

| **method**: HTTP method of the endpoint
| **path**: HTTP path of the resource/functionaly
| **processor**: function to execute when this endpoint is accessed

The "/hello" endpoint given in the summary ilustrates this behavior:

.. literalinclude:: ../codes/hello.py
  :language: python

Suppose now that we wish to create another endpoint similar to "/hello" but
that includes the timestamp in the response. Let's say that the act of
obtaining this timestamp is a common functionality throughout our project and we want it
to be available to other modules, so this code should preferably reside
outside the endpoint file. We can proceed by creating a file named *timestamp.py*
inside our directory of modules with the following contents:

.. literalinclude:: ../codes/timestamp.py
  :language: python

And as said in the beginning, the directory of modules serviced by *pavao* is added
to the python search path, so we can simply import *timestamp.py* and use it inside
the new endpoint callback:

.. literalinclude:: ../codes/stamped_hello.py
  :language: python

While this is fine, *pavao* also includes the method **pavao.include()**, which
does basically the same thing as the ordinary Python "import" directive but further
tracks the dependency between **stamped_hello.py** and **timestamp.py**. This
is used for the hot-reloading of modules when changes are detected, such that if
**timestamp.py** is modified, **stamped_hello.py** (and all other files that
import it through **pavao.include()**) will be reloaded. More information on this
can be found in the YYYY section.

Our modules's directory is then now comprised of these three files:

.. code::

   $ tree modules
   modules/
   ├── hello.py
   ├── stamped_hello.py
   └── timestamp.py

   1 directory, 3 files

The function **pavao_endpoint()** itself can receive a set of
injected parameters and additionaly be made an asynchronous method.
For further information regarding this, see section XXX.


Path definition
===============

The path of an endpoint consists of the usual URL pattern and can
additionally include one or more wildcards, which are formed
by named variables inside braces. The named variables can be optionally followed
by a colon plus some Python builtin type (str, int, float, etc...). *pavao*
will attempt to match the specified type, automatically converting the corresponding
string to it. All these named variables will be presented to the endpoint servicing
function inside the dictionary parameter **'path_variables'**, as ilustrated by
the example below:

.. literalinclude:: ../codes/greet.py
  :language: python

If the path of an endpoint matches positionally a path request but the corresponding
string of one or more of its wildcards cannot be converted to the required type,
*pavao* will skip this endpoint in its search, and will return a 404 response status
if no other endpoint meets the condition. For example, in the server logs below it's
possible to see the responses for different accesses to the above example, and how
only the last access actually matches:

.. code::

   INFO: <url>:44042 - "GET /greet/Mary/Jane HTTP/1.1" 404 Not Found
   INFO: <url>:49188 - "GET /greet/Mary/23.55 HTTP/1.1" 404 Not Found
   INFO: <url>:35732 - "GET /greet/Mary/6 HTTP/1.1" 200 OK


Servicing function definition
=============================

The servicing function can be either a normal function or an asynchronous
one if it needs to use *await* to execute asynchronous methods. This function
can be declared to accept a range of possible arguments, depending on the
availability of suppliers, but by default the following parameters
can be automatically injected:

   - receive
   - request
   - response
   - path_variables
   - broadcasting

receive
-------

**receive** is the very same function as defined by the
`ASGI specification <https://asgi.readthedocs.io/en/latest/specs/www.html#request-receive-event>`_.
*pavao* only receives the scope message to direct the request to the respective
endpoint as well to parse the preliminary data of the request, which are presented
to the function within the **request** argument. **receive** can thus be used to
receive additional data from the request.

request
-------

**request** holds parsed information from the scope of the HTTP request. This includes
headers, cookies, source and destination addresses, and URL parameters from the request.
For more details, refer to the documentation of the class itself.

response
--------

**response** is a thin layer over the original ASGI specification `send function
<https://asgi.readthedocs.io/en/latest/specs/main.html#applications>`_. It stores
some state and has convenience methods to easen common operations, like adding
cookies, setting status code and defining contents to write back to the requester.
The functions **emit_headers()** and **emit_body()** can be used for finer control,
but *pavao* will take care of sending data automatically if these functions are
not employed by the serciving function.

path_variables
--------------

**path_variables** is a dictionary holding any matched path wildcard, as explained in
the Path definion section above. If no wildcards are present in the endpoint path, it'll
be an empty dictionary nonetheless.

