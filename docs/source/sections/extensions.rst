
Extensions
**********

pavao extensions are self-contained packages that add suppliers, filters, and endpoint
modules to any pavao project. Two official extensions exist:

- `pavao-auth <https://github.com/vottini/pavao-auth>`_ — JWT-based authentication,
  role and permission management, and a full administration API
- `pavao-postgres <https://github.com/vottini/pavao-postgres>`_ — PostgreSQL connection
  pool supplier with optional ``task_store`` and ``stored_settings`` backends

Extensions are managed with the ``pavao-pkg`` command, installed alongside pavao.
They are vendored into your project — their files are copied into your ``foundation/``
and ``modules/`` directories and committed to version control. No network access is needed
to run the project after that; ``pavao-pkg`` is only used when adding or updating
extensions.

Using extensions
================

Adding an extension
-------------------

Pass the GitHub repository and a tag:

.. code-block:: console

   $ pavao-pkg add github.com/vottini/pavao-auth@v1.0.0

This downloads the archive, records the repository, tag, and a SHA-256 content hash in
``pavao_packages.json``, copies ``foundation/`` to ``foundation/auth/`` and ``modules/``
to ``modules/auth/``, installs Python dependencies from ``requirements.txt`` if one is
present, and adds the vendored directories to ``.gitignore`` automatically.

``pavao_packages.json`` is committed to version control. The vendored directories
(``foundation/auth/``, ``modules/auth/``) are not.

Dependency conflicts
^^^^^^^^^^^^^^^^^^^^

Before installing an extension's ``requirements.txt``, ``pavao-pkg`` checks whether any
listed package is already installed at a version that does not satisfy the extension's
constraints. If a conflict is found the install is aborted and the mismatches are
reported:

.. code-block:: console

   $ pavao-pkg add github.com/vottini/pavao-auth@v1.0.0
     dependency conflict — the extension requires versions that differ from what is installed:
       asyncpg>=0.30  (installed: 0.27.0)
     aborting — use --force to install anyway

Only cases where the installed version is **lower** than the extension's minimum
requirement are reported. A higher installed version is always accepted — a user on
``asyncpg==0.30`` satisfies an extension that requires ``asyncpg>=0.27`` or even
``asyncpg==0.27``. Packages that are not yet installed are also ignored and will be
installed fresh by pip.

Use ``--force`` to proceed despite conflicts:

.. code-block:: console

   $ pavao-pkg add github.com/vottini/pavao-auth@v1.0.0 --force

``--force`` is also accepted by ``update`` and ``sync``.

Syncing after a fresh clone
---------------------------

After cloning, restore all extension files with:

.. code-block:: console

   $ pavao-pkg sync

``sync`` downloads every entry in ``pavao_packages.json``, verifies each archive against
the recorded hash, copies the files, and installs Python dependencies. If any hash does
not match — meaning the tag was force-pushed after it was first recorded — ``sync`` aborts
and reports the mismatch. Dependency conflicts are checked the same way as ``add`` and
also abort unless ``--force`` is passed.

Updating an extension
---------------------

.. code-block:: console

   $ pavao-pkg update pavao-auth@v1.1.0

Omitting the tag re-fetches the current version (useful to reinstall after a
``git clean``):

.. code-block:: console

   $ pavao-pkg update pavao-auth

Removing an extension
---------------------

.. code-block:: console

   $ pavao-pkg remove pavao-auth

This deletes ``foundation/auth/`` and ``modules/auth/``, removes the entry from
``pavao_packages.json``, and cleans up the ``.gitignore`` entries. Python dependencies
installed by the extension are **not** removed automatically — uninstall them manually
with ``pip uninstall`` if they are no longer needed by other packages.

Listing installed extensions
-----------------------------

.. code-block:: console

   $ pavao-pkg list
     pavao-auth@v1.0.0  (github.com/vottini/pavao-auth)
     pavao-postgres@v0.3.1  (github.com/vottini/pavao-postgres)

Custom foundation and modules directories
-----------------------------------------

``pavao-pkg`` defaults to ``foundation/`` and ``modules/`` relative to the current
working directory. Override them with ``--foundation`` and ``--modules``:

.. code-block:: console

   $ pavao-pkg add github.com/vottini/pavao-auth@v1.0.0 \
       --foundation app/foundation \
       --modules app/modules

All commands accept these flags; use the same values consistently across ``add``,
``update``, ``remove``, and ``sync``.

Building an extension
=====================

An extension is a directory (or Git repository) with the following layout:

.. code-block:: text

   pavao-myext/
   ├── requirements.txt       ← Python dependencies (optional)
   ├── foundation/            ← suppliers and filters
   │   ├── supplier.py
   │   └── filter.py
   └── modules/               ← endpoint, task, and service modules
       ├── items/
       │   ├── list.py
       │   └── create.py
       └── shared/
           └── utils.py

When installed, ``foundation/`` becomes ``foundation/myext/`` and ``modules/`` becomes
``modules/myext/`` in the target project. The ``myext`` name is derived by stripping the
``pavao-`` prefix from the repository name.

Naming convention
-----------------

The repository must be named ``pavao-<name>``. The ``<name>`` part becomes the
subdirectory name in both ``foundation/`` and ``modules/``. Choose a name that is
unlikely to conflict with other extensions or with the user's own code.

Internal imports
----------------

Because the extension's files are placed inside a subdirectory, internal imports must
use **relative** form. Absolute imports that work during development will break after
installation:

.. code-block:: python

   # correct — survives installation under foundation/myext/
   from .utils import helper

   # breaks — resolves to 'utils' at the root, not 'myext.utils'
   from utils import helper

Relative imports work at any nesting depth and are unaffected by the directory name the
extension is installed under.

Configuration
-------------

Suppliers read configuration from ``application.yml`` via ``loaded_settings``. Use a
top-level key that matches your extension name to avoid conflicts with the user's own
settings or other extensions:

.. code-block:: yaml

   myext:
     api_key: ${MYEXT_API_KEY}
     timeout: 30

.. code-block:: python

   class MySupplier(pavao.ParameterSupplier):
     def configure(self, loaded_settings):
       self.config = loaded_settings.get_setting('myext', {
         'api_key': str,
         'timeout': 30,
       })

Tagging releases
----------------

``pavao-pkg`` pins extensions to Git tags. Every published version of an extension must
have a corresponding annotated tag. Follow `semantic versioning <https://semver.org>`_:
``v1.0.0``, ``v1.1.0``, ``v2.0.0``. Never move or delete a published tag — doing so
will break ``pavao-pkg sync`` for anyone who has pinned to it, since the hash recorded
at install time will no longer match.
