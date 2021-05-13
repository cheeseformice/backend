-- These are created after logs are created, so they don't have these indexes

CREATE INDEX `round_played` ON `player`(`round_played`);
CREATE INDEX `cheese_gathered` ON `player`(`cheese_gathered`);
CREATE INDEX `first` ON `player`(`first`);
CREATE INDEX `bootcamp` ON `player`(`bootcamp`);
CREATE INDEX `score_stats` ON `player`(`score_stats`);
CREATE INDEX `score_shaman` ON `player`(`score_shaman`);
CREATE INDEX `score_survivor` ON `player`(`score_survivor`);
CREATE INDEX `score_racing` ON `player`(`score_racing`);
CREATE INDEX `score_defilante` ON `player`(`score_defilante`);
CREATE INDEX `score_overall` ON `player`(`score_overall`);

CREATE INDEX `round_played` ON `tribe_stats`(`round_played`);
CREATE INDEX `cheese_gathered` ON `tribe_stats`(`cheese_gathered`);
CREATE INDEX `first` ON `tribe_stats`(`first`);
CREATE INDEX `bootcamp` ON `tribe_stats`(`bootcamp`);
CREATE INDEX `score_stats` ON `tribe_stats`(`score_stats`);
CREATE INDEX `score_shaman` ON `tribe_stats`(`score_shaman`);
CREATE INDEX `score_survivor` ON `tribe_stats`(`score_survivor`);
CREATE INDEX `score_racing` ON `tribe_stats`(`score_racing`);
CREATE INDEX `score_defilante` ON `tribe_stats`(`score_defilante`);
CREATE INDEX `score_overall` ON `tribe_stats`(`score_overall`);

CREATE TABLE `temp_rank_boilerplate`(
  `id` bigint(20) NOT NULL DEFAULT '0',

  `shaman_cheese` int(11) DEFAULT NULL,
  `saved_mice` int(11) DEFAULT NULL,
  `saved_mice_hard` int(11) DEFAULT NULL,
  `saved_mice_divine` int(11) DEFAULT NULL,

  `round_played` int(11) DEFAULT NULL,
  `cheese_gathered` int(11) DEFAULT NULL,
  `first` int(11) DEFAULT NULL,
  `bootcamp` int(11) DEFAULT NULL,

  `survivor_round_played` int(11) DEFAULT NULL,
  `survivor_mouse_killed` int(11) DEFAULT NULL,
  `survivor_shaman_count` int(11) DEFAULT NULL,
  `survivor_survivor_count` int(11) DEFAULT NULL,

  `racing_round_played` int(11) DEFAULT NULL,
  `racing_finished_map` int(11) DEFAULT NULL,
  `racing_first` int(11) DEFAULT NULL,
  `racing_podium` int(11) DEFAULT NULL,

  `defilante_round_played` int(11) DEFAULT NULL,
  `defilante_finished_map` int(11) DEFAULT NULL,
  `defilante_points` int(11) DEFAULT NULL,

  `score_stats` int(11) DEFAULT NULL,
  `score_shaman` int(11) DEFAULT NULL,
  `score_survivor` int(11) DEFAULT NULL,
  `score_racing` int(11) DEFAULT NULL,
  `score_defilante` int(11) DEFAULT NULL,
  `score_overall` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `round_played`(`round_played`),
  INDEX `cheese_gathered`(`cheese_gathered`),
  INDEX `first`(`first`),
  INDEX `bootcamp`(`bootcamp`),
  INDEX `score_stats`(`score_stats`),
  INDEX `score_shaman`(`score_shaman`),
  INDEX `score_survivor`(`score_survivor`),
  INDEX `score_racing`(`score_racing`),
  INDEX `score_defilante`(`score_defilante`),
  INDEX `score_overall`(`score_overall`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;

CREATE TABLE `tribe_daily` LIKE `temp_rank_boilerplate`;
CREATE TABLE `player_daily` LIKE `temp_rank_boilerplate`;
CREATE TABLE `tribe_weekly` LIKE `temp_rank_boilerplate`;
CREATE TABLE `player_weekly` LIKE `temp_rank_boilerplate`;
CREATE TABLE `tribe_monthly` LIKE `temp_rank_boilerplate`;
CREATE TABLE `player_monthly` LIKE `temp_rank_boilerplate`;

DROP TABLE `temp_rank_boilerplate`;
