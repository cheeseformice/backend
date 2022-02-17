import asyncio
import logging

from datetime import datetime, timedelta

from table import Table
from utils import env
from formulas import formulas, overall_scores


stat_columns = (
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
)


async def post_update(player, tribe, member, cfm, a801):
	tribe_stats = Table("tribe_stats")
	# Extract stats info
	await tribe_stats.extract_info(cfm, env.cfm_db, hashes=False)

	async with cfm.acquire() as conn:
		async with conn.cursor() as inte:
			await write_tribe_logs(tribe, tribe_stats, inte)

			for table in ("player", "tribe_stats"):
				await update_log_pointers(table, inte)

	return await asyncio.wait([
		write_periodic_rank(tbl, period, days, cfm)
		for (tbl, period, days) in (
			(player, "daily", 1),
			(player, "weekly", 7),
			(player, "monthly", 30),
			(tribe_stats, "daily", 1),
			(tribe_stats, "weekly", 7),
			(tribe_stats, "monthly", 30),
		)
	])


async def update_log_pointers(tbl, inte):
	tribe = 1 if tbl == "tribe_stats" else 0
	logging.debug("[{}] inserting new log pointers".format(tbl))
	await inte.execute(
		"INSERT INTO `last_log` (`tribe`, `id`) \
		SELECT \
			{tribe} as `tribe`, \
			`new`.`id` \
		FROM \
			`{table}` as `new` \
			LEFT JOIN `last_log` as `ptr` \
				ON `ptr`.`tribe` = {tribe} AND `ptr`.`id` = `new`.`id` \
		WHERE `ptr`.`id` IS NULL"
		.format(
			tribe=tribe,
			table="player_new" if tbl == "player" else "tribe_active",
		)
	)

	for days, period in ((1, "day"), (7, "week"), (30, "month")):
		logging.debug(
			"[{}] updating log pointers for a {} ago".format(tbl, period)
		)

		start = datetime.now() - timedelta(days=days)
		end = datetime.now() - timedelta(days=days - 1)
		await inte.execute(
			"UPDATE \
				`last_log` as `ptr` \
				INNER JOIN `{table}` as `log` \
					ON `log`.`id` = `ptr`.`id` \
					AND `log`.`log_date` >= '{start}' \
					AND `log`.`log_date` < '{end}' \
			SET `{period}` = `log`.`log_id` \
			WHERE `ptr`.`tribe` = {tribe}"
			.format(
				tribe=tribe,
				start=start.strftime("%Y-%m-%d"),
				end=end.strftime("%Y-%m-%d"),
				period=period,
				table=f"{tbl}_changelog"
			)
		)


async def write_periodic_rank(tbl, period, days, pool):
	async with pool.acquire() as conn:
		async with conn.cursor() as cursor:
			return await _write_periodic_rank(tbl, period, days, cursor)


async def _write_periodic_rank(tbl, period, days, inte):
	if tbl.is_empty:
		# No historic data to use
		return

	start = datetime.now() - timedelta(days=days - 1)

	if tbl.name == "tribe_stats":
		format_name = "tribe@{}".format(period)
		target = "tribe_{}".format(period)
	else:
		format_name = "{}@{}".format(tbl.name, period)
		target = "{}_{}".format(tbl.name, period)

	columns = "`,`".join(stat_columns)
	calculations = ",".join([
		"`c`.`{0}` - `o`.`{0}`"
		.format(column)
		for column in stat_columns
	])
	log = "{}_changelog".format(tbl.name)
	score_formulas = ",".join([
		"`{}` = {}"
		.format(column, formula)
		for column, formula in formulas.items()
	])

	if period == "daily":
		period_unit = "day"
	elif period == "weekly":
		period_unit = "week"
	elif period == "monthly":
		period_unit = "month"

	await inte.execute(f"TRUNCATE `{target}`")
	logging.debug("[{}] calculating periods".format(format_name))
	await inte.execute(
		"INSERT INTO \
			`{target}` (`id`, `{columns}`) \
		SELECT \
			`n`.`id`, \
			{calculations} \
		FROM \
			( \
				SELECT MAX(`log_id`) as `log_id`, `id` \
				FROM `{log}` \
				WHERE `log_date` >= '{start}' \
				GROUP BY `id` \
			) as `n` \
			INNER JOIN `last_log` as `ptr` \
				ON `ptr`.`tribe` = {tribe} \
				AND `ptr`.`id` = `n`.`id` \
			INNER JOIN `{log}` as `o` \
				ON `o`.`id` = `n`.`id` \
				AND `ptr`.`{period}` = `o`.`log_id` \
			INNER JOIN `{log}` as `c` \
				ON `c`.`id` = `n`.`id` \
				AND `c`.`log_id` = `n`.`log_id`"
		.format(
			target=target,
			columns=columns,
			calculations=calculations,
			log=log,
			tribe=1 if tbl.name == "tribe_stats" else 0,
			start=start.strftime("%Y-%m-%d"),
			period=period_unit,
		)
	)

	logging.debug("[{}] calculating scores".format(format_name))
	await inte.execute(
		"UPDATE `{target}` \
		SET {formulas}"
		.format(
			target=target,
			formulas=score_formulas,
		)
	)

	logging.debug("[{}] calculating overall score".format(format_name))
	await inte.execute(
		"UPDATE `{target}` \
		SET \
			`score_overall` = {formula}"
		.format(
			target=target,
			formula=overall_scores[period]
		)
	)

	logging.debug("[{}] done".format(format_name))


