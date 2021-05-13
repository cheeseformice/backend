CREATE TABLE `member` (
  `id_tribe` bigint(20) NOT NULL,
  `id_member` bigint(20) NOT NULL DEFAULT '0',
  `id_spouse` bigint(20) NOT NULL DEFAULT '0',
  `id_gender` bigint(20) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id_member`),
  KEY `id_tribe` (`id_tribe`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;
