
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, Optional


class TaskStore(ABC):

	# --- write (used by the framework) ---

	@abstractmethod
	async def register_task(self,
		name: str,
		package: Optional[str]) -> tuple:
		...

	@abstractmethod
	async def start_execution(self,
		task_id: int,
		started_at: datetime) -> int:
		...

	@abstractmethod
	async def record_output(self,
		execution_id: int,
		instant: datetime,
		content: str,
		is_error: bool) -> None:
		...

	@abstractmethod
	async def finish_execution(self,
		execution_id: int,
		ended_at: datetime,
		success: bool) -> None:
		...

	# --- read (available to user modules) ---

	@abstractmethod
	async def list_tasks(self) -> list:
		"""Return all registered tasks as dicts with keys:
		id, package, name, enabled."""
		...

	@abstractmethod
	async def get_executions(self,
		task_id: int,
		day: Optional[date] = None) -> list:
		"""Return completed executions for a task as dicts with keys:
		id, success, execution_start, execution_end.
		If day is given, only executions that started on that date are returned."""
		...

	@abstractmethod
	async def get_outputs(self,
		execution_id: int) -> list:
		"""Return output rows for an execution as dicts with keys:
		instant, error, content."""
		...


STORED_SETTINGS_ALLOWED_TYPES: dict = {
	'int':   int,
	'float': float,
	'str':   str,
	'bool':  bool,
}

class StoredSettings(ABC):
	"""Typed key-value store for persisting application state across restarts.

	Supported value types are the scalar types in STORED_SETTINGS_ALLOWED_TYPES
	(int, float, str, bool), homogeneous lists of any of those scalars, and the
	empty list [].

	Implementations must:
	  - Raise ValueError for unsupported scalar types
	  - Raise ValueError for lists whose elements are not all the same type
	  - Raise ValueError for lists whose element type is not in STORED_SETTINGS_ALLOWED_TYPES
	  - Reconstruct values with their original type on get()
	  - Return None for keys that have never been set
	"""

	@abstractmethod
	async def get(self, key: str) -> Optional[Any]:
		"""Return the value stored under key, reconstructed to its original type.
		Returns None if the key has never been set."""
		...

	@abstractmethod
	async def set(self, key: str, value: Any) -> None:
		"""Persist value under key.
		Raises ValueError if the value type is not supported."""
		...


__all__ = [
	'TaskStore',
	'StoredSettings',
]
