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


async def write_periodic_rank(tbl, period, days, pool):
	async with pool.acquire() as conn:
		async with conn.cursor() as cursor:
			return await _write_periodic_rank(tbl, period, days, cursor)


async def _write_periodic_rank(tbl, period, days, inte):
	if tbl.is_empty:
		return

	start_from = datetime.now() - timedelta(days=days - 1)
	start_from = start_from.replace(hour=0, minute=0, second=0)

	if tbl.name == "tribe_stats":
		format_name = "tribe@{}".format(period)
		target = "tribe_{}".format(period)
		source = tbl.name
	else:
		format_name = "{}@{}".format(tbl.name, period)
		target = "{}_{}".format(tbl.name, period)
		source = "{}_new".format(tbl.name)

	columns = "`,`".join(stat_columns)
	calculations = ",".join([
		"`n`.`{0}` - `o`.`{0}`"
		.format(column)
		for column in stat_columns
	])
	log = "{}_changelog".format(tbl.name)
	score_formulas = ",".join([
		"`{}` = {}"
		.format(column, formula)
		for column, formula in formulas.items()
	])

	truncate = "TRUNCATE `{}`".format(target)
	calculate_period = (
		"INSERT INTO \
			`{target}` (`id`, `{columns}`) \
		SELECT \
			`n`.`id`, \
			{calculations} \
		FROM \
			`{source}` as `n` \
			INNER JOIN ( \
				SELECT min(`log_id`) as `boundary`, `id` \
				FROM `{log}` \
				WHERE `log_date` >= {start_from} \
				GROUP BY `id` \
			) as `b` ON `b`.`id` = `n`.`id` \
			INNER JOIN `{log}` as `o` \
				ON `o`.`id` = `n`.`id` AND `b`.`boundary` = `o`.`log_id`"
		.format(
			target=target,
			columns=columns,
			calculations=calculations,
			source=source,
			log=log,
			start_from=start_from.strftime("%Y%m%d"),
		)
	)
	scores = (
		"UPDATE `{target}` \
		SET {formulas}"
		.format(
			target=target,
			formulas=score_formulas,
		)
	)
	overall_score = (
		"UPDATE `{target}` \
		SET \
			`score_overall` = {formula}"
		.format(
			target=target,
			formula=overall_scores[period]
		)
	)

	logging.debug("[{}] calculating periods".format(format_name))
	await inte.execute(truncate)
	await inte.execute(calculate_period)
	logging.debug("[{}] calculating scores".format(format_name))
	await inte.execute(scores)
	logging.debug("[{}] calculating overall score".format(format_name))
	await inte.execute(overall_score)
	logging.debug("[{}] done".format(format_name))


async def write_tribe_logs(tribe, stats, inte):
	if not tribe.is_empty:
		stats.is_empty = False
		logging.debug("[tribe] calculating active tribes")

		await inte.execute("TRUNCATE `tribe_active`")
		await inte.execute(
			"INSERT INTO `tribe_active` \
				(`id`, `members`, `active`, `members_sqrt`) \
			\
			SELECT \
				`t`.`id`, \
				COUNT(`m`.`id_member`) as `members`, \
				COUNT(`p`.`id`) as `active`, \
				POWER(COUNT(`m`.`id_member`), 0.5) as `members_sqrt` \
			FROM \
				`tribe` as `t` \
				INNER JOIN `member` as `m` \
					ON `t`.`id` = `m`.`id_tribe` \
				LEFT JOIN `player_new` as `p` \
					ON `m`.`id_member` = `p`.`id` \
			GROUP BY `t`.`id` \
			HAVING `active` > 0"
		)

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

	logging.debug("[tribe] calculating stats")

	# Prepare query
	if tribe.is_empty:
		columns = [
			"COUNT(`m`.`id_member`) as `members`",
			"COUNT(`p_n`.`id`) as `active`",
		]
		div_by = "POWER(COUNT(`m`.`id_member`), 0.5)"
	else:
		columns = [
			"`t`.`members`",
			"`t`.`active`",
		]
		div_by = "`t`.`members_sqrt`"

	for column in stats.columns:
		if column not in (
			"id",
			"members",
			"active",
		):
			columns.append(
				"SUM(`p`.`{0}`) / {1} as `{0}`"
				.format(column, div_by)
			)

	# Run query
	await inte.execute(
		"REPLACE INTO `tribe_stats` \
		SELECT \
			`t`.`id`, \
			{0} \
		FROM \
			`tribe{1}` as `t` \
			INNER JOIN `member` as `m` \
				ON `t`.`id` = `m`.`id_tribe` \
			INNER JOIN `player` as `p` \
				ON `p`.`id` = `m`.`id_member` \
			{2} \
		GROUP BY `t`.`id`"
		.format(
			",".join(columns),
			"" if tribe.is_empty else "_active",

			"LEFT JOIN `player_new` as `p_n` ON `p_n`.`id` = `p`.`id`"
			if tribe.is_empty else
			# No need to join player_new if we are using tribe_active
			""
		)
	)
