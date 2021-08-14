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
  `mouse` boolean NOT NULL DEFAULT '1',
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
