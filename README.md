# CFM Backend Services
These are all the services the HTTP API requires in order to work.
This uses `docker-compose` in order to work, but every service is meant to be easily isolated if needed; as long as the dependecies are running (generally just redis and the database).

## Running
First you need to create a `.env` file.
Running the following commands will clone this repository and copy the testing environment.
```bash
git clone https://github.com/cheeseformice/backend
cd backend
cat test.env > .env
```

You can customize all the variables to your needs.
The first time the services are run, the database(s) will generate a volume with the table structures, using the credentials provided in the environment variables.
After that happens, *if* you need to edit the database credentials, you can either delete the generated volumes and force the services to generate new ones, or directly edit the credentials using a mysql client, by using the `GRANT` command.

### If you have access to Atelier801's API
You can fill in `A801_*` environment variables with the credentials given to you. The following command will build all the needed images and start all the services.
```bash
docker-compose up --build --detach
```

**NOTE:** Atelier801's API is... HUGE! And this project works by copying it locally. It uses around 36GB of disk space (leaderboards and everything).

The first time it is run, it has to download the whole database, which can take several hours (up to 20 hours depending on your setup).
After that is done, any subsequent update will take, in the worse case scenario (slow network, slow disk I/O and slow CPU) it can take up to an hour or two.

### If you don't have access to Atelier801's API (or want to run tests)
This repository contains a [mockupdb](./mockupdb) service, which is a mockup of Atelier801's API, containing a way smaller volume of data. This allows you to run tests and experiment with the services, locally.

To run this, you don't need to do any change to your `.env` file (using `test.env` directly should work properly), but you can tweak the configurations if you want to.
```bash
docker-compose --file docker-compose.test.yml up --build --detach
```

### Checking the logs
Once all the services are running, you can check the logs by running the following command, which will display them in real time.
```bash
docker-compose logs --follow
```
