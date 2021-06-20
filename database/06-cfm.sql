CREATE TABLE `roles` (
  `id` bigint(20) NOT NULL, -- User ID
  `tfm` int(11) NOT NULL DEFAULT '0', -- TFM Roles
  `cfm` int(11) NOT NULL DEFAULT '0', -- CFM Roles
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `auth` (
  `id` bigint(20) NOT NULL,
  `password` varchar(97) NOT NULL,
  `refresh` int(11) NOT NULL DEFAULT '0',
  `discord` bigint(20),
  PRIMARY KEY (`id`),
  KEY `discord` (`discord`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `player_privacy` (
  `id` bigint(20) NOT NULL,
  `names` boolean NOT NULL DEFAULT '0',
  `soulmate` boolean NOT NULL DEFAULT '0',
  `tribe` boolean NOT NULL DEFAULT '0',
  `look` boolean NOT NULL DEFAULT '0',
  `activity` boolean NOT NULL DEFAULT '0',
  `badges` boolean NOT NULL DEFAULT '1',
  `titles` boolean NOT NULL DEFAULT '1',
  `shaman` boolean NOT NULL DEFAULT '1',
  `normal` boolean NOT NULL DEFAULT '1',
  `survivor` boolean NOT NULL DEFAULT '1',
  `racing` boolean NOT NULL DEFAULT '1',
  `defilante` boolean NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `tribe_privacy` (
  `id` bigint(20) NOT NULL,
  `names` smallint(1) NOT NULL DEFAULT '0',
  `member` smallint(1) NOT NULL DEFAULT '3',
  `active` smallint(1) NOT NULL DEFAULT '2',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `sanctions`(
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `player` boolean NOT NULL DEFAULT '1',
  `subject` bigint(20) NOT NULL DEFAULT '0',

  `mod` bigint(20) NOT NULL DEFAULT '0', -- who made the sanction
  `type` varchar(20) NOT NULL DEFAULT 'unknown',
  `reason` text NOT NULL DEFAULT '',
  `date` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,

  -- 0 = available, 1 = not available, 2 = open, 3 = closed
  `appeal_state` tinyint(2) NOT NULL DEFAULT '0',

  `canceller` bigint(20) DEFAULT NULL, -- who cancelled the sanction
  `cancel_reason` text DEFAULT NULL,
  `cancel_date` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `sanctioned`(`subject`, `player`),
  INDEX `mod`(`mod`),
  INDEX `canceller`(`canceller`),
  INDEX `appeal_state`(`appeal_state`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;

CREATE TABLE `appeal_msg`(
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `sanction` int(11) NOT NULL DEFAULT '0',
  `author` bigint(20) NOT NULL DEFAULT '0',
  -- system msg (for ex. closed, reopened, sanction cancelled...)
  `system` varchar(20) NOT NULL DEFAULT '',
  -- normal msg
  `message` text NOT NULL DEFAULT '',
  `date` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `sanction`(`sanction`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;
