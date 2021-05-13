CREATE TABLE `tribe` (
  `id` bigint(20) NOT NULL DEFAULT '0',
  `name` varchar(50) CHARACTER SET utf8 NOT NULL,
  PRIMARY KEY (`id`),
  KEY `name` (`name`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;