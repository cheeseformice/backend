CREATE TABLE `tribe` (
  `id` bigint(20) NOT NULL DEFAULT '0',
  `name` varchar(50) CHARACTER SET utf8 NOT NULL,
  PRIMARY KEY (`id`),
  KEY `name` (`name`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;

CREATE TABLE `tribe_stats` (
  `id` bigint(20) NOT NULL DEFAULT '0',
  `members` bigint(20) NOT NULL DEFAULT '0',
  `active` bigint(20) NOT NULL DEFAULT '0',

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
  PRIMARY KEY (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;
