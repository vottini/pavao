
import sys
import time
import asyncio
import os

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .logger import Logger

class Modifications:
	def __init__(self, creations=None, deletions=None, updates=None):
		self.creations = creations if creations is not None else tuple()
		self.deletions = deletions if deletions is not None else tuple()
		self.updates = updates if updates is not None else tuple()

	def add_creation(self, created):
		if created in self.creations or created in self.updates:
			return self

		if created in self.deletions:
			newer_deletions = tuple(dlt for dlt in self.deletions if dlt != created)
			newer_updates = (*self.updates, created)

			return Modifications(
				self.creations,
				newer_deletions,
				newer_updates)

		newer_creations = (*self.creations, created)
		return Modifications(
			newer_creations,
			self.deletions,
			self.updates)


	def add_deletion(self, deleted):
		if deleted in self.deletions:
			return self

		if deleted in self.creations or deleted in self.updates:
			newer_creations = tuple(ctd for ctd in self.creations if ctd != deleted)
			newer_updates = tuple(upd for upd in self.updates if upd != deleted)

			return Modifications(
				newer_creations,
				self.deletions,
				newer_updates)

		newer_deletions = (*self.deletions, deleted)
		return Modifications(
			self.creations,
			newer_deletions,
			self.updates)


	def add_update(self, updated):
		if updated in self.updates or updated in self.creations:
			return self

		newer_updates = (*self.updates, updated)
		newer_deletions = tuple(dlt for dlt in self.deletions if dlt != updated)
		return Modifications(
			self.creations,
			newer_deletions,
			newer_updates)


	def __hash__(self):
		return hash(self.deletions) ^ hash(self.updates)

#-------------------------------------------------------------------------------

class SimulatedEvent:
	def __init__(self, event_type, src_path):
		self.is_directory = False
		self.event_type = event_type
		self.src_path = src_path

#-------------------------------------------------------------------------------

class PathMonitor(FileSystemEventHandler):

	def __init__(self, path, callback):
		FileSystemEventHandler.__init__(self)
		self.callback = callback
		self.path = path

		self.queue = asyncio.Queue()
		self.changes = asyncio.Event()
		self.observer = Observer()

		self.running = False
		self.modifications = Modifications()
		self.monitoring = None
		self.condensing = None
		self.loop = None


	async def _add_to_queue(self, event):
		await self.queue.put(event)


	def handle(self, event):
		if not event.is_directory:
			asyncio.run_coroutine_threadsafe(
				self._add_to_queue(event),
				self.loop)


	def on_created(self, event): self.handle(event)
	def on_deleted(self, event): self.handle(event)
	def on_modified(self, event): self.handle(event)


	def on_moved(self, event):
		if not event.is_directory:
			self.handle(SimulatedEvent('deleted', event.src_path))
			self.handle(SimulatedEvent('created', event.dest_path))


	async def _monitor(self):

		try:
			while True:
				event = await self.queue.get()
				abs_path = os.path.abspath(event.src_path)

				if event.event_type == 'created':
					self.modifications = self.modifications.add_creation(
						abs_path)

				if event.event_type == 'modified':
					self.modifications = self.modifications.add_update(
						abs_path)

				if event.event_type == 'deleted':
					self.modifications = self.modifications.add_deletion(
						abs_path)

				self.changes.set()
				self.queue.task_done()

		except asyncio.CancelledError as e:
			pass


	async def _collect(self):

		try:
			while True:
				await self.changes.wait()
				previous_hash = hash(self.modifications)
				await asyncio.sleep(1)

				while True:
					current_hash = hash(self.modifications)
					if current_hash == previous_hash: break
					previous_hash = current_hash
					await asyncio.sleep(1)

				self.callback(
					self.modifications.creations,
					self.modifications.deletions,
					self.modifications.updates)

				self.modifications = Modifications()
				self.changes.clear()

		except asyncio.CancelledError as e:
			pass

		except Exception as e:
			msg = f"Error while collecting file changes: {e}"
			Logger.warn(msg)


	def schedule_execution(self, loop):
		self.running = True
		self.loop = loop

		self.monitoring = self.loop.create_task(self._monitor())
		self.condensing = self.loop.create_task(self._collect())
		self.observer.schedule(self, self.path, recursive=True) #, follow_symlink=True)
		self.observer.start()


	def stop(self):
		if self.running:
			self.running = False
			self.observer.stop()
			self.observer.join()

			self.monitoring.cancel()
			self.condensing.cancel()


	async def _finish(self):
		await self.monitoring
		await self.condensing

	def stop_and_wait(self):
		if self.running:
			self.stop()
			self.loop.run_until_complete(self._finish())

#-------------------------------------------------------------------------------

__all__ = [
	"PathMonitor"
]

