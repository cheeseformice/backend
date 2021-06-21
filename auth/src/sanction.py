from enum import IntEnum
from common import service, env

from shared.models import roles, player, tribe, sanctions, appeal_msg
from shared.schemas import as_dict, as_dict_list
from sqlalchemy import and_, or_, desc, func
from sqlalchemy.sql import select

import aiohttp


link = "https://cheese.formice.com"


class AuthLevel(IntEnum):
	user = 0
	mod = 1
	admin = 2


def get_auth(request):
	roles = request.user["cfm_roles"]
	if "dev" in roles or "admin" in roles:
		return AuthLevel.admin

	if "mod" in roles:
		return AuthLevel.mod

	return AuthLevel.user


def profile_link(is_player, name, _id):
	return f"[{name}]({link}/{'p' if is_player else 't'}/{_id}): `{_id}`"


async def sanction_notification(sanction):
	subject_type = "Player" if sanction.player else "Tribe"
	subject = profile_link(
		sanction.player, sanction.subject_name, sanction.subject
	)
	fields = [
		{
			"name": "Subject",
			"value": f"{subject_type}\n{subject}",
			"inline": True
		},
		{
			"name": "Sanction type",
			"value": sanction.type.capitalize(),
			"inline": True
		},
		{
			"name": "Responsible moderator",
			"value": profile_link(True, sanction.mod_name, sanction.mod),
			"inline": True
		},
		{
			"name": "Sanction date",
			"value": sanction.date.strftime("%Y-%m-%d %H:%M:%S UTC"),
			"inline": True
		},
		{
			"name": "Sanction reason",
			"value": sanction.reason
		}
	]

	if sanction.canceller is None:
		title = f"New sanction #{sanction.id}"
		color = 0xC10015
	else:
		title = f"Sanction #{sanction.id} cancelled"
		color = 0xF2C037
		fields.extend([
			{
				"name": "Canceller",
				"value": profile_link(
					True, sanction.canceller_name, sanction.canceller
				),
				"inline": True
			},
			{
				"name": "Cancellation date",
				"value": sanction.cancel_date.strftime(
					"%Y-%m-%d %H:%M:%S UTC"
				),
				"inline": True
			},
			{
				"name": "Cancellation reason",
				"value": sanction.cancel_reason
			},
		])

	info = f"{link}/sanction/{sanction.id}"
	history = f"{link}/p/{sanction.subject}/sanctions"
	fields.append({
		"name": "Useful links",
		"value": (
			f"[Sanction information]({info}) - "
			f"[Subject sanction history]({history})"
		)
	})

	async with aiohttp.ClientSession() as session:
		await session.post(env.sanction_webhook, json={
			"embed": {
				"title": title,
				"color": color,
				"fields": fields,
			}
		}, headers={
			"Content-Type": "application/json"
		})


def fetch_player_query():
	return select(
		player.c.id,
		player.c.name,
		roles.c.cfm_roles,
		roles.c.tfm_roles,
	).select_from(player)


def fetch_tribe_query():
	return select(
		tribe.c.id,
		tribe.c.name,
	).select_from(tribe)


def fetch_sanctions_query(fetch_mod_names=False, fetch_many=False):
	to_select = (
		sanctions.c.id,
		sanctions.c.player,
		sanctions.c.subject,

		sanctions.c.type,
		sanctions.c.reason,
		sanctions.c.date,

		sanctions.c.appeal_state,

		sanctions.c.cancel_reason,
		sanctions.c.cancel_date,
	)
	select_from = sanctions

	if fetch_mod_names:
		mod = player.alias()
		mod_roles = roles.alias()
		canceller = player.alias()
		canceller_roles = roles.alias()

		to_select.extend((
			mod.c.id.label("mod_id"),
			mod.c.name.label("mod_name"),
			mod_roles.c.cfm_roles.label("mod_cfm_roles"),
			mod_roles.c.tfm_roles.label("mod_tfm_roles"),

			canceller.c.id.label("canceller_id"),
			canceller.c.name.label("canceller_name"),
			canceller_roles.c.cfm_roles.label("canceller_cfm_roles"),
			canceller_roles.c.tfm_roles.label("canceller_tfm_roles"),
		))
		select_from = (
			select_from
			.join(mod, mod.c.id == sanctions.c.mod)
			.outerjoin(mod_roles, mod_roles.c.id == sanctions.c.mod)
			.outerjoin(canceller, canceller.c.id == sanctions.c.canceller)
			.outerjoin(
				canceller_roles, canceller_roles.c.id == sanctions.c.mod
			)
		)

	if fetch_many:
		to_select.append(func.count(appeal_msg.c.id).label("messages"))
		select_from = select_from.outerjoin(
			appeal_msg, appeal_msg.c.sanction == sanctions.c.id
		)

	query = select(*to_select).select_from(select_from)
	if fetch_many:
		return query.group_by(sanctions.c.id)
	return query


