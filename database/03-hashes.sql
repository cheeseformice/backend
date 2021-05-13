CREATE TABLE `hashes_boilerplate` (
  `id` bigint(20) NOT NULL,
  `hashed` int(11) UNSIGNED NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;

CREATE TABLE `player_hashes_0` LIKE `hashes_boilerplate`;
CREATE TABLE `player_hashes_1` LIKE `hashes_boilerplate`;

CREATE TABLE `tribe_hashes_0` LIKE `hashes_boilerplate`;
CREATE TABLE `tribe_hashes_1` LIKE `hashes_boilerplate`;

CREATE TABLE `member_hashes_0` LIKE `hashes_boilerplate`;
CREATE TABLE `member_hashes_1` LIKE `hashes_boilerplate`;

DROP TABLE `hashes_boilerplate`;
