import re
import aiohttp

from collections import namedtuple

from shared.models import player, player_changelog

from sqlalchemy import or_
from sqlalchemy.sql import select


User = namedtuple("User", "id old_name new_name changed")
TEAM_API = "http://discorddb.000webhostapp.com/get?k=&e=json&f=teamList&i=1"
A801_API = "https://atelier801.com/staff-ajax?role={}"
A801_REGEX = (
	r'([^ <]+)<span class="font-s couleur-hashtag-pseudo"> (#\d{4})</span>'
)
tfm_roles = (
	# role, api
	# api: int -> from atelier801.com
	# api: str -> from discorddb
	("admin", 128),
	("mod", 1),
	("sentinel", 4),
	("mapcrew", 16),
	("module", "mt"),
	("funcorp", "fc"),
	("fashion", "fs"),
)

service = None


def set_service(new):
	global service
	service = new


async def fetch_users(conditions, conn):
	result = await conn.execute(
		select(
			player_changelog.c.id,
			player_changelog.c.name,
			player.c.name.label("new_name"),
		)
		.select_from(
			player_changelog
			.join(player, player.c.id == player_changelog.c.id)
		)
		.where(or_(*conditions))
		.group_by(player_changelog.c.name)
	)
	return await result.fetchall()


async def get_new_names(names, only_changed=False, conn=None):
	users = {}
	for name in names:
		if "#" not in name:
			name += "#0000"

		users[name.lower()] = User(
			id=None,
			old_name=name,
			new_name=None,
			changed=None,
		)

	if not users:
		return users

	# in_() doesn't work, we have to manually add eq checks
	name_in = [
		player_changelog.c.name == user.old_name
		for user in users
	]

	if conn is None:
		# Conn was not provided, get a new one
		async with service.db.acquire() as conn:
			result = await fetch_users(name_in, conn)
	else:
		result = await fetch_users(name_in, conn)

	for row in result:
		old_name = row.name.lower()

		user = users[old_name]
		user.id = row.id
		user.new_name = row.new_name
		user.changed = old_name != row.new_name.lower()

	if only_changed:
		return list(filter(lambda user: user.changed, users.values()))
	return list(users.values())


async def download_teams():
	teams = {}  # team_name: {user_name, user_name}
	names = set()

	async with aiohttp.ClientSession() as sess:
		# Download team API members
		async with sess.get(TEAM_API) as resp:
			result = await resp.json()

			for team, members in result.items():
				members = list(members.keys())
				names = names.union(members)

				# Check if we need to store this role
				for role, api in tfm_roles:
					if api == team:
						break
				else:
					continue

				teams[role] = set(members)

		# Download all needed A801 teams
		for role, api in tfm_roles:
			if not isinstance(api, int):
				continue

			async with sess.get(A801_API.format(api)) as resp:
				members = []

				content = await resp.read()
				for name, tag in re.findall(A801_REGEX, content.decode()):
					name = f"{name}{tag}"
					members.append(name)

				names = names.union(members)
				teams[role] = set(members)

	return teams, names