@service.on_request("get-sanctions")
async def get_sanctions(request):
	auth = get_auth(request)

	if auth is AuthLevel.user:
		if request.subject is None or \
			request.subject != request.user["user"]:
			await request.reject("MissingPrivileges")
			return

	async with service.db.acquire() as conn:
		query = fetch_sanctions_query(
			fetch_mod_names=auth is not AuthLevel.user,
			fetch_many=True
		)
		if request.subject is not None:
			query = query.where(and_(
				sanctions.c.player == request.is_player,
				sanctions.c.subject == request.subject
			))

		players, tribes = set(), set()
		result = await conn.execute(
			query.order_by(desc(sanctions.c.id))
			.offset(request.offset).limit(request.limit)
		)
		sanction_list = await result.fetchall()

		# Fetch all subjects
		for sanction in sanction_list:
			container = players if sanction.player else tribes
			container.add(sanction.subject)

		if len(players) > 0:
			result = await conn.execute(
				fetch_player_query().where(or_(player.c.id == 0, *[
					player.c.id == subject
					for subject in players
				]))
			)
			players = {
				row.id: as_dict("BasicPlayer", row)
				for row in await result.fetchall()
			}

		if len(tribes) > 0:
			result = await conn.execute(
				fetch_tribe_query().where(or_(tribe.c.id == 0, *[
					tribe.c.id == subject
					for subject in tribes
				]))
			)
			tribes = {
				row.id: as_dict("BasicTribe", row)
				for row in await result.fetchall()
			}

	response = as_dict_list("SanctionContainer", sanction_list)
	for idx, sanction in enumerate(response):
		# Add the sanction subject to each sanction
		container = players if sanction_list[idx].player else tribes
		sanction["subject"].update(container[sanction_list[idx].subject])

	await request.send(response)


@service.on_request("get-sanction")
async def get_sanction(request):
	auth = get_auth(request)

	async with service.db.acquire() as conn:
		result = await conn.execute(
			fetch_sanctions_query(
				fetch_mod_names=auth is not AuthLevel.user,
				fetch_many=False
			).where(sanctions.c.id == request.sanction)
		)
		sanction = await result.first()
		if sanction is None:
			await request.send(None)
			return

		if auth is AuthLevel.user and not (
			sanction.player and sanction.subject == request.user["user"]
		):
			# The subject is not this user, and they don't have other powers
			await request.reject("MissingPrivileges")
			return

		# Fetch subject
		if sanction.player:
			result = await conn.execute(
				fetch_player_query().where(player.c.id == sanction.subject)
			)
			subject = as_dict("BasicPlayer", await result.first())
		else:
			result = await conn.execute(
				fetch_tribe_query().where(tribe.c.id == sanction.subject)
			)
			subject = as_dict("BasicTribe", await result.first())

		# Fetch appeal messages (if any!)
		messages = []
		if sanction.appeal_state in (2, 3):  # open or closed
			result = await conn.execute(
				select(
					appeal_msg.c.id,
					player.c.id.label("author_id"),
					player.c.id.label("author_name"),
					roles.c.cfm_roles.label("author_cfm_roles"),
					roles.c.tfm_roles.label("author_tfm_roles"),
					appeal_msg.c.system,
					appeal_msg.c.message,
					appeal_msg.c.date,
				)
				.select_from(
					appeal_msg
					.join(player, player.c.id == appeal_msg.c.author)
					.outerjoin(roles, roles.c.id == appeal_msg.c.author)
				)
				.where(appeal_msg.c.sanction == request.sanction)
			)
			messages = as_dict_list("AppealMessage", await result.fetchall())

	if auth is AuthLevel.user:
		for message in messages:
			# Hide system messages unless mod or admin
			if message["system"]:
				message["author"] = None

	response = as_dict("SanctionContainer", sanction)
	response["subject"].update(subject)
	response["appeal"]["messages"] = messages
	await request.send(response)


@service.on_request("sanction")
async def sanction(request):
	pass


@service.on_request("cancel-sanction")
async def cancel_sanction(request):
	pass


@service.on_request("post-appeal-msg")
async def post_appeal_msg(request):
	pass


@service.on_request("change-appeal-state")
async def change_appeal_state(request):
	pass
