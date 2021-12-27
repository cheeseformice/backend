#include "redismodule.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <stdbool.h>
#include <time.h>
#include <unistd.h>
#include <signal.h>
#include <string.h>
#include <pthread.h>
#include <mariadb/mysql.h>

#define mysqlError(con) fprintf(stderr, "%s\n", mysql_error(con));
#define stmtError(stmt) fprintf(stderr, "%s\n", mysql_stmt_error(stmt));
#define getenvdef(var,default) getenv(var) ? getenv(var) : default;

#define tablesLength 2
#define statsLength 10
#define perIndex 39

volatile sig_atomic_t didShutdown = 0;
volatile sig_atomic_t didBoot = 0;
pthread_t bootThreadId;
pthread_t generatorThreadId;

const char* tables[tablesLength] = {
  "player",
  "tribe_stats",
};
volatile sig_atomic_t available[tablesLength] = {0, 0};
volatile sig_atomic_t outdated[tablesLength] = {0, 0};

const char* validStats[statsLength] = {
  "round_played",
  "cheese_gathered",
  "first",
  "bootcamp",
  "score_stats",
  "score_shaman",
  "score_survivor",
  "score_racing",
  "score_defilante",
  "score_overall",
};

int** statsStart[tablesLength];
int** statsEnd[tablesLength];

int** genStatsStart[tablesLength];
int** genStatsEnd[tablesLength];

void printfd(const char* fmt, ...) {
  time_t raw;
  time(&raw);
  struct tm* info = localtime(&raw);

  char buffer[18 + strlen(fmt)];
  strftime(buffer, 18, "[%d/%m %H:%M:%S] ", info);
  strcat(buffer, fmt);

  va_list argptr;
  va_start(argptr, fmt);
  vprintf(buffer, argptr);
  va_end(argptr);

  fflush(stdout);
}

int max(int a, int b) {
  return a >= b ? a : b;
}

int getTableSlot(const char* tbl) {
  for (uint8_t slot = 0; slot < tablesLength; slot++)
    if (strcmp(tbl, tables[slot]) == 0)
      return slot;
  return -1;
}

int getStatIndex(const char* name) {
  for (uint8_t i = 0; i < statsLength; i++)
    if (strcmp(name, validStats[i]) == 0)
      return i;
  return -1;
}

bool parseArguments(
  RedisModuleCtx *ctx, RedisModuleString **argv, int argc,
  int *tableSlot, int *statIndex, long long *stat
) {

  if (argc != 4) {
    RedisModule_WrongArity(ctx);
    return false;
  }

  if (RedisModule_StringToLongLong(argv[3], stat) != REDISMODULE_OK) {
    RedisModule_ReplyWithError(ctx, "ERR invalid stat value");
    return false;
  }

  size_t len;
  const char* tbl = RedisModule_StringPtrLen(argv[1], &len);
  *tableSlot = getTableSlot(tbl);
  if (*tableSlot == -1) {
    RedisModule_ReplyWithError(ctx, "ERR unknown table");
    return false;
  }

  const char* name = RedisModule_StringPtrLen(argv[2], &len);
  *statIndex = getStatIndex(name);
  if (*statIndex == -1) {
    RedisModule_ReplyWithError(ctx, "ERR unknown stat");
    return false;
  }

  if (available[*tableSlot] == 0) {
    RedisModule_ReplyWithError(ctx, "ERR currently unavailable");
    return false;
  }

  return true;
}

int reply_GETPOS(RedisModuleCtx *ctx, int outdated, int position, int value) {
  RedisModule_ReplyWithArray(ctx, 3);
  RedisModule_ReplyWithLongLong(ctx, outdated);
  RedisModule_ReplyWithLongLong(ctx, position);
  return RedisModule_ReplyWithLongLong(ctx, value);
}

/* RANKING.GETPOS name stat */
// Returns approximate leaderboard position of stat
int cmd_GETPOS(RedisModuleCtx *ctx, RedisModuleString **argv, int argc) {
  int slot;
  int statIndex;
  long long stat;
  if (!parseArguments(ctx, argv, argc, &slot, &statIndex, &stat))
    return REDISMODULE_OK;

  int* ptr = statsStart[slot][statIndex];
  int* end = statsEnd[slot][statIndex];

  int l = 0;
  int r = end - ptr - 1;
  int m;
  while (l <= r) {
    m = (l + r) / 2;

    // comparisons are inverted because the array is inverted
    if (ptr[m] > stat) {
      l = m + 1;

    } else if (ptr[m] < stat) {
      r = m - 1;

    } else {
      return reply_GETPOS(ctx, outdated[slot], m * perIndex, ptr[m]);
    }
  }

  // r is in the least number greater than stat, which is what we are looking for
  r = max(r, 0);
  return reply_GETPOS(ctx, outdated[slot], r * perIndex, ptr[r]);
}

