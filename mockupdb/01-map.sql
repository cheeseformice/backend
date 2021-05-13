CREATE TABLE `map` (
  `id` int(11) NOT NULL,
  `author` varchar(100) NOT NULL,
  `xml` text NOT NULL,
  `p` tinyint(4) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;