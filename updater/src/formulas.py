# Formulas for the composite scores
formulas = {
	"score_stats": (
		"(POWER(`cheese_gathered`, 2) + POWER(`first`, 2) "
		"+ POWER(`saved_mice`, 2)) / `round_played`"
	),
	"score_shaman": (
		"(`shaman_cheese` * 0.05 + `{0}` * 0.2 "
		"+ `{0}_hard`*0.35 + `{0}_divine`*0.5) "
		"/ POWER(GREATEST(`round_played`, 1), 0.25)"
		.format("saved_mice")
	),
	"score_survivor": (
		"(1.6 * `{0}survivor_count` + 0.8 * `{0}mouse_killed`) "
		"/ POWER(GREATEST(`{0}shaman_count` * `{0}round_played`, 1), 0.25)"
		.format("survivor_")
	),
	"score_racing": (
		"(2 * `{0}first` + `{0}podium`) "
		"/ POWER(GREATEST(`{0}round_played` * `{0}finished_map`, 1), 0.25)"
		.format("racing_")
	),
	"score_defilante": (
		"`{0}points` / "
		"POWER(GREATEST(`{0}round_played` * `{0}finished_map`, 1), 0.25)"
		.format("defilante_")
	),
}


overall_formula = (
	"(IFNULL(`score_stats` / {stats}, 0) + "
	"IFNULL(`score_shaman` / {shaman}, 0) + "
	"IFNULL(`score_survivor` / {survivor}, 0) + "
	"IFNULL(`score_racing` / {racing}, 0) + "
	"IFNULL(`score_defilante` / {defilante}, 0))"
)
overall_scores = {
	"alltime": overall_formula.format(
		stats=2723.477,
		shaman=24.956,
		survivor=1.580,
		racing=0.861,
		defilante=2.851,
	),
	"daily": overall_formula.format(
		stats=3.1,
		shaman=0.311,
		survivor=0.056,
		racing=0.074,
		defilante=0.333,
	),
}
overall_scores["weekly"] = overall_scores["daily"]
overall_scores["monthly"] = overall_scores["daily"]
