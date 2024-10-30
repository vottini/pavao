
import asyncio
from dataclasses import dataclass
from typing import Dict

from .utils import adapter
from .utils import async_adapter

class EndpointFunction:
	def __init__(self, preprocessor, processor, postprocessor):
		self.preprocessor = preprocessor
		self.processor = async_adapter(adapter(processor))
		self.postprocessor = postprocessor

	async def execute(self, context):
		if self.preprocessor is None:
			await self.processor(context)
			return

		try:
			await self.preprocessor(context)
			await self.processor(context)

		finally:
			if self.postprocessor is not None:
				await self.postprocessor(context)


@dataclass
class EndpointData:
	function: EndpointFunction
	all_specs: Dict[str, str]

