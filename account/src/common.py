import os
import asyncio

from webhook import Webhook
from shared.pyservice import Service
from aiomysql.sa import create_engine


class env:
	cfm_ip = os.getenv("DB_IP", "cfmdb")
	cfm_user = os.getenv("DB_USER", "test")
	cfm_pass = os.getenv("DB_PASS", "test")
	cfm_db = os.getenv("DB", "api_data")
	sanction_wh_id = os.getenv("SANCTION_WH_ID")
	sanction_wh_token = os.getenv("SANCTION_WH_TOKEN")


service = Service("account")


@service.event
async def on_boot(new):
	global service
	service = new

	service.wh = Webhook(int(env.sanction_wh_id), env.sanction_wh_token)
	await service.wh.boot()

	service.db = await create_engine(
		host=env.cfm_ip, port=3306,
		user=env.cfm_user, password=env.cfm_pass,
		db=env.cfm_db, loop=service.loop,
		autocommit=True
	)

	service.loop.create_task(ping_db())


@service.event
async def on_stop():
	await service.wh.stop()


async def ping_db():
	while True:
		async with service.db.acquire() as conn:
			await conn.connection.ping()

		await asyncio.sleep(60.0)