/* RANKING.GETPAGE name start */
// Returns an approximate of the value that the row may have
int cmd_GETPAGE(RedisModuleCtx *ctx, RedisModuleString **argv, int argc) {
  int slot;
  int statIndex;
  long long startRow;
  if (!parseArguments(ctx, argv, argc, &slot, &statIndex, &startRow))
    return REDISMODULE_OK;

  int* ptr = statsStart[slot][statIndex] + startRow / perIndex;
  int* end = statsEnd[slot][statIndex];

  if (ptr >= end)
    return RedisModule_ReplyWithError(ctx, "ERR page too far");
  RedisModule_ReplyWithArray(ctx, 3);
  RedisModule_ReplyWithLongLong(ctx, startRow / perIndex * perIndex);
  RedisModule_ReplyWithLongLong(ctx, *ptr);
  return RedisModule_ReplyWithLongLong(ctx, outdated[slot]);
}

MYSQL* connectToMySQL(void) {
  MYSQL *con = mysql_init(NULL);

  if (con == NULL) {
    mysqlError(con);
    return NULL;
  }

  char* host = getenvdef("DB_IP", "cfmdb");
  char* user = getenvdef("DB_USER", "test");
  char* pass = getenvdef("DB_PASS", "test");
  char* db = getenvdef("DB", "api_data");

  if (mysql_real_connect(con, host, user, pass, db, 3306, NULL, 0) == NULL) {
    mysqlError(con);
    mysql_close(con);
    return NULL;
  }

  return con;
}

void freeIndices(int slot) {
  for (int i = 0; i < statsLength; i++)
    free(statsStart[slot][i]);

  free(statsStart[slot]);
  free(statsEnd[slot]);
}

bool loadIndex(int slot, int i, const char* path) {
  FILE *f = fopen(path, "rb");
  if (f == NULL) return false;

  fseek(f, 0, SEEK_END);
  int size = ftell(f);
  rewind(f);

  int *content = (int*) malloc(size);
  fread(content, 1, size, f);
  fclose(f);

  genStatsStart[slot][i] = content;
  genStatsEnd[slot][i] = content + (size / sizeof(int));
  return true;
}

bool saveIndex(int slot, int i, char* path) {
  FILE *f = fopen(path, "wb");
  if (f == NULL) {
    printfd("could not write index %d\n", i);
    return false;
  }

  fwrite((char*) statsStart[slot][i], sizeof(int), statsEnd[slot][i] - statsStart[slot][i], f);
  fclose(f);

  printfd("index %d written\n", i);
  return true;
}

void saveIndices(int slot) {
  const char* path = getenvdef("INDEX_SAVE", "/data/rank_%s_index%d.bin");
  printfd("saving indices to %s (%s)\n", path, tables[slot]);

  for (int i = 0; i < statsLength; i++) {
    char buffer[256];
    sprintf(buffer, path, tables[slot], i);

    saveIndex(slot, i, buffer);
  }

  printfd("indices saved\n");
}

bool allocateParentArrays(int slot) {
  genStatsStart[slot] = (int**) malloc(statsLength * sizeof(int*));
  if (genStatsStart[slot] == NULL) {
    fprintf(stderr, "failed to allocate memory for indices for %s.\n", tables[slot]);
    return false;
  }

  genStatsEnd[slot] = (int**) malloc(statsLength * sizeof(int*));
  if (genStatsEnd[slot] == NULL) {
    fprintf(stderr, "failed to allocate memory for indices for %s.\n", tables[slot]);
    free(genStatsStart[slot]);
    return false;
  }

  return true;
}

void moveGeneratedIndices(int slot) {
  statsStart[slot] = genStatsStart[slot];
  statsEnd[slot] = genStatsEnd[slot];
  outdated[slot] = 0;
}

