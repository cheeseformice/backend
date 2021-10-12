from common import service
from helpers import filter_private, check_needs, fix_dates
from fetch import fetch_player_info, fetch_player_logs, fetch_member_logs
from read import read_history

from shared.logs import PlayerLogs, TribeLogs
from shared.models import tribe, tribe_changelog
from shared.schemas import as_dict

from sqlalchemy import desc
from sqlalchemy.sql import select


@service.on_request("player")
async def player_logs(request):
	user, logs_req = request.id, request.logs
	offset, limit = request.offset, request.limit
	auth = request.auth

	async with service.db.acquire() as conn:
		# Fetch player info and privacy settings
		player_info = await fetch_player_info(conn, user)
		if player_info is None:
			return await request.reject("NotFound", "Player not found")

		# logged in and requesting their own logs?
		privileged: bool = auth is not None and auth["user"] == user
		logs = PlayerLogs.filter(logs_req)
		if not privileged:
			logs = filter_private(logs, player_info)

		# fetch needed logs
		rows = []
		needs_player, needs_member = check_needs(logs)
		if needs_player:
			rows = await fetch_player_logs(conn, user, offset, limit)
		if needs_member:
			rows.extend(await fetch_member_logs(conn, user, offset, limit))

	result, used_dates, stores = read_history(logs, rows)

	response = as_dict("BasicPlayer", player_info)
	response["dates"] = fix_dates(used_dates, stores)
	response.update(result)
	await request.send(response)


@service.on_request("tribe")
async def tribe_logs(request):
	tribe_id, logs_req = request.id, request.logs
	offset, limit = request.offset, request.limit

	async with service.db.acquire() as conn:
		# Fetch tribe info
		result = await conn.execute(
			select(tribe)
			.where(tribe.c.id == tribe_id)
		)
		tribe_info = await result.first()

		if tribe_info is None:
			return await request.reject("NotFound", "Tribe not found")

		# Which logs are you trying to access?
		logs = TribeLogs.filter(logs_req)

		# Fetch necessary information
		result = await conn.execute(
			select(tribe_changelog)
			.where(tribe_changelog.c.id == tribe_id)
			.order_by(desc(tribe_changelog.c.log_id))
			.offset(offset)
			.limit(limit)
		)
		rows = await result.fetchall()

	result, used_dates, stores = read_history(logs, rows)

	response = as_dict("BasicTribe", tribe_info)
	response["dates"] = fix_dates(used_dates, stores)
	response.update(result)
	await request.send(response)
