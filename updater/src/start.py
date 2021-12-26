import os
import asyncio
import logging
import aiomysql

from download import RunnerPool
from post_update import post_update
from table import Table
from utils import env

from shared.miniredis import Client


logging.basicConfig(
	format='[%(asctime)s] [%(levelname)s] %(message)s',
	level=logging.DEBUG
)

try:
	import uvloop
except ImportError:
	uvloop = None
	logging.warning("Can't use uvloop.")


def start(loop):
	return loop.run_until_complete(asyncio.gather(
		# CFM DB
		aiomysql.create_pool(
			host=env.cfm_ip, port=3306,
			user=env.cfm_user, password=env.cfm_pass,
			db=env.cfm_db, loop=loop,
			autocommit=True
		),

		# Atelier801 API
		aiomysql.create_pool(
			host=env.a801_ip, port=3306,
			user=env.a801_user, password=env.a801_pass,
			db=env.a801_db, loop=loop
		),
	))


async def notify_redis():
	if ":" in env.host:
		address = env.host.split(":")
		address[1] = int(address[1])
	else:
		address = env.host

	client = Client(
		address,
		reconnect=env.reconnect,
		loop=asyncio.get_event_loop()
	)
	await client.start()
	await client.send("ranking.updatedone")


def run(loop, pools):
	runner = RunnerPool(
		int(os.getenv("PIPE_SIZE", "100")),
		int(os.getenv("BATCH_SIZE", "100")),
		*pools
	)

	player = Table("player")
	tribe = Table("tribe")
	member = Table("member")

	logging.debug("start all")
	loop.run_until_complete(asyncio.wait((
		runner.extract(player),
		runner.extract(tribe),
		runner.extract(member),
	)))
	loop.run_until_complete(post_update(player, tribe, member, *pools))
	loop.run_until_complete(notify_redis())
	logging.debug("end all")


def stop(loop, pools):
	tasks = []
	for pool in pools:
		pool.close()
		tasks.append(pool.wait_closed())

	loop.run_until_complete(asyncio.wait(tasks))


if __name__ == "__main__":
	if uvloop is not None:
		uvloop.install()

	loop = asyncio.get_event_loop()

	pools = start(loop)
	try:
		run(loop, pools)
	finally:
		stop(loop, pools)
