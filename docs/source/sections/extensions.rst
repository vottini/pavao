
Extensions
**********

pavao extensions are self-contained packages that add suppliers, filters, and endpoint
modules to any pavao project. Two official extensions exist:

`pavao-postgres <https://github.com/vottini/pavao-postgres>`_
  PostgreSQL support. Provides a ``pg_connection`` injectable backed by an asyncpg
  connection pool. Optionally replaces the built-in SQLite ``task_store`` and
  ``stored_settings`` backends with PostgreSQL equivalents — useful when the application
  already runs a Postgres server or needs to scale across multiple processes.

`pavao-auth <https://github.com/vottini/pavao-auth>`_
  JWT-based authentication, role and permission management, and a full administration API.

Extensions are managed with the ``pavao-pkg`` command, installed alongside pavao.
They are vendored into your project — their files are copied into your ``foundation/``
and ``modules/`` directories and committed to version control. No network access is needed
to run the project after that; ``pavao-pkg`` is only used when adding or updating
extensions.

Caveats of vendoring
====================

The vendoring model has a few trade-offs worth understanding before adopting it:

**Do not edit vendored files.** Once installed, extension files sit inside your project
and look like ordinary source files. Any manual edits will be silently overwritten the
next time ``pavao-pkg update`` or ``pavao-pkg sync`` runs. Treat everything under
``foundation/<ext>/`` and ``modules/<ext>/`` as read-only. Configuration belongs in
``application.yml``; behaviour changes belong in a fork or a wrapper module of your own.

**The pinned hash covers the archive, not the local files.** The SHA-256 recorded in
``pavao_packages.json`` is taken from the downloaded archive at install time. It
protects against a tag being silently republished upstream, but it does not detect local
drift — if vendored files are modified after installation, ``pavao-pkg`` has no way to
notice. If you suspect local files have been accidentally changed, run
``pavao-pkg update <ext>`` (without a new tag) to reinstall from the pinned version.

**Python dependencies are not removed on uninstall.** When you remove an extension,
its Python packages remain in your environment. If they are no longer needed, uninstall
them manually with ``pip uninstall``. This is especially relevant when multiple
extensions share a dependency at different versions.

Using extensions
================

Adding an extension
-------------------

Pass the GitHub repository. Omitting ``--tag`` installs the latest published tag:

.. code-block:: console

   $ pavao-pkg add github.com/vottini/pavao-auth

To pin to a specific tag:

.. code-block:: console

   $ pavao-pkg add github.com/vottini/pavao-auth --tag v1.0.0

This downloads the archive, records the repository, tag, and a SHA-256 content hash in
``pavao_packages.json``, copies every subdirectory inside the extension's ``foundation/``
directly into your project's ``foundation/``, does the same for ``modules/``, installs
Python dependencies from ``requirements.txt`` if one is present, and adds the vendored
directories to ``.gitignore`` automatically.

The extension itself controls the subdirectory names. ``pavao-auth`` ships
``foundation/auth/`` and ``modules/auth/``, so those paths appear in your project.
No renaming or prefix-stripping is performed by ``pavao-pkg``.

``pavao_packages.json`` is committed to version control. The vendored directories
are not.

Dependency conflicts
^^^^^^^^^^^^^^^^^^^^

Before installing an extension's ``requirements.txt``, ``pavao-pkg`` checks whether any
listed package is already installed at a version that does not satisfy the extension's
constraints. If a conflict is found the install is aborted and the mismatches are
reported:

.. code-block:: console

   $ pavao-pkg add github.com/vottini/pavao-auth --tag v1.0.0
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

   $ pavao-pkg add github.com/vottini/pavao-auth --tag v1.0.0 --force

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

   $ pavao-pkg update pavao-auth --tag v1.1.0

Omitting ``--tag`` re-fetches the current pinned version (useful to reinstall after a
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

   $ pavao-pkg add github.com/vottini/pavao-auth --tag v1.0.0 \
       --foundation app/foundation \
       --modules app/modules

All commands accept these flags; use the same values consistently across ``add``,
``update``, ``remove``, and ``sync``.

Building an extension
=====================

`pavao-postgres <https://github.com/vottini/pavao-postgres>`_ is the reference
implementation to follow when building an extension. It demonstrates the full structure:
a supplier that reads configuration from ``application.yml``, relative imports between
files within the same subdirectory, an optional ``requirements.txt``, and replacement
backends for built-in injectables.

An extension is a directory (or Git repository). Both ``foundation/`` and ``modules/``
are optional — include only the ones your extension needs:

.. code-block:: text

   pavao-myext/
   ├── requirements.txt        ← Python dependencies (optional)
   ├── foundation/             ← optional: suppliers and filters
   │   └── myext/             ← your chosen namespace
   │       ├── supplier.py
   │       └── filter.py
   └── modules/                ← optional: endpoint, task, and service modules
       └── myext/             ← same namespace
           ├── items/
           │   ├── list.py
           │   └── create.py
           └── shared/
               └── utils.py

An extension that only provides a supplier (like ``pavao-postgres``) needs only
``foundation/``; one that only adds ready-made endpoints needs only ``modules/``.
``pavao-pkg`` silently skips whichever directory is absent.

``pavao-pkg`` copies every subdirectory inside ``foundation/`` directly into the target
project's ``foundation/``, and does the same for ``modules/``. No renaming is performed.
The subdirectory names you choose in the extension repo are the names that appear in the
user's project.

Naming convention
-----------------

The repository should be named ``pavao-<name>`` as a convention for discoverability.
The subdirectory names inside ``foundation/`` and ``modules/`` are yours to choose —
pick something short and unlikely to conflict with other extensions or with the user's
own code. Using the same name for both is recommended for consistency.

Internal imports
----------------

Foundation and module files are loaded by pavao directly from disk, not as part of a
Python package, so relative imports (``from . import``) do not work. Use
``pavao.from_module()`` instead:

.. code-block:: python

   # correct — loads sibling file by path, injects names into the current scope
   pavao.from_module('pg_task_store').import_item('PgTaskStore')

   # multiple items can be chained
   pavao.from_module('pg_task_store').import_item('PgTaskStore').import_item('PgStoredSettings')

   # breaks — no package context at load time
   from .pg_task_store import PgTaskStore

``pavao.from_module()`` resolves the path relative to the calling file and injects the
imported names directly into the calling module's scope — no assignment needed.
It works at any nesting depth and is unaffected by where the extension is installed.

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
