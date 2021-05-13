CREATE TABLE `lastupdate_transformice` (
  `label` varchar(100) DEFAULT NULL,
  `lastupdate` datetime DEFAULT NULL,
  UNIQUE KEY `label` (`label`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;

CREATE TABLE `lastupdate_tribulle` (
  `label` varchar(100) DEFAULT NULL,
  `lastupdate` datetime DEFAULT NULL,
  UNIQUE KEY `label` (`label`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;