bool generateIndices(MYSQL *con, int slot, char* qualificationQuery) {
  printfd("generating indices\n");
  outdated[slot] = 1;

  // on success, allocates statsStart, statsEnd, all children arrays and returns true
  // on failure, prints error and returns false. none of the arrays are allocated after that
  bool setupIndices = false;

  // check how many numbers we need to store
  char buffer[256];
  sprintf(buffer, "SELECT COUNT(*) FROM `%s`;", tables[slot]);
  if (mysql_query(con, buffer) > 0) {
    mysqlError(con);
    goto error;
  }

  MYSQL_RES *countRes = mysql_use_result(con);
  MYSQL_ROW countRow = mysql_fetch_row(countRes);
  const int count = atoi(countRow[0]) / perIndex;
  mysql_free_result(countRes);

  // allocate parent arrays
  if (!allocateParentArrays(slot)) return false;

  // allocate children arrays
  for (int i = 0; i < statsLength; i++) {
    genStatsStart[slot][i] = (int*) malloc(count * sizeof(int));

    if (genStatsStart[slot][i] == NULL) {
      fprintf(stderr, "failed to allocate memory for indices.\n");
      // could not allocate more memory, so free what we already had
      for (int j = 0; j < i; j++)
        free(genStatsStart[slot][j]);
      goto error;
    }
  }
  setupIndices = true;
  printfd("memory allocated\n");

  // get & store all the numbers
  for (int i = 0; i < statsLength; i++) {
    const char* name = validStats[i];

    // prepare mysql query
    char* fmt = (char*) malloc(sizeof(char) * 1024);
    if (slot == 0) {
      char* preFmt = "SELECT `p`.`%%s` "
                     "FROM `%%s` as `p` "
                     "LEFT JOIN `disqualified` as `d` "
                     "ON `d`.`id` = `p`.`id` "
                     "WHERE `d`.`id` IS NULL%s "
                     "ORDER BY `p`.`%%s` DESC";
      int length = strlen(preFmt) + 1 + strlen(qualificationQuery);
      snprintf(fmt, length, preFmt, qualificationQuery);
    } else if (slot == 1) {
      fmt = "SELECT `%s` FROM `%s` ORDER BY `%s` DESC";
    } else {
      printfd("unknown table slot %d\n", slot);
      goto error;
    }
    int length = strlen(fmt) + 1 + strlen(tables[slot]) + strlen(name) * 2;
    char query[length];
    snprintf(query, length, fmt, name, tables[slot], name);
    printfd("using query %s\n", query);

    MYSQL_STMT *stmt = mysql_stmt_init(con);
    if (mysql_stmt_prepare(stmt, query, strlen(query)) != 0) {
      stmtError(stmt);
      goto error;
    }

    // bind result
    int statValue;
    my_bool isNull;
    my_bool hasError;
    MYSQL_BIND bind[1];
    memset(bind, 0, sizeof(bind));
    bind[0].buffer_type = MYSQL_TYPE_LONG;
    bind[0].buffer = (char *)&statValue;
    bind[0].is_null = &isNull;
    bind[0].error = &hasError;

    if (mysql_stmt_bind_result(stmt, bind) != 0) {
      stmtError(stmt);
      goto error;
    }

    if (mysql_stmt_execute(stmt) != 0) {
      stmtError(stmt);
      goto error;
    }

    printfd("generating indices for %s\n", name);
    // fetch all rows
    int* ptr = genStatsStart[slot][i];
    while (mysql_stmt_fetch(stmt) == 0) {
      if (isNull || statValue == 0) {
        *ptr = 0;
        break;
      } else {
        *ptr = statValue;
      }
      ptr++;

      // ignore rows we don't need
      for (int ignored = 0; ignored < perIndex - 1; ignored++)
        if (mysql_stmt_fetch(stmt) != 0) goto nextStat; // break out of both loops
    }

nextStat: ;
    // check if there have been errors
    int stmt_errno = mysql_stmt_errno(stmt);
    if (stmt_errno != 0) {
      stmtError(stmt);
    } else {
      printfd("index generation for %s successful\n", name);
      genStatsEnd[slot][i] = ptr;
    }

    // before going to the next stat, we need to cleanup
    mysql_stmt_free_result(stmt);
    mysql_stmt_close(stmt);

    if (stmt_errno != 0) goto error;
  }

  // if everything goes smoothly, we just save the indices in disk & return true
  moveGeneratedIndices(slot);
  saveIndices(slot);
  return true;
error:
  if (setupIndices) {
    // indices were setup, we need to free everything
    for (int i = 0; i < statsLength; i++)
      free(genStatsStart[slot][i]);
  }
  free(genStatsStart[slot]);
  free(genStatsEnd[slot]);

  return false;
}

char* getQualificationQuery() {
  FILE* fp = fopen("/data-shared/qualification.cfg", "r");
  if (fp == NULL)
    return "";

  char* query = (char*) malloc(sizeof(char) * 2048);
  char* line;
  size_t len = 0;
  while (getline(&line, &len, fp) != -1) {
    char field[64];
    int min;
    char minStr[10];
    if (sscanf(line, "%s = %d", field, &min) == EOF) { continue; }

    snprintf(minStr, 10, "%d", min);
    if (min == 0) { continue; }

    strcat(query, " AND `p`.`");
    strcat(query, field);
    strcat(query, "` >= ");
    strcat(query, minStr);
  }

  fclose(fp);
  free(line);
  return query;
}

