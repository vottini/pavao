
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


class StoredSettings(ABC):

	@abstractmethod
	async def get(self, key: str) -> Optional[Any]:
		...

	@abstractmethod
	async def set(self, key: str, value: Any) -> None:
		...


__all__ = [
	'TaskStore',
	'StoredSettings',
]
