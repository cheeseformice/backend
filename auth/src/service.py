import os
import asyncio
import concurrent.futures as futures

from argon2 import PasswordHasher

from shared.pyservice import Service

from shared.models import roles, auth, player, player_privacy

from aiomysql.sa import create_engine
from sqlalchemy.sql import select
from sqlalchemy.dialects.mysql import insert


class env:
	cfm_ip = os.getenv("DB_IP", "cfmdb")
	cfm_user = os.getenv("DB_USER", "test")
	cfm_pass = os.getenv("DB_PASS", "test")
	cfm_db = os.getenv("DB", "api_data")
	max_workers = int(os.getenv("HASH_WORKERS", "0")) or None


service = Service("auth")
ph = PasswordHasher()


def hash_password(password):
	return ph.hash(password)


def verify_password(password, hashed):
	return ph.verify(hashed, password)


def to_role_factory(*enum):
	def to_roles(bits):
		if bits == 0:
			return []

		roles = []
		for idx, role in enumerate(enum):
			if bits & (2 ** idx):
				roles.append(role)

		return roles

	return to_roles


cfm_roles = (
	"dev",
	"admin",
	"mod",
	"translator",
)
to_cfm_roles = to_role_factory(*cfm_roles)
to_tfm_roles = to_role_factory(
	"admin",
	"mod",
	"sentinel",
	"mapcrew",
	"module",
	"funcorp",
	"fashion",
)
privacy_fields = (
	# (name, default)
	("names", False),
	("soulmate", False),
	("tribe", False),
	("look", False),
	("activity", False),
	("badges", True),
	("titles", True),
	("shaman", True),
	("normal", True),
	("survivor", True),
	("racing", True),
	("defilante", True),
)
privacy_keys = set()
for field, _ in privacy_fields:
	privacy_keys.add(field)


def from_cfm_roles(roles):
	bits = 0
	for role in roles:
		bits |= 2 ** cfm_roles.index(role)
	return bits


@service.event
async def on_boot(new):
	global service
	service = new

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


async def ping_db():
	while True:
		async with service.db.acquire() as conn:
			await conn.connection.ping()

		await asyncio.sleep(60.0)


@service.on_request("new-session")
async def new_session(request):
	if request.uses == "refresh":
		token = request.refresh

		async with service.db.acquire() as conn:
			result = await conn.execute(
				select(
					auth.c.id,
					auth.c.refresh,

					roles.c.cfm.label("cfm_roles"),
					roles.c.tfm.label("tfm_roles"),
				)
				.select_from(
					auth
					.outerjoin(roles, roles.c.id == auth.c.id)
				)
				.where(auth.c.id == token["user"])
			)
			row = await result.first()

		if row is None or row.refresh != token["refresh"]:
			return await request.reject("ExpiredToken", "Token has expired")

		response = {}
		await request.open_stream()

	elif request.uses == "credentials":
		async with service.db.acquire() as conn:
			result = await conn.execute(
				select(
					player.c.id,
					auth.c.password,
					auth.c.refresh,

					roles.c.cfm.label("cfm_roles"),
					roles.c.tfm.label("tfm_roles"),
				)
				.select_from(
					player
					.join(auth, player.c.id == auth.c.id)
					.outerjoin(roles, roles.c.id == auth.c.id)
				)
				.where(player.c.name == request.user)
			)
			row = await result.first()

		if row is None:  # User isn't registered
			return await request.reject(
				"InvalidCredentials",
				"Invalid username or password."
			)

		# Hashing may take some time, so give a response before timeout
		await request.open_stream()
		is_correct = await service.loop.run_in_executor(
			service.process_pool,
			verify_password, request.password, row.password
		)

		if not is_correct:
			await request.send({
				"success": False,
				"err": "InvalidCredentials",
				"err_msg": "Invalid username or password."
			})
			await request.end()
			return

		# Check if the user wants to stay logged in
		response = {
			"refresh": {
				"user": row.id,
				"refresh": row.refresh,
				"duration": "180d" if request.remind else "1d"
			}
		}

	response["success"] = True
	response["session"] = {
		"user": row.id,
		"cfm_roles": to_cfm_roles(row.cfm_roles),
		"tfm_roles": to_tfm_roles(row.tfm_roles),
	}
	await request.send(response)
	await request.end()


