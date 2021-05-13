# updater
Database updater: detect all changes in a801's database and pull them

## Performance
**Memory usage** depends on the similarity in both tables; if the rows are in the same order (or just a few are misplaced), it will be minimal, but if they aren't similar at all, it can get really big if the databases are big. Python uses nearly **20MB** and when we ran this updater, **it didn't go over that threshold.**

**Speed** depends on CPU speed and bandwidth. In our setup, we have an Intel Core Processor **(2.4GHz, 1 core) and 250Mbit/s** for bandwidth, and it checks **150000 rows per second** (transferring the whole database, with about **100 million users in about 14 minutes**)

## How it works
This updater acts as a middle-man between both databases (external & internal) and its purpose is to replicate the external (a801) one. Keeping in mind that their database is HUGE (near 100mil users), and this replication process has to be very quick.

The first idea that came to my mind was a big `SELECT` query on their database and then many small `INSERT` ones in ours (and that is partly what we still do!), however, it takes nearly 5-6 hours to do just that, so I thought of this smarter approach:

First, we optimize our database for reads (the MyISAM database engine does a good job, but there are better ones), and we also store CRC32 hashes (4 bytes) for each row: just concatenate every column in every row into a string and then apply this hash on them.

Second, we send a query to the external database requesting only row ID and this CRC32 hash. We then compare them with our hashes, and if they match that means the row hasn't been modified, so we just ignore that row.

Third, from the rows that do not match their hash, we fetch the rest of the data from the external database and store that, with the new hash in our DB.

This means that the first time it runs it takes nearly 5-6 hours because it doesn't have anything to compare, so it has to read and write A LOT of data, but from the second run it takes nearly 1 hour **using only python and not pypy**. That's a 5x speed improvement!

## How to use
You can use our [mockupdb](../mockupdb), which is just a mockup of Atelier801's database (obviously, with way less data) and our [database](../database) to write the data to.

In case you have access to the real Atelier801's database, you can just plug your credentials in the environment variables and that should be it.

On the first run, your database should NOT have any data, other than the tables.
