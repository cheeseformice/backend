import os
import json
import aiohttp
import asyncio

from utils import set_service, get_new_names, download_teams, tfm_roles

from datetime import datetime, timedelta

from shared.pyservice import Service
from shared.models import roles

from aiomysql.sa import create_engine
from sqlalchemy import and_
from sqlalchemy.sql import select, delete
from sqlalchemy.dialects.mysql import insert


class env:
	cfm_ip = os.getenv("DB_IP", "cfmdb")
	cfm_user = os.getenv("DB_USER", "test")
	cfm_pass = os.getenv("DB_PASS", "test")
	cfm_db = os.getenv("DB", "api_data")
	name_webhook = os.getenv("NAME_WEBHOOK")


assert env.name_webhook is not None, "NAME_WEBHOOK doesn't have any link"


service = Service("naming")


@service.event
async def on_boot(new):
	global service
	service = new

	set_service(new)

	service.db = await create_engine(
		host=env.cfm_ip, port=3306,
		user=env.cfm_user, password=env.cfm_pass,
		db=env.cfm_db, loop=service.loop,
		autocommit=True
	)

	service.loop.create_task(ping_db())
	service.loop.create_task(update_roles())


async def ping_db():
	while True:
		async with service.db.acquire() as conn:
			await conn.connection.ping()

		await asyncio.sleep(60.0)


async def write_roles(new_roles):
	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(roles.c.id, roles.c.tfm)
			.select_from(roles)
			.where(roles.c.tfm > 0)
		)
		old_roles = await result.fetchall()

		may_delete = False
		modified = {}
		for row in old_roles:
			if row.id not in new_roles:
				modified[row.id] = 0
				may_delete = True

			elif new_roles[row.id] != row.tfm:
				modified[row.id] = new_roles[row.id]

		if not modified:
			return

		await service.send_strict("broadcast:roles", "tfm", **{
			str(_id): bits
			for _id, bits in modified.items()
		})

		query = [
			{
				"id": _id,
				"cfm": 0,
				"tfm": bits,
			}
			for _id, bits in modified.items()
		]

		insert_stmt = insert(roles).values(query)
		await conn.execute(
			insert_stmt.on_duplicate_key_update(
				tfm=insert_stmt.inserted.tfm
			)
		)

		if may_delete:
			await conn.execute(
				delete(roles)
				.where(and_(roles.c.tfm == 0, roles.c.cfm == 0))
			)


async def update_roles():
	while True:
		run_at = datetime.utcnow()
		if run_at.hour >= 15:
			run_at = run_at + timedelta(days=1)
		run_at = run_at.replace(hour=15, minute=0, second=0, microsecond=0)
		diff = run_at - datetime.utcnow()
		await asyncio.sleep(diff.total_seconds())

		teams, names = await download_teams()
		users = await get_new_names(names)

		new_roles = {}  # user_id: role (int)
		changes = {}  # old_name: new_name

		for user in users:
			if user.new_name is None:
				continue

			user_roles = 0
			for idx, (role, _) in enumerate(tfm_roles):
				if user.old_name in teams[role]:
					user_roles |= 2 ** idx

			if user_roles > 0:
				new_roles[user.id] = user_roles

			if user.changed:
				changes[user.old_name.lower()] = user.new_name

		if changes:
			async with aiohttp.ClientSession() as sess:
				await sess.post(env.name_webhook, json={
					"content": json.dumps(changes)
				}, headers={
					"Content-Type": "application/json"
				})

		await write_roles(new_roles)


@service.on_request("changes")
async def fetch_changes(request):
	users = await get_new_names(request.names, only_changed=True)

	await request.send({
		user.old_name: {
			"id": user.id,
			"new_name": user.new_name
		}
		for user in users
	})


if __name__ == "__main__":
	service.run(workers=int(os.getenv("WORKERS", "1")))
