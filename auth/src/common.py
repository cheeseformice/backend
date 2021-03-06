import os
import aiohttp
import asyncio
import concurrent.futures as futures

from shared.webhook import Webhook
from shared.pyservice import Service
from aiomysql.sa import create_engine


class env:
	cfm_ip = os.getenv("DB_IP", "cfmdb")
	cfm_user = os.getenv("DB_USER", "test")
	cfm_pass = os.getenv("DB_PASS", "test")
	cfm_db = os.getenv("DB", "api_data")
	ticket_api = os.getenv("TICKET_API", "http://localhost:8080/auth")
	max_workers = int(os.getenv("HASH_WORKERS", "0")) or None
	roles_wh_id = os.getenv("ROLES_WH_ID")
	roles_wh_token = os.getenv("ROLES_WH_TOKEN")


service = Service("auth")


@service.event
async def on_boot(new):
	global service
	service = new

	service.wh = Webhook(int(env.roles_wh_id), env.roles_wh_token)
	await service.wh.boot()

	service.http = await aiohttp.ClientSession().__aenter__()
	service.db = await create_engine(
		host=env.cfm_ip, port=3306,
		user=env.cfm_user, password=env.cfm_pass,
		db=env.cfm_db, loop=service.loop,
		autocommit=True
	)
	service.process_pool = futures.ProcessPoolExecutor(
		max_workers=env.max_workers
	)

	service.loop.create_task(ping_db())


@service.event
async def on_stop():
	await service.http.__aexit__(None, None, None)
	await service.wh.stop()


async def ping_db():
	while True:
		async with service.db.acquire() as conn:
			await conn.connection.ping()

		await asyncio.sleep(60.0)
