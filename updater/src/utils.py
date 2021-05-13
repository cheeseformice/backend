import os
import aiomysql


class env:
	a801_ip = os.getenv("A801_IP", "mockupdb")
	a801_user = os.getenv("A801_USER", "test")
	a801_pass = os.getenv("A801_PASS", "test")
	a801_db = os.getenv("A801_DB", "atelier801_api")

	cfm_ip = os.getenv("DB_IP", "database")
	cfm_user = os.getenv("DB_USER", "test")
	cfm_pass = os.getenv("DB_PASS", "test")
	cfm_db = os.getenv("DB", "api_data")


def with_cursors(*from_pools):
	"""A decorator to acquire cursors from the given pools before
	calling the class method.
	"""
	def decorator(func):
		async def acquire_cursors(self, pools, *args, **kwargs):
			# Acquire connections
			conns = []
			for pool in pools:
				conns.append(await pool.acquire())
			# Acquire cursors
			cursors = []
			for conn in conns:
				cursors.append(await conn.cursor(aiomysql.SSCursor))

			try:
				return await func(self, *cursors, *args, **kwargs)

			finally:
				# No matter what, close cursors and release connections
				for cursor in cursors:
					await cursor.close()
				for conn in conns:
					pool.release(conn)

		if not from_pools:
			# No pools specified, assume first argument to be the pool
			def wrapper(self, pool, *args, **kwargs):
				return acquire_cursors(self, (pool,), *args, **kwargs)

		else:
			# Pool names specified, so fetch them before calling
			def wrapper(self, *args, **kwargs):
				pools = []
				for pool_name in from_pools:
					pools.append(getattr(self, pool_name))

				return acquire_cursors(self, pools, *args, **kwargs)

		return wrapper

	return decorator
