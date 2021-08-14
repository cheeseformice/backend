import sqlalchemy as sa


metadata = sa.MetaData()


def to_columns(fields):
	columns = []
	for field in fields:
		if isinstance(field[-1], dict):
			kwargs = field[-1]
			field = field[:-1]
		else:
			kwargs = {}

		columns.append(sa.Column(*field, **kwargs))
	return columns


def to_stats_fields(names):
	return list(map(lambda name: (name, sa.Integer), names))


# Website tables
roles = sa.Table(
	"roles", metadata,
	sa.Column("id", sa.BigInteger, primary_key=True),
	sa.Column("tfm", sa.Integer),
	sa.Column("cfm", sa.Integer),
)

auth = sa.Table(
	"auth", metadata,
	sa.Column("id", sa.BigInteger, primary_key=True),
	sa.Column("password", sa.String(97)),
	sa.Column("refresh", sa.Integer, default=0),
	sa.Column("discord", sa.Integer, index=True),
)

player_privacy = sa.Table(
	"player_privacy", metadata,
	sa.Column("id", sa.BigInteger, primary_key=True),
	sa.Column("names", sa.Boolean, nullable=False, default=False),
	sa.Column("soulmate", sa.Boolean, nullable=False, default=False),
	sa.Column("tribe", sa.Boolean, nullable=False, default=False),
	sa.Column("look", sa.Boolean, nullable=False, default=False),
	sa.Column("activity", sa.Boolean, nullable=False, default=False),
	sa.Column("badges", sa.Boolean, nullable=False, default=True),
	sa.Column("titles", sa.Boolean, nullable=False, default=True),
	sa.Column("shaman", sa.Boolean, nullable=False, default=True),
	sa.Column("mouse", sa.Boolean, nullable=False, default=True),
	sa.Column("survivor", sa.Boolean, nullable=False, default=True),
	sa.Column("racing", sa.Boolean, nullable=False, default=True),
	sa.Column("defilante", sa.Boolean, nullable=False, default=True),
)


# Transformice information
stats = (
	"shaman_cheese",
	"saved_mice",
	"saved_mice_hard",
	"saved_mice_divine",

	"round_played",
	"cheese_gathered",
	"first",
	"bootcamp",

	"survivor_round_played",
	"survivor_mouse_killed",
	"survivor_shaman_count",
	"survivor_survivor_count",

	"racing_round_played",
	"racing_finished_map",
	"racing_first",
	"racing_podium",

	"defilante_round_played",
	"defilante_finished_map",
	"defilante_points",

	"score_stats",
	"score_shaman",
	"score_survivor",
	"score_racing",
	"score_defilante",
	"score_overall",
)

player = sa.Table(
	"player", metadata,
	sa.Column("id", sa.BigInteger, primary_key=True),
	sa.Column("name", sa.String(100), index=True),

	sa.Column("title", sa.Text),
	sa.Column("badges", sa.Text),
	sa.Column("unlocked_titles", sa.Text),

	sa.Column("look", sa.Text),
	sa.Column("dress_list", sa.Text),
	sa.Column("color1", sa.Text),
	sa.Column("color2", sa.Text),

	sa.Column("experience", sa.Integer),
	*to_columns(to_stats_fields(stats)),
)

member = sa.Table(
	"member", metadata,
	sa.Column("id_tribe", sa.BigInteger, primary_key=True),
	sa.Column("id_member", sa.BigInteger, primary_key=True),
	sa.Column("id_spouse", sa.BigInteger),
	sa.Column("id_gender", sa.BigInteger),
)

tribe = sa.Table(
	"tribe", metadata,
	sa.Column("id", sa.BigInteger, primary_key=True),
	sa.Column("name", sa.String(50), index=True),
)

tribe_stats = sa.Table(
	"tribe_stats", metadata,
	sa.Column("id", sa.BigInteger, primary_key=True),

	sa.Column("members", sa.BigInteger),
	sa.Column("active", sa.BigInteger),

	*to_columns(to_stats_fields(stats)),
)


# Changelogs
changelog_fields = (
	("log_id", sa.Integer, {"primary_key": True}),
	("log_date", sa.DateTime, {
		"index": True, "server_default": sa.text("NOW()")
	}),
)

player_changelog = sa.Table(
	"player_changelog", metadata,
	*to_columns(changelog_fields),
	sa.Column("id", sa.BigInteger, index=True),
	sa.Column("name", sa.String(100), index=True),

	sa.Column("badges", sa.Text),
	sa.Column("unlocked_titles", sa.Text),
	sa.Column("look", sa.Text),

	sa.Column("experience", sa.Integer),
	*to_columns(to_stats_fields(stats)),
)

tribe_changelog = sa.Table(
	"tribe_stats_changelog", metadata,
	*to_columns(changelog_fields),
	sa.Column("id", sa.BigInteger, index=True),
	sa.Column("members", sa.BigInteger),
	sa.Column("active", sa.BigInteger),
	*to_columns(to_stats_fields(stats)),
)

member_changelog = sa.Table(
	"member_changelog", metadata,
	*to_columns(changelog_fields),
	sa.Column("id_tribe", sa.BigInteger, index=True),
	sa.Column("id_member", sa.BigInteger, index=True),
	sa.Column("id_spouse", sa.BigInteger),
)


# Periodic leaderboards
def temp_rank_table(name):
	return sa.Table(
		name, metadata,
		sa.Column("id", sa.BigInteger, primary_key=True),
		*to_columns(to_stats_fields(stats)),
	)


periods = {
	"player": {
		"overall": player,
		"daily": temp_rank_table("player_daily"),
		"weekly": temp_rank_table("player_weekly"),
		"monthly": temp_rank_table("player_monthly"),
	},
	"tribe": {
		"overall": tribe_stats,
		"daily": temp_rank_table("tribe_daily"),
		"weekly": temp_rank_table("tribe_weekly"),
		"monthly": temp_rank_table("tribe_monthly"),
	},
}
