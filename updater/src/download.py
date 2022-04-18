import sys
import math  # DEBUG!
import asyncio
import logging

from utils import env, with_cursors
from formulas import overall_scores


PROGRESS = 5  # show progress every 5%
PROGRESS = 100 // PROGRESS


def fetch_columns(columns):
	result = []
	for column in columns:
		if column == "registration_date":
			# convert registration_date to unix timestamp in millis
			result.append(
				"(unix_timestamp(`registration_date`)+3600*24)*1000"
			)
		else:
			result.append(f"`{column}`")
	return result


class RunnerPool:
	def __init__(self, pipe, batch, cfm, a801):
		self.pipe = pipe  # pipe max size
		self.batch = batch  # batch size

		self.internal = cfm
		self.external = a801

	async def extract(self, table):
		if table.primary is None:
			# We need table information
			await table.extract_info(self.internal, env.cfm_db)

		logging.debug("start data extraction for table {}".format(table.name))

		if table.is_empty:
			logging.debug("table is empty, using fetch-update process")

			# If the table is empty, we have no hashes to compare
			pipes = [
				asyncio.Queue(maxsize=self.pipe)
				for p in range(3)
			]

			done, pending = await asyncio.wait((
				self.grab_loop(table, inp=None, out=pipes[0], grab_all=True),
				self.fetch_loop(
					table, inp=pipes[0], out=pipes[1], out2=pipes[2], grab_all=True
				),
				self.update_loop(table, inp=pipes[1], out=None),
				self.hash_loop(table, inp=pipes[2], out=None),
			), return_when=asyncio.FIRST_EXCEPTION)

		else:
			logging.debug(
				"table contains old data, updating modified rows only"
			)

			# If the table isn't empty, we assume we do have hashes
			pipes = [
				asyncio.Queue(maxsize=self.pipe)
				for p in range(5)
			]

			# And so, we use a more complex but faster algorithm
			# to fetch data
			done, pending = await asyncio.wait((
				self.load_loop(table, inp=None, out=pipes[0]),
				self.grab_loop(table, inp=None, out=pipes[1], grab_all=False),
				self.filter_loop(table, inp=pipes[0], inp2=pipes[1], out=pipes[2]),
				self.fetch_loop(
					table, inp=pipes[2], out=pipes[3], out2=pipes[4], grab_all=False
				),
				self.update_loop(table, inp=pipes[3], out=None),
				self.hash_loop(table, inp=pipes[4], out=None),
			), return_when=asyncio.FIRST_EXCEPTION)

		if pending:
			# There are pending tasks, so one of them
			# threw an exception
			logging.error(
				"[{}] something went wrong while extracting data"
				.format(table.name)
			)

			for task in pending:
				task.cancel()

			for task in done:
				exc = task.exception()

				if exc is None:
					continue

				task.print_stack(file=sys.stdout)

		else:
			if table.name == "player":
				try:
					await self.update_disqualifications()
				except Exception:
					import traceback
					traceback.print_exc()
			await self.post_download(table)

			logging.info("[{}] done updating".format(table.name))

	@with_cursors("internal")
	async def load_loop(self, inte, table, *, inp, out):
		assert inp is None and out is not None

		logging.debug("[{}] start load loop".format(table.name))
		# Send the query to the database
		await inte.execute(
			"SELECT `id`, `hashed` FROM `{}`"
			.format(table.read_hash)
		)
		logging.debug("[{}] load query sent".format(table.name))

		while True:
			# And fetch in small groups so we don't spam anything
			batch = await inte.fetchmany(self.batch)
			if not batch:
				# No more cached hashes
				await out.put(None)
				break

			await out.put(batch)

		logging.debug("[{}] load loop done".format(table.name))

	@with_cursors("external")
	async def grab_loop(self, exte, table, *, inp, out, grab_all):
		assert inp is None and out is not None

		logging.debug("[{}] start grab loop".format(table.name))

		await exte.execute(
			"SELECT COUNT(*) FROM `{}`"
			.format(table.name)
		)
		row = await exte.fetchone()
		await exte.fetchone()

		logging.info("[{}] total rows: {}".format(table.name, row[0]))
		progress = max(1, round(row[0] / PROGRESS / self.batch))
		count, total = 0, math.ceil(row[0] / self.batch)

		crc_columns = list(filter(
			lambda col: col != "registration_date",
			table.columns
		))

		if grab_all:
			select = "CRC32(CONCAT_WS('', `{0}`)), {1}{2}".format(
				"`,`".join(crc_columns),
				",".join(fetch_columns(table.columns)),
				table.composite_scores,
			)
		else:
			select = "`{0}`, CRC32(CONCAT_WS('', `{1}`))".format(
				table.primary,
				"`,`".join(crc_columns),
			)

		await exte.execute(
			"SELECT \
				{} \
			FROM \
				`{}`"
			.format(
				select,
				table.name,
			)
		)

		while True:
			batch = await exte.fetchmany(self.batch)
			if not batch:
				break

			await out.put(batch)

			count += 1  # DEBUG !
			if count % progress == 0:
				logging.info(
					"[{}] {}/{} batches processed ({}%)"
					.format(
						table.name,
						count, total,
						round(count / total * 100)
					)
				)

		await out.put(None)
		logging.debug("[{}] grab loop done".format(table.name))

	async def filter_loop(self, table, *, inp, inp2, out):
		assert inp is not None and inp2 is not None and out is not None

		logging.debug("[{}] start filter loop".format(table.name))

		new_batch, needed = [], self.batch

		internal_hashes = {}
		external_hashes = {}

		internal_count = 0
		external_count = 0

		get_internal = asyncio.create_task(inp.get())
		get_external = asyncio.create_task(inp2.get())
		tasks = {get_internal, get_external}
		paused = None

		while True:
			a = max(internal_count, external_count)
			b = min(internal_count, external_count)
			ratio = a / max(b, 1)
			if ratio >= 3:
				# If one stream has stored 3x more than the other
				# stop the stream, as it is filling up the memory
				if paused is None:
					if a == internal_count:
						paused = get_internal
					else:
						paused = get_external

					tasks.remove(paused)
			elif ratio < 1.5 and paused is not None:
				# If one stream has been stopped and the other caught up,
				# resume the stopped stream
				tasks.add(paused)
				paused = None

			# Wait until any of the internal or external fetch are complete
			done, pending = await asyncio.wait(
				tasks, return_when=asyncio.FIRST_COMPLETED
			)

			for task in done:
				batch = task.result()

				# Remove coroutine from list
				tasks.remove(task)

				if batch:
					# There is hash data, adjust variables for easier
					# operation
					if task == get_internal:
						coro = inp.get()
						get_internal = task = asyncio.create_task(coro)
						read, write = external_hashes, internal_hashes
					else:
						coro = inp2.get()
						get_external = task = asyncio.create_task(coro)
						read, write = internal_hashes, external_hashes

					stored = 0
					removed = 0
					for row in batch:
						_id, new_hash = row[0], row[1]

						# If this id has been read by the other input
						if _id in read:
							# then we check if their hashes are different
							if new_hash != read[_id]:
								# then we add the new hash to the new batch
								new_batch.append((
									_id,
									external_hashes[_id]
									if task == get_internal else
									new_hash
								))
								needed -= 1

							# and free some memory
							removed += 1
							del read[_id]

						# If this id hasn't been read by the other input
						else:
							# we mark it as read by this one
							stored += 1
							write[_id] = new_hash

					if task == get_internal:
						internal_count += stored
						external_count -= removed
					else:
						external_count += stored
						internal_count -= removed

					# And we schedule this coroutine to run again
					tasks.add(task)

				else:
					# No more data to check
					break

			else:
				# previous loop hasn't reached "break", so just continue

				# While there are excess of rows in the batch
				while needed < 0:
					# send a proper batch
					await out.put(new_batch[:needed])
					# and prepare the next one (even if it has an excess)
					new_batch = new_batch[needed:]
					needed += self.batch

				if needed == 0:
					# No more needed rows for this batch, just send it
					await out.put(new_batch)
					# and prepare the next one
					new_batch, needed = [], self.batch

				continue
			# previous loop did reach break, propagate it
			break

		if get_internal in tasks:
			# This chunk is not executed in get_external was in tasks
			logging.info("[{}] get_internal in tasks".format(table.name))

			batch = await get_internal
			while batch is not None:
				for row in batch:
					_id, new_hash = row[0], row[1]

					# If this id has been read by external
					if _id in external_hashes:
						# then we check if their hashes are different
						if new_hash != external_hashes[_id]:
							# and add the new hash to the batch
							new_batch.append((
								_id,
								external_hashes[_id]
							))
							needed -= 1

						# and free some memory
						del external_hashes[_id]

					# If this id hasn't been read by the other input
					else:
						# we mark it as read by this one
						internal_hashes[_id] = new_hash

				# While there are excess of rows in the batch
				while needed < 0:
					# send a proper batch
					await out.put(new_batch[:needed])
					# and prepare the next one (even if it has an excess)
					new_batch = new_batch[needed:]
					needed += self.batch

				if needed == 0:
					# No more needed rows for this batch, just send it
					await out.put(new_batch)
					# and prepare the next one
					new_batch, needed = [], self.batch

				batch = await inp.get()

		# Finish transferring new data
		if get_external in tasks:
			# This chunk is not executed if get_internal was in tasks
			batch = await get_external
			while batch:
				for (_id, new_hash) in batch:
					if _id in internal_hashes:
						old_hash = internal_hashes[_id]
						del internal_hashes[_id]

						if new_hash == old_hash:
							continue

					new_batch.append((
						_id,
						new_hash
					))
					needed -= 1

				# While there are excess of rows in the batch
				while needed < 0:
					# send a proper batch
					await out.put(new_batch[:needed])
					# and prepare the next one (even if it has an excess)
					new_batch = new_batch[needed:]
					needed += self.batch

				if needed == 0:
					# No more needed rows for this batch, just send it
					await out.put(new_batch)
					# and prepare the next one
					new_batch, needed = [], self.batch

				batch = await inp2.get()

		logging.debug(
			"[{}] internal batches done, {}-{} unpaired hashes"
			.format(table.name, len(external_hashes), len(internal_hashes))
		)

		new_batch.extend(external_hashes.items())
		needed -= len(external_hashes)

		# While there are excess of rows in the batch
		while needed < 0:
			# send a proper batch
			await out.put(new_batch[:needed])
			# and prepare the next one (even if it has an excess)
			new_batch = new_batch[needed:]
			needed += self.batch

		if needed == 0:
			# No more needed rows for this batch, just send it
			await out.put(new_batch)
			needed += self.batch

		if needed < self.batch:
			# Batch has items, but not the required amount
			await out.put(False)  # Signal less items
			await out.put(new_batch)

		await out.put(None)  # Signal EOF

		logging.debug("[{}] filter loop done".format(table.name))

		if len(internal_hashes) >= 100000:
			logging.debug(
				"[{}] too many rows to delete. did tig's db update?."
				.format(table.name)
			)

		else:
			await self.delete_rows(
				table,
				list(map(str, internal_hashes.keys()))
			)

	async def bulk_delete(self, inte, table, batch):
		batch = ",".join(batch)

		await inte.execute(
			"DELETE FROM `{}` WHERE `{}` IN ({})"
			.format(
				table.name,
				table.primary,
				batch
			)
		)
		await inte.execute(
			"DELETE FROM `{}` WHERE `id` IN ({})"
			.format(
				table.read_hash,
				batch
			)
		)

	@with_cursors("internal")
	async def delete_rows(self, inte, table, rows):
		logging.debug(
			"[{}] start delete ({} rows)"
			.format(table.name, len(rows))
		)

		batch = None
		needed = self.batch - len(rows)
		while needed < 0:
			needed += self.batch
			batch = rows[:self.batch]
			rows = rows[self.batch:]
			await self.bulk_delete(inte, table, batch)

		if needed < self.batch:
			await self.bulk_delete(inte, table, rows)

		logging.debug("[{}] done delete".format(table.name))

	@with_cursors("external")
	async def fetch_loop(self, exte, table, *, inp, out, out2, grab_all):
		assert inp is not None and out is not None

		logging.debug("[{}] start fetch loop".format(table.name))

		primary_idx = table.columns.index(table.primary)

		if grab_all:
			# There is nothing to compare, so just fetch and update
			while True:
				batch = await inp.get()
				if not batch:
					await out2.put(None)
					await out.put(None)
					break

				# Send rows and calculated hashes separately
				hashes = []
				for idx, row in enumerate(batch):
					#                    primary column, hash
					hashes.append((row[primary_idx + 1], row[0]))
					# remove hash from item
					batch[idx] = row[1:]

				await out2.put(hashes)
				await out.put(batch)

			logging.debug("[{}] fetch loop done".format(table.name))
			return

		# Prepare query (it is waaaay faster this way)
		query = (
			"SELECT {}{} FROM `{}` WHERE `{}` IN ({})"
			.format(
				",".join(fetch_columns(table.columns)),
				table.composite_scores,
				table.name,
				table.primary,
				"{}," * (self.batch - 1) + "{}"  # argument placeholder
			).format
		)

		fill_placeholders = False
		ids = [0] * self.batch
		while True:
			# Get filtered rows
			batch = await inp.get()
			if batch is None:
				await out2.put(None)
				await out.put(None)
				break

			elif batch is False:
				# This batch may have less items than expected
				batch = await inp.get()
				fill_placeholders = True

			# Dump batch ids into an ids list
			for idx, row in enumerate(batch):
				ids[idx] = row[0]

			if fill_placeholders:
				# Missing items, fill with 0 (reserved for souris)
				fill_placeholders = False

				for idx in range(len(batch), self.batch):
					ids[idx] = 0

			# Fetch all the data and send hashes
			await exte.execute(query(*ids))
			await out2.put(batch)
			await out.put(await exte.fetchall())

		logging.debug("[{}] fetch loop done".format(table.name))

	@with_cursors("internal")
	async def update_loop(self, inte, table, *, inp, out):
		assert inp is not None and out is None

		logging.debug("[{}] start update loop".format(table.name))

		if not table.is_empty:
			await inte.execute("TRUNCATE `{}_new`".format(table.name))

		# Prepare query (it is waaaay faster this way)
		query = (
			"REPLACE INTO `{}{}` (`{}`) VALUES ({})"
			.format(
				table.name,
				"" if table.is_empty else "_new",
				"`,`".join(table.write_columns),
				",".join(["%s"] * len(table.write_columns))
			)
		)

		while True:
			batch = await inp.get()
			if batch is None:
				break

			# Insert data into the database
			await inte.executemany(query, batch)

		logging.debug("[{}] update loop done".format(table.name))

	@with_cursors("internal")
	async def hash_loop(self, inte, table, *, inp, out):
		assert inp is not None and out is None

		logging.debug("[{}] start hash loop".format(table.name))

		# Prepare query (it is waaaay faster this way)
		query = (
			"INSERT INTO `{}` (`id`, `hashed`) VALUES (%s, %s)"
			.format(table.read_hash if table.is_empty else table.write_hash)
		)

		while True:
			batch = await inp.get()
			if batch is None:
				break

			# Insert data into the database
			await inte.executemany(query, batch)

		logging.debug("[{}] hash loop done".format(table.name))

	@with_cursors("internal", "external")
	async def update_disqualifications(self, inte, exte):
		logging.debug("[disq] updating disqualifications")
		await inte.execute("UPDATE `disqualified` SET `tfm` = 0")

		logging.debug("[disq] old tfm disqualifications wiped")
		await exte.execute(
			"SELECT `id` FROM `player` WHERE `stats_reliability` = 2"
		)
		query = (
			"INSERT INTO `disqualified` (`id`, `tfm`) \
			VALUES (%s, 1) ON DUPLICATE KEY UPDATE `tfm` = 1"
		)
		while True:
			batch = await exte.fetchmany(self.batch)
			if not batch:
				break
			await inte.executemany(query, batch)

		logging.debug("[disq] deleting removed cfm disqualifications")
		await inte.execute(
			"UPDATE \
				`disqualified` as `d` \
				LEFT JOIN `sanctions` as `s` ON `s`.`player` = `d`.`id` \
			SET `d`.`cfm` = 0 \
			WHERE \
				`s`.`player` IS NULL AND \
				`d`.`cfm` = 1"
		)

		logging.debug("[disq] inserting new cfm disqualifications")
		await inte.execute(
			"INSERT INTO `disqualified` (`id`, `cfm`) \
			SELECT `player` as `id`, 1 as `cfm` FROM `sanctions` \
			ON DUPLICATE KEY UPDATE `cfm` = 1"
		)

		logging.debug("[disq] deleting byproducts")
		await inte.execute(
			"DELETE FROM `disqualified` WHERE `cfm` = 0 AND `tfm` = 0"
		)

		logging.debug("[disq] done")

	@with_cursors("internal")
	async def post_download(self, inte, table):
		if table.name == "player":
			logging.debug("[player] calculating overall score")

			await inte.execute(
				"UPDATE `player{}` \
				SET `score_overall`={}"
				.format(
					"" if table.is_empty else "_new",
					overall_scores["alltime"]
				)
			)

			logging.debug("[player] renaming players without #")

			await inte.execute(
				"UPDATE `player{}` \
				SET `name`=CONCAT(`name`, '#0000') \
				WHERE `name` NOT LIKE '%#%'"
				.format(
					"" if table.is_empty else "_new"
				)
			)

		if table.is_empty:
			return

		await inte.execute(
			"SELECT COUNT(*) FROM `{}`"
			.format(table.write_hash)
		)
		row = await inte.fetchone()
		await inte.fetchone()  # has to return None for next execute

		logging.debug(
			"[{}] initiate internal hash transfer ({} hashes)"
			.format(table.name, row[0])
		)

		await inte.execute(
			"REPLACE INTO `{0}` \
			SELECT `w`.* \
			FROM `{1}` as `w`"
			.format(table.read_hash, table.write_hash)
		)

		logging.debug("[{}] truncate temp hash table".format(table.name))

		await inte.execute("TRUNCATE `{}`".format(table.write_hash))

		logging.debug("[{}] initiate changelog save".format(table.name))

		await inte.execute(
			"INSERT INTO `{0}_changelog` (`{1}`) \
			SELECT `n`.* \
			FROM `{0}_new` as `n`"
			.format(
				table.name,
				"`,`".join(table.write_columns)
			)
		)

		logging.debug("[{}] transfer new data".format(table.name))

		await inte.execute(
			"REPLACE INTO `{0}` \
			SELECT `n`.* \
			FROM `{0}_new` as `n`"
			.format(table.name)
		)
