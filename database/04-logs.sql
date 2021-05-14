CREATE TABLE `player_new` LIKE `player`;

CREATE TABLE `player_changelog` LIKE `player`;
ALTER TABLE `player_changelog`
  ADD COLUMN `log_id` int(11) NOT NULL AUTO_INCREMENT FIRST,
  ADD COLUMN `log_date` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER `log_id`,
  DROP PRIMARY KEY,
  ADD PRIMARY KEY (`log_id`),
  ADD KEY (`log_date`),
  ADD KEY (`id`);

CREATE TABLE `tribe_new` LIKE `tribe`;

CREATE TABLE `tribe_active` (
  `id` bigint(20) NOT NULL DEFAULT '0',
  `members` bigint(20) NOT NULL DEFAULT '0',
  `active` bigint(20) NOT NULL DEFAULT '0',
  `members_sqrt` bigint(20) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;

CREATE TABLE `tribe_changelog` LIKE `tribe`;
ALTER TABLE `tribe_changelog`
  ADD COLUMN `log_id` int(11) NOT NULL AUTO_INCREMENT FIRST,
  ADD COLUMN `log_date` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER `log_id`,
  DROP PRIMARY KEY,
  ADD PRIMARY KEY (`log_id`),
  ADD KEY (`log_date`),
  ADD KEY (`id`);

CREATE TABLE `tribe_stats_changelog` LIKE `tribe_stats`;
ALTER TABLE `tribe_stats_changelog`
  ADD COLUMN `log_id` int(11) NOT NULL AUTO_INCREMENT FIRST,
  ADD COLUMN `log_date` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER `log_id`,
  DROP PRIMARY KEY,
  ADD PRIMARY KEY (`log_id`),
  ADD KEY (`log_date`),
  ADD KEY (`id`);

CREATE TABLE `member_new` LIKE `member`;

CREATE TABLE `member_changelog` LIKE `member`;
ALTER TABLE `member_changelog`
  ADD COLUMN `log_id` int(11) NOT NULL AUTO_INCREMENT FIRST,
  ADD COLUMN `log_date` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER `log_id`,
  DROP PRIMARY KEY,
  ADD PRIMARY KEY (`log_id`),
  ADD KEY (`log_date`),
  ADD KEY (`id_member`);
