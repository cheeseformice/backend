CREATE TABLE `member` (
  `id_tribe` bigint(20) NOT NULL,
  `id_member` bigint(20) NOT NULL DEFAULT '0',
  `name` varchar(100) CHARACTER SET utf8 NOT NULL,
  `id_spouse` bigint(20) NOT NULL DEFAULT '0',
  `id_gender` bigint(20) NOT NULL DEFAULT '0',
  `marriage_date` datetime DEFAULT NULL,
  PRIMARY KEY (`id_tribe`,`id_member`),
  KEY `id_member` (`id_member`),
  KEY `name` (`name`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;