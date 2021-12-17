import aiohttp


class Webhook:
	def __init__(self, id: int, token: str):
		self.id = id
		self.token = token

		self.session_manager = aiohttp.ClientSession()

	async def boot(self):
		self.session = await self.session_manager.__aenter__()

	async def stop(self):
		await self.session_manager.__aexit__(None, None, None)

	async def post(self, content=None, embeds=None):
		data = {}
		if content is not None:
			data["content"] = content
		if embeds is not None:
			data["embeds"] = embeds

		await self.session.post(
			f"https://discord.com/api/webhooks/{self.id}/{self.token}",
			json=data,
			headers={
				"Content-Type": "application/json",
			}
		)
