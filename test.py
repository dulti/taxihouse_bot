import asyncio
import time
from pprint import pprint

from utils.db_api.postgresql import Database
from utils.misc.plate_parser import get_status

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
plates = ['Т915СР69', 'М342ТМ750', 'К952СР750', 'С655РР750', 'В743МВ750',
          'НХ57977', 'Р023ЕУ750', 'А023СТ750', 'М173КЕ13', 'Н375СЕ124',
          'О390ЕЕ196', 'О392ТО33', 'О437РМ32', 'О405РМ32', 'Т816РЕ777',
          'О985ТА750', 'ОХ97577', 'А121ХК156', 'А532ХЕ156', 'О783МА799']

db = Database()


async def test():
    await db.create()

    db_records = (await db.get_all_plates())[:]
    converted_records = {}
    for record in db_records:
        converted_records[record['plate']] = (record['status'], record['status_date'])

    res = await get_status([record['plate'] for record in db_records], converted_records)

    pprint(res)
start_time = time.time()
asyncio.run(test())
print(time.time() - start_time)
