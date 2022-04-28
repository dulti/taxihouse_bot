from datetime import datetime
from typing import Union

import asyncpg
from asyncpg import Pool, Connection

from data import config


class Database:

    def __init__(self):
        self.pool: Union[Pool, None] = None

    async def create(self):
        self.pool = await asyncpg.create_pool(
            user=config.PGUSER,
            password=config.PGPASS,
            host=config.PGHOST,
            database=config.PGNAME
        )

    async def execute(self, command: str, *args,
                      fetch: bool = False,
                      fetchval: bool = False,
                      fetchrow: bool = False,
                      execute: bool = False):
        async with self.pool.acquire() as connection:
            connection: Connection
            async with connection.transaction():
                if fetch:
                    result = await connection.fetch(command, *args)
                elif fetchval:
                    result = await connection.fetchval(command, *args)
                elif fetchrow:
                    result = await connection.fetchrow(command, *args)
                elif execute:
                    result = await connection.execute(command, *args)
                else:
                    raise RuntimeError('At least one parameter should be set to True')
                return result

    @staticmethod
    def format_args(sql: str, parameters: dict):
        sql += " AND ".join([
            f"{item} = ${num}" for num, item in enumerate(parameters,
                                                          start=1)
        ])
        return sql, tuple(parameters.values())

    async def create_table_users(self):
        sql = """
        CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL UNIQUE,
        username VARCHAR(100),
        is_elevated BOOLEAN DEFAULT FALSE,
        is_active BOOLEAN DEFAULT TRUE,
        is_admin BOOLEAN DEFAULT FALSE,
        watch_on BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        phone VARCHAR(50) UNIQUE,
        max_plates INTEGER,
        paid_until TIMESTAMP,
        delta_paid_until INTEGER
        );
        """
        return await self.execute(sql, execute=True)

    async def create_table_plates(self):
        sql = """
        CREATE TABLE IF NOT EXISTS plates(
        id SERIAL PRIMARY KEY,
        plate VARCHAR(9) NOT NULL UNIQUE,
        status VARCHAR(25) NOT NULL,
        status_date TIMESTAMP,
        first_added_by BIGINT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        users_watching INTEGER NOT NULL
        );
        """
        return await self.execute(sql, execute=True)

    async def create_table_watches(self):
        sql = """
        CREATE TABLE IF NOT EXISTS watches(
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        plate VARCHAR(9) NOT NULL,
        created_at TIMESTAMP NOT NULL
        );
        """
        return await self.execute(sql, execute=True)

    async def create_table_operations(self):
        sql = """
        CREATE TABLE IF NOT EXISTS operations(
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP NOT NULL,
        operation VARCHAR(100) NOT NULL,
        user_id BIGINT,
        by_bot BOOLEAN,
        plate VARCHAR(9)
        );
        """
        return await self.execute(sql, execute=True)

    async def create_table_report(self):
        sql = """
        CREATE TABLE IF NOT EXISTS report(
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP NOT NULL,
        plate VARCHAR(9) NOT NULL,
        status VARCHAR(25) NOT NULL,
        user_id BIGINT NOT NULL
        );
        """
        return await self.execute(sql, execute=True)

    async def create_table_notifications(self):
        """
        Notification types:
        0 - maximum plates change
        1 - paid period expiry
        """
        sql = """
        CREATE TABLE IF NOT EXISTS notifications(
        user_id BIGINT NOT NULL,
        notification_type INTEGER NOT NULL,
        added_by BIGINT NOT NULL,
        added_at TIMESTAMP NOT NULL,
        go_off_at TIMESTAMP NOT NULL,
        delta_days INTEGER NOT NULL,
        old_value INTEGER NOT NULL,
        new_value INTEGER NOT NULL,
        PRIMARY KEY (user_id, notification_type)
        );
        """
        return await self.execute(sql, execute=True)

    async def add_user(self, user_id: int, username: str, is_elevated: bool, is_active: bool,
                       is_admin: bool, watch_on: bool, created_at: datetime, updated_at: datetime, phone: str,
                       max_plates: int, paid_until: datetime, delta_paid_until: int):
        sql = """
        INSERT INTO users(
        user_id, username, is_elevated, is_active, is_admin, watch_on, 
        created_at, updated_at, phone, max_plates, paid_until, delta_paid_until
        ) VALUES(
        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
        );
        """
        return await self.execute(sql, user_id, username, is_elevated, is_active, is_admin, watch_on, created_at,
                                  updated_at, phone, max_plates, paid_until, delta_paid_until, execute=True)

    async def get_user_by_user_id(self, user_id: int):
        sql = """
        SELECT *
        FROM users
        WHERE user_id = $1;
        """
        return await self.execute(sql, user_id, fetchrow=True)

    async def get_user_by_phone(self, phone: str):
        sql = """
        SELECT *
        FROM users
        WHERE phone = $1;
        """
        return await self.execute(sql, phone, fetchrow=True)

    async def get_all_users(self):
        sql = """
        SELECT users.*, COUNT(watches.plate) as total_plates
        FROM users
        LEFT JOIN watches
        ON users.user_id = watches.user_id
        GROUP BY users.id;
        """
        return await self.execute(sql, fetch=True)

    async def update_user(self, id_: int, user_id: int, username: Union[str, None], is_elevated: bool, is_active: bool,
                          is_admin: bool, watch_on: bool, updated_at: datetime, phone: Union[str, None],
                          max_plates: int, paid_until: datetime, delta_paid_until: int):
        sql = """
        UPDATE users
        SET user_id = $1, username = $2, is_elevated = $3, is_active = $4, is_admin = $5, watch_on = $6, 
        updated_at = $7, phone = $8, max_plates=$9, paid_until=$10, delta_paid_until=$11
        WHERE id = $12;
        """
        return await self.execute(sql, user_id, username, is_elevated, is_active, is_admin, watch_on,
                                  updated_at, phone, max_plates, paid_until, delta_paid_until, id_, execute=True)

    async def update_user_max_plates(self, user_id: int, max_plates: int):
        sql = """
        UPDATE users
        SET max_plates = $2
        WHERE user_id = $1;
        """
        return await self.execute(sql, user_id, max_plates, execute=True)

    async def update_user_paid_until(self, user_id: int, paid_until: datetime, delta_paid_until: int):
        sql = """
        UPDATE users
        SET paid_until = $2, delta_paid_until = $3
        WHERE user_id = $1;
        """
        return await self.execute(sql, user_id, paid_until, delta_paid_until, execute=True)

    async def add_operation(self, created_at: datetime, operation: str, user_id: Union[int, None],
                            by_bot: bool, plate: Union[str, None]):
        sql = """
        INSERT INTO operations(
        created_at, operation, user_id, by_bot, plate
        ) VALUES(
        $1, $2, $3, $4, $5
        );
        """
        return await self.execute(sql, created_at, operation, user_id, by_bot, plate, execute=True)

    async def add_plate(self, plate: str, status: str, status_date: datetime, first_added_by: int,
                        created_at: datetime, updated_at: datetime, users_watching: int):
        sql = """
        INSERT INTO plates(
        plate, status, status_date, first_added_by, created_at, updated_at, users_watching
        ) VALUES(
        $1, $2, $3, $4, $5, $6, $7
        );
        """
        return await self.execute(sql, plate, status, status_date, first_added_by, created_at,
                                  updated_at, users_watching, execute=True)

    async def get_plate(self, plate: str):
        sql = """
        SELECT *
        FROM plates
        WHERE plate = $1;
        """
        return await self.execute(sql, plate, fetchrow=True)

    async def get_all_plates(self):
        sql = """
        SELECT *
        FROM plates;
        """
        return await self.execute(sql, fetch=True)

    async def get_plates_by_user(self, user_id: int):
        sql = """
        SELECT plates.*
        FROM plates
        JOIN watches
        ON plates.plate = watches.plate
        WHERE watches.user_id = $1;
        """
        return await self.execute(sql, user_id, fetch=True)

    async def get_plates_by_user_with_limit(self, user_id: int, limit: int):
        sql = """
        SELECT plates.*
        FROM plates
        JOIN watches
        ON plates.plate = watches.plate
        WHERE watches.user_id = $1
        ORDER BY watches.created_at DESC
        LIMIT $2;
        """
        return await self.execute(sql, user_id, limit, fetch=True)

    async def update_plate(self, plate: str, status: str, status_date: datetime, updated_at: datetime,
                           users_watching: int):
        sql = """
        UPDATE plates
        SET status = $1, status_date = $2, updated_at = $3, users_watching = $4
        WHERE plate = $5;
        """
        return await self.execute(sql, status, status_date, updated_at, users_watching, plate, execute=True)

    async def remove_plate(self, id_: int):
        sql = """
        DELETE FROM plates
        WHERE id = $1;
        """
        return await self.execute(sql, id_, execute=True)

    async def add_watch(self, user_id: int, plate: str, created_at: datetime):
        sql = """
        INSERT INTO watches (
        user_id, plate, created_at
        ) VALUES(
        $1, $2, $3
        );
        """
        return await self.execute(sql, user_id, plate, created_at, execute=True)

    async def remove_watch(self, id_: int):
        sql = """
        DELETE FROM watches
        WHERE id = $1;
        """
        return await self.execute(sql, id_, execute=True)

    async def get_watch_by_user_by_plate(self, user_id: int, plate: str):
        sql = """
        SELECT *
        FROM watches
        WHERE user_id = $1 AND plate = $2;
        """
        return await self.execute(sql, user_id, plate, fetchrow=True)

    async def get_watch_by_plate(self, plate: str):
        sql = """
        SELECT *
        FROM watches
        WHERE plate = $1;
        """
        return await self.execute(sql, plate, fetch=True)

    async def count_watches_by_user(self, user_id: int):
        sql = """
        SELECT COUNT(*)
        FROM watches
        WHERE user_id = $1;
        """
        return await self.execute(sql, user_id, fetchval=True)

    async def add_report(self, created_at: datetime, plate: str, user_id: int, status: str):
        sql = """
        INSERT INTO report(
        created_at, plate, status, user_id
        ) VALUES(
        $1, $2, $3, $4
        );
        """
        return await self.execute(sql, created_at, plate, status, user_id, execute=True)

    async def clean_report(self):
        sql = """
        DELETE FROM report;
        """
        return await self.execute(sql, execute=True)

    async def get_report_by_plate_user(self, plate: str, user_id: int):
        sql = """
        SELECT *
        FROM report
        WHERE plate = $1 AND user_id = $2;
        """
        return await self.execute(sql, plate, user_id, fetchrow=True)

    async def get_report_by_user(self, user_id: int):
        sql = """
        SELECT *
        FROM report
        WHERE user_id = $1;
        """
        return await self.execute(sql, user_id, fetch=True)

    async def update_report(self, id_: int, status: str):
        sql = """
        UPDATE report
        SET status = $1
        WHERE id = $2;
        """
        return await self.execute(sql, status, id_, execute=True)

    async def remove_report_by_user(self, user_id: int):
        sql = """
        DELETE FROM report
        WHERE user_id = $1;
        """
        return await self.execute(sql, user_id, execute=True)

    async def remove_report_by_plate_user(self, plate: str, user_id: int):
        sql = """
        DELETE FROM report
        WHERE user_id = $1 AND plate = $2;
        """
        return await self.execute(sql, user_id, plate, execute=True)

    async def add_notification(self, user_id: int, notification_type: int, added_by: int, added_at: datetime,
                               go_off_at: datetime, delta_days: int, old_value: int, new_value: int):
        """
        Notification types:
        0 - maximum plates change
        1 - paid period expiry
        """
        sql = """
        INSERT INTO notifications(
            user_id, notification_type, added_by, added_at, go_off_at, delta_days, old_value, new_value
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8
        );
        """
        return await self.execute(sql, user_id, notification_type, added_by, added_at, go_off_at, delta_days,
                                  old_value, new_value, execute=True)

    async def remove_notification(self, user_id: int, notification_type: int):
        """
        Notification types:
        0 - maximum plates change
        1 - paid period expiry
        """
        sql = """
        DELETE FROM notifications
        WHERE user_id = $1 AND notification_type = $2;
        """
        return await self.execute(sql, user_id, notification_type, execute=True)

    async def get_notifications_by_type(self, notification_type: int):
        """
        Notification types:
        0 - maximum plates change
        1 - paid period expiry
        """
        sql = """
        SELECT * FROM notifications
        WHERE notification_type = $1;
        """
        return await self.execute(sql, notification_type, fetch=True)

    async def update_notification(self, user_id: int, notification_type: int, delta_days: int):
        """
        Notification types:
        0 - maximum plates change
        1 - paid period expiry
        """
        sql = """
        UPDATE notifications
        SET delta_days = $3
        WHERE user_id = $1 AND notification_type = $2;
        """
        return await self.execute(sql, user_id, notification_type, delta_days, execute=True)

    async def create_service_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS service (
        parameter VARCHAR(10) PRIMARY KEY,
        value_int INTEGER,
        value_char VARCHAR(10),
        value_ts TIMESTAMP
        ); 
        """
        return await self.execute(sql, execute=True)

    async def get_service(self, parameter: str):
        sql = """
        SELECT * FROM service
        WHERE parameter = $1;
        """
        return await self.execute(sql, parameter, fetchrow=True)