int generateAllIndices(void) {
  char* qualificationQuery = getQualificationQuery();
  MYSQL *con = connectToMySQL();

  if (con == NULL) {
    free(qualificationQuery);
    return 1;
  }

  for (uint8_t slot = 0; slot < tablesLength; slot++)
    if (generateIndices(con, slot, qualificationQuery))
      available[slot] = 1;

  mysql_close(con);
  free(qualificationQuery);
  return 0;
}

void *generateAllIndicesThread(void *arg) {
  generateAllIndices();
  return NULL;
}

void *bootModule(void *arg) {
  char* qualificationQuery = getQualificationQuery();
  printfd("using qualification query '%s'\n", qualificationQuery);

  uint8_t slot;
  int error = -1;
  for (slot = 0; slot < tablesLength; slot++) {
    // try to load indices from disk first
    if (!allocateParentArrays(slot)) {
      error = 0;
    } else {
      const char* path = getenvdef("INDEX_SAVE", "/data/rank_%s_index%d.bin");
      printfd("loading indices from %s\n", path);
      for (int i = 0; i < statsLength; i++) {
        char buffer[256];
        sprintf(buffer, path, tables[slot], i);

        if (!loadIndex(slot, i, buffer)) {
          printfd("could not load indices, starting index generation\n");
          error = i;
          break;
        }
      }
    }

    if (error > -1) {
      printfd("indices for %s couldn't load\n", tables[slot]);
      break;
    }
    moveGeneratedIndices(slot);
    available[slot] = 1;

    printfd("indices for %s loaded successfully\n", tables[slot]);
  }

  if (error > -1) {
    // gotta free what we already had
    for (int i = 0; i < error; i++)
      free(genStatsStart[slot][i]);

    free(genStatsStart[slot]);
    free(genStatsEnd[slot]);

    // and generate indices
    generateAllIndices();
  } else {
    printfd("all indices loaded successfully\n");
  }

  free(qualificationQuery);
  didBoot = 1;
  return NULL;
}

int cmd_UPDATEDONE(RedisModuleCtx *ctx, RedisModuleString **argv, int argc) {
  const char* channelStr = "broadcast:update";
  const char* messageStr = "done";

  RedisModuleString *channel = RedisModule_CreateString(ctx, channelStr, strlen(channelStr));
  RedisModuleString *message = RedisModule_CreateString(ctx, messageStr, strlen(messageStr));
  RedisModule_PublishMessage(ctx, channel, message);
  RedisModule_FreeString(ctx, channel);
  RedisModule_FreeString(ctx, message);

  if (didBoot == 1) {
    pthread_create(&generatorThreadId, NULL, generateAllIndicesThread, NULL);
  }

  return RedisModule_ReplyWithLongLong(ctx, 1);
}

void onShutdown(void) {
  if (didShutdown == 1) return;
  didShutdown = 1;

  printfd("shutting down module\n");

  pthread_cancel(bootThreadId);
  pthread_cancel(generatorThreadId);
  printfd("free indices on unload\n");
  for (uint8_t slot = 0; slot < tablesLength; slot++)
    if (available[slot])
      freeIndices(slot);
  mysql_library_end();
}

void onServerShutdown(RedisModuleCtx *ctx, RedisModuleEvent e, uint64_t sub, void *data) {
  REDISMODULE_NOT_USED(ctx);
  REDISMODULE_NOT_USED(e);
  REDISMODULE_NOT_USED(sub);
  REDISMODULE_NOT_USED(data);

  onShutdown();
}

int RedisModule_OnLoad(RedisModuleCtx *ctx, RedisModuleString **argv, int argc) {
  REDISMODULE_NOT_USED(argv);
  REDISMODULE_NOT_USED(argc);

  if (RedisModule_Init(ctx, "ranking", 1, REDISMODULE_APIVER_1) == REDISMODULE_ERR)
    return REDISMODULE_ERR;

  if (RedisModule_CreateCommand(ctx, "ranking.getpos",
      cmd_GETPOS, "readonly", 1, 1, 1) == REDISMODULE_ERR)
    return REDISMODULE_ERR;

  if (RedisModule_CreateCommand(ctx, "ranking.getpage",
      cmd_GETPAGE, "readonly", 1, 1, 1) == REDISMODULE_ERR)
    return REDISMODULE_ERR;

  if (RedisModule_CreateCommand(ctx, "ranking.updatedone",
      cmd_UPDATEDONE, "readonly", 1, 1, 1) == REDISMODULE_ERR)
    return REDISMODULE_ERR;

  RedisModule_SubscribeToServerEvent(ctx, RedisModuleEvent_Shutdown, onServerShutdown);

  pthread_create(&bootThreadId, NULL, bootModule, NULL);

  return REDISMODULE_OK;
}

int RedisModule_OnUnload(RedisModuleCtx *ctx) {
  REDISMODULE_NOT_USED(ctx);
  onShutdown();
  return REDISMODULE_OK;
}