@service.on_request("new-validation")
async def new_validation(request):
	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(
				player.c.id,
				auth.c.refresh
			)
			.select_from(
				player
				.outerjoin(auth, auth.c.id == player.c.id)
			)
			.where(player.c.name == request.user)
		)
		row = await result.first()

	if row is None:
		return await request.reject(
			"NotFound",
			"The given player has not been found in Transformice."
		)

	if request.method == "register" and row.refresh is not None:
		return await request.reject("WrongMethod")
	elif request.method == "password" and row.refresh is None:
		return await request.reject("WrongMethod")

	await request.send({
		"user": row.id,
		"refresh": row.refresh
	})


@service.on_request("is-valid")
@service.on_request("use-validity")
async def validation(request):
	if request.type == "is-valid":
		token = {
			"user": request.user,
			"refresh": request.refresh,
		}
	else:
		token = request.token

	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(
				player.c.id,
				auth.c.refresh
			)
			.select_from(
				player
				.outerjoin(auth, auth.c.id == player.c.id)
			)
			.where(player.c.id == token["user"])
		)
		row = await result.first()

		if row is None:
			# The account has been deleted?
			return await request.reject(
				"NotFound",
				"The given player has not been found in Transformice."
			)

		if token["refresh"] != row.refresh:
			return await request.reject("ExpiredToken")

		if request.type == "is-valid":
			return await request.end()

		# Hashing may take some time, so give a response before timeout
		await request.end()

		password = await service.loop.run_in_executor(
			service.process_pool,
			hash_password, request.password
		)

		if token["refresh"] is None:
			query = (
				auth.insert()
				.values(
					id=token["user"],
					password=password,
					discord=None
				)
			)
		else:
			query = (
				auth.update()
				.where(auth.c.id == token["user"])
				.values(
					password=password,
					refresh=auth.c.refresh + 1
				)
			)

		await conn.execute(query)


@service.on_request("change-roles")
async def change_roles(request):
	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(
				player.c.id,
				roles.c.cfm,
			)
			.select_from(
				player
				.outerjoin(roles, roles.c.id == player.c.id)
			)
			.where(player.c.name == request.target)
		)
		row = await result.first()
		if row is None:
			await request.reject(
				"NotFound",
				"The player {} was not found."
				.format(request.target)
			)
			return

		new_roles = request.roles
		if row.cfm is not None:
			# The user had previous roles
			current_roles = to_cfm_roles(row.cfm)

			if "dev" in current_roles \
				and "dev" not in new_roles:
				# Trying to dismiss a dev
				await request.reject(
					"Forbidden",
					"Developers have to be dismissed through the DB."
				)
				return

			source_roles = request.user["cfm_roles"]
			if "admin" in current_roles \
				and "admin" not in new_roles \
				and "dev" not in source_roles:
				# Trying to dismiss an admin, while not being a dev
				await request.reject(
					"Forbidden",
					"Administrators have to be dismissed by a developer."
				)
				return

		await request.end()

		new_roles = from_cfm_roles(new_roles)
		await service.send_strict("broadcast:roles", "cfm", **{
			str(row.id): new_roles
		})
		insert_stmt = (
			insert(roles)
			.values(
				id=row.id,
				cfm=new_roles,
				tfm=0
			)
		)
		await conn.execute(
			insert_stmt.on_duplicate_key_update(cfm=new_roles)
		)


@service.on_request("get-privacy")
async def get_privacy(request):
	async with service.db.acquire() as conn:
		result = await conn.execute(
			select(player_privacy)
			.where(player_privacy.c.id == request.auth["user"])
		)
		row = await result.first()

	if row is None:
		await request.send(dict(privacy_fields))

	else:
		response = {}
		for field, _ in privacy_fields:
			response[field] = getattr(row, field)

		await request.send(response)


@service.on_request("set-privacy")
async def set_privacy(request):
	for field in request.privacy:
		if field not in privacy_keys:
			await request.reject("UnknownField", f"Uknown field: {field}")
			return

	if not request.privacy:
		await request.end()
		return

	async with service.db.acquire() as conn:
		insert_stmt = (
			insert(player_privacy)
			.values(id=request.auth["user"], **request.privacy)
		)
		await conn.execute(
			insert_stmt.on_duplicate_key_update(**request.privacy)
		)

	await request.end()


if __name__ == "__main__":
	service.run(workers=int(os.getenv("WORKERS", "2")))