async def write_tribe_logs(tribe, stats, inte):
	if not tribe.is_empty:
		stats.is_empty = False
		logging.debug("[tribe] calculating active tribes")

		await inte.execute("TRUNCATE `tribe_active`")
		await inte.execute(
			"INSERT INTO `tribe_active` \
				(`id`, `members`, `active`) \
			\
			SELECT \
				`t`.`id`, \
				COUNT(`m`.`id_member`) as `members`, \
				COUNT(`p`.`id`) as `active` \
			FROM \
				`tribe` as `t` \
				INNER JOIN `member` as `m` \
					ON `t`.`id` = `m`.`id_tribe` \
				LEFT JOIN `player_new` as `p` \
					ON `m`.`id_member` = `p`.`id` \
			GROUP BY `t`.`id` \
			HAVING `active` > 0"
		)

	logging.debug("[tribe] calculating stats")

	# Prepare query
	stats_columns = ["id", "members", "active"]
	if tribe.is_empty:
		columns = [
			"COUNT(`m`.`id_member`) as `members`",
			"COUNT(`p_n`.`id`) as `active`",
		]
	else:
		columns = [
			"`t`.`members`",
			"`t`.`active`",
		]

	for column in stats.columns:
		if column not in (
			"id",
			"members",
			"active",
		):
			columns.append(
				"SUM(`p`.`{0}`) as `{0}`"
				.format(column,)
			)
			stats_columns.append(column)

	# Run query
	await inte.execute(
		"REPLACE INTO `tribe_stats` (`{3}`) \
		SELECT \
			`t`.`id`, \
			{0} \
		FROM \
			`tribe{1}` as `t` \
			INNER JOIN `member` as `m` \
				ON `t`.`id` = `m`.`id_tribe` \
			INNER JOIN `player` as `p` \
				ON `p`.`id` = `m`.`id_member` \
			LEFT JOIN `disqualified` as `d` \
				ON `d`.`id` = `p`.`id` \
			{2} \
		WHERE `d`.`id` IS NULL \
		GROUP BY `t`.`id`"
		.format(
			",".join(columns),
			"" if tribe.is_empty else "_active",

			"LEFT JOIN `player_new` as `p_n` ON `p_n`.`id` = `p`.`id`"
			if tribe.is_empty else
			# No need to join player_new if we are using tribe_active
			"",

			"`,`".join(stats_columns),
		)
	)

	logging.debug("[tribe] calculating scores")
	await inte.execute(
		"UPDATE `tribe_stats` as `t` {1} \
		SET {0}"
		.format(
			",".join((
				"`t`.`{}` = {}"
				.format(column, formula)
				for column, formula in formulas.items()
			)),

			""
			if tribe.is_empty else
			"INNER JOIN `tribe_active` as `a` ON `a`.`id` = `t`.`id`"
		)
	)
	await inte.execute(
		"UPDATE `tribe_stats` as `t` {1} \
		SET `t`.`score_overall` = {0}"
		.format(
			overall_scores["alltime"],

			""
			if tribe.is_empty else
			"INNER JOIN `tribe_active` as `a` ON `a`.`id` = `t`.`id`"
		)
	)

	# Write changelogs
	if not tribe.is_empty:
		logging.debug("[tribe] write stats changelogs")
		await inte.execute(
			"INSERT INTO `tribe_stats_changelog` (`{}`) \
			SELECT `o`.* \
			FROM `tribe_active` as `n` \
			INNER JOIN `tribe_stats` as `o` ON `n`.`id` = `o`.`id`"
			.format(
				"`,`".join(stats.write_columns)
			)
		)
