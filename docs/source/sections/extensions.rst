
Extras
******

JWT
===

pavao ships with ``JwtSupplier``, a self-contained JWT utility that handles token
generation, validation, and signing-key rotation. It is not wired automatically; the
application registers it as a custom supplier so that any module can receive a ``jwt``
parameter and use it.

A minimal supplier that exposes ``jwt`` to the rest of the application:

.. code-block:: python

   import pavao

   class JwtProvider(pavao.ParameterSupplier):
     def configure(self, loaded_settings):
       self.jwt = pavao.JwtSupplier()

     def parameters_supplied(self):
       async def provide():
         return self.jwt
       return {'jwt': (provide, None)}

Place this file in the foundation directory (``--foundation``) and ``jwt`` becomes
available to any module that declares it.

Generating tokens
-----------------

.. code-block:: python

   claims = {
     'sub': user_id,
     'iat': now.timestamp(),
     'exp': (now + timedelta(minutes=30)).timestamp()
   }

   token = jwt.generate_token(claims)

``claims`` is a plain dict. Any JSON-serializable values are accepted; the standard
fields (``sub``, ``iat``, ``exp``) are not enforced by pavao — the application is
responsible for including and interpreting them. ``generate_token`` returns a signed
HS256 JWT string.

Validating tokens
-----------------

.. code-block:: python

   claims = jwt.validate_token(token_string)
   if claims is None:
     response.set_status(401)
     return

``validate_token`` returns the claims dict if the token is structurally valid and its
signature matches a known key, or ``None`` if it is malformed, signed with an unknown
key, or was issued with a key that has since expired. The application is responsible for
checking ``exp`` and other application-level claims after a successful validation.

Key rotation
------------

Signing keys are generated automatically when ``JwtSupplier`` is instantiated. To rotate
to a new key:

.. code-block:: python

   jwt.refresh_secret_key()

Tokens signed with the old key are immediately invalidated. To keep old tokens valid
during a transition window:

.. code-block:: python

   jwt.refresh_secret_key(previous_validity=7)      # keep old key valid for 7 days
   jwt.refresh_secret_key(previous_validity=timedelta(hours=2))

``previous_validity`` accepts either a positive integer (days) or a ``timedelta``.
Multiple past keys can be active simultaneously; each is tracked by its identifier
embedded in the token header (``kid``).

Putting it together
-------------------

A login endpoint that uses ``accepts_json`` to parse credentials and returns a signed
token:

.. literalinclude:: ../codes/login.py
   :language: python

The descriptor declares ``jwt`` as a dependency and returns ``None`` if the supplier is
not configured, making the endpoint conditional on the presence of the JWT provider.

Token configuration
-------------------

The following keys in ``application.yml`` are available for applications that choose to
honour them (``JwtSupplier`` does not read them automatically — they are intended for use
in the supplier's ``configure`` method):

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Key
     - Description
   * - ``pavao.token.issuer``
     - Issuer string to embed in token claims
   * - ``pavao.token.validity.access_minutes``
     - Access token lifetime in minutes
   * - ``pavao.token.validity.refresh_minutes``
     - Refresh token lifetime in minutes

Internationalization
====================

pavao automatically localizes its own built-in error responses — missing parameters,
invalid JSON, wrong content type — according to the ``Accept-Language`` header sent by
the client. Twenty languages are supported out of the box, including English, Portuguese,
Spanish, French, German, Chinese, Japanese, Arabic, and Russian.

Application modules can plug into the same mechanism using ``ModuleLocalizer``.

Adding message files
--------------------

Create a ``messages/`` directory alongside your module code and add one ``.ini`` file per
language. The filename is the locale identifier (e.g. ``en_US.ini``, ``pt_BR.ini``).
Each file contains plain ``KEY = value`` pairs:

.. code-block:: ini

   ; messages/en_US.ini
   ITEM_NOT_FOUND = "Item not found"
   ACCESS_DENIED  = "You do not have access to this resource"

.. code-block:: ini

   ; messages/pt_BR.ini
   ITEM_NOT_FOUND = "Item não encontrado"
   ACCESS_DENIED  = "Você não tem acesso a este recurso"

Using ModuleLocalizer
---------------------

``ModuleLocalizer`` is instantiated once at module load time and maps message keys to
``LazyLocalizer`` objects. A ``LazyLocalizer`` holds a reference to its key and performs
the actual lookup only when ``localize()`` is called with a language priority list:

.. code-block:: python

   import pavao

   _localizer = pavao.ModuleLocalizer('items', pavao.path_to('messages'))

   ITEM_NOT_FOUND = _localizer.map('ITEM_NOT_FOUND')
   ACCESS_DENIED  = _localizer.map('ACCESS_DENIED')

The first argument to ``ModuleLocalizer`` is a module name used for logging; it does not
affect message resolution.

Localizing a response
---------------------

``request.parse_locale_priority()`` returns the ordered list of languages from the
client's ``Accept-Language`` header. Pass it to ``localize()`` to get the best available
translation:

.. literalinclude:: ../codes/i18n_endpoint.py
   :language: python

Resolution order
----------------

For a given priority list, pavao tries each language in order. If an exact locale is not
available (e.g. ``fr_FR`` is requested but only ``fr_BE`` exists), the language prefix is
matched as a fallback. If no match is found at all, ``en_US`` is used as the final
fallback.
