import asyncio
import json
import re
from datetime import datetime
from json import JSONDecodeError
from typing import Callable
from urllib.parse import quote

from aiohttp import ClientSession, ClientConnectionError
from bs4 import BeautifulSoup

from data.config import N_WORKERS, RECONN_ATTEMPTS


class PlateParser:

    def __init__(self, plates, max_workers=N_WORKERS):
        self.plates = plates
        # create a queue that only allows a maximum of N_WORKERS items
        self.queue = asyncio.Queue()
        self.max_workers = max_workers
        self.servers = ['mtdi', 'mos']
        # create a dict that will keep the parsing results
        self.result = {plate: {server: None for server in self.servers} for plate in plates}
        self.payloaders = {'mtdi': self._generate_mtdi_payload, 'mos': self._generate_mos_payload}
        self.processors = {'mtdi': self._process_mtdi, 'mos': self._process_mos}

    # generate_SERVER_payload methods return a tuple with three elements:
    # - headers
    # - url
    # - params (optional)

    @staticmethod
    def _generate_mtdi_payload(plate: str) -> tuple:
        payload = (
            {
                'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                               'AppleWebKit/537.36 (KHTML, like Gecko) '
                               'Chrome/90.0.4430.93 Safari/537.36'),
                'referer': ('https://mtdi.mosreg.ru/deyatelnost/celevye-programmy/'
                            'taksi1/proverka-razresheniya-na-rabotu-taksi')
            },
            (f'https://mtdi.mosreg.ru/deyatelnost/celevye-programmy/taksi1/'
             f'proverka-razresheniya-na-rabotu-taksi?number={plate}&name=&id=&region=ALL'),
            None  # params
        )
        return payload

    @staticmethod
    def _generate_mos_payload(plate: str) -> tuple:
        user_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
                      ' Chrome/90.0.4430.93 Safari/537.36')
        page_url = 'https://www.mos.ru/otvet-transport/kak-proverit-razreshenie-taksi/'

        payload = (
            {
                'cookie': 'mos_id=Cg8qAWBwsxBnuEpI18M8AgA=;',
                'User-Agent': user_agent,
                'referer': f'{page_url}?number={quote(plate)}',
                'x-caller-id': 'widget-avtokod-taxi-stats'
            },
            'https://www.mos.ru/altmosmvc/api/v1/taxi/getInfo/',
            {
                'Region': '', 'RegNum': plate, 'FullName': '',
                'LicenseNum': '', 'Condition': '', 'pagenumber': 1
            }
        )
        return payload

    @staticmethod
    def _process_mtdi(resp: str) -> tuple:
        r_souped = BeautifulSoup(resp, 'html.parser')
        pattern = re.compile(r'result: (\[.*?\])')
        script = r_souped.find('script', text=pattern)

        if script:
            match = pattern.search(script.string)
            if match:
                json_ = json.loads(match.group(1))
                if len(json_) == 0:
                    status = 'Запись не найдена'
                    date_ = datetime.min
                else:
                    results = {}
                    for record in json_:
                        results[datetime.strptime(record['info']['permissionDate'],
                                                  '%d.%m.%Y')] = record['info']['status']
                    date_ = max(results)
                    status = results[date_]
            else:
                status = 'FAIL'
                date_ = None
        else:
            status = 'FAIL'
            date_ = None

        return status, date_

    @staticmethod
    def _process_mos(resp: str) -> tuple:
        try:
            json_ = json.loads(resp)
            if json_['Count'] == 0:
                status = 'Запись не найдена'
                date_ = datetime.min
            else:
                results = {}
                for record in json_['Infos']:
                    results[datetime.strptime(record['EditDate'], '%d.%m.%Y')] = record['Condition']
                date_ = max(results)
                status = results[date_]
        except (JSONDecodeError, TypeError):
            print(resp, flush=True)
            status = 'FAIL'
            date_ = None
        return status, date_

    @staticmethod
    async def _get_status(plate: str,
                          payload_func: Callable[[str], tuple],
                          process_func: Callable[[bytes], tuple]):
        headers, url, params = payload_func(plate)
        try:
            async with ClientSession(headers=headers) as client:
                async with client.get(url, params=params) as resp:
                    if not resp.ok:
                        return 'DOWN', None
                    await asyncio.sleep(0)
                    r = await resp.read()
        except ClientConnectionError:
            return 'FAIL', None

        return process_func(r)

    async def get_all_statuses(self):
        # DON'T await here; start consuming things out of the queue, and
        # meanwhile execution of this function continues. We'll start two
        # coroutines for fetching and two coroutines for processing.
        all_the_coros = asyncio.gather(
            *[self._worker() for _ in range(self.max_workers)])

        # place all URLs on the queue
        for plate in self.plates:
            for server in self.servers:
                await self.queue.put((plate, server))

        # now put a bunch of `None`'s in the queue as signals to the workers
        # that there are no more items in the queue.
        for _ in range(self.max_workers):
            await self.queue.put(None)

        # now make sure everything is done
        await all_the_coros

    async def _worker(self):
        while True:
            data = await self.queue.get()
            if data is None:
                # this coroutine is done; simply return to exit
                return
            plate, server = data
            status, date_ = await self._get_status(plate, self.payloaders[server], self.processors[server])
            if status in ['Прекращено', 'Истек срок действия']:
                status = 'Признано недействующим'
            self.result[plate][server] = (status, date_)


async def get_status(plates: list[str], db_records: dict[str: tuple] = None) -> dict:
    """
    Use without db_records when requesting statuses for new plates.
    Use with db_records when updating on schedule.
    db_records format: {plate: (status, date), ...}
    """

    attempts = 0
    # get all plates statuses
    while True:
        plate_parser = PlateParser(plates)
        await plate_parser.get_all_statuses()
        plates_data = plate_parser.result

        attempts += 1

        for plate in plates_data:
            # if nothing failed, break; else retry
            if 'FAIL' not in [val[0] for val in plates_data[plate].values()]:  # val[0] = status
                break
        # or break if reached 10 attempts
        if attempts >= RECONN_ATTEMPTS:
            break

    # if db_records was passed, add another 'server' key to plates_data with db values
    if db_records:
        for plate in plates_data:
            plates_data[plate]['db'] = db_records[plate]

    # find the relevant status for each plate
    relevant_statuses = {}

    for plate in plates_data:

        # if all parsers return 'Not found', return 'Not found' and today's date
        if all([plates_data[plate][server][0] == 'Запись не найдена' for server in plate_parser.servers]):
            relevant_statuses[plate] = ('Запись не найдена', datetime.today())
            continue

        # if all parsers fail or servers are down, return fail: we couldn't update
        if (all([plates_data[plate][server][0] == 'FAIL' for server in plate_parser.servers]) or
            all([plates_data[plate][server][0] == 'DOWN' for server in plate_parser.servers])):
            relevant_statuses[plate] = ('FAIL', None)
            continue

        # if any of the parsers failed or the server was down, remove the failed entry
        for server in plate_parser.servers:
            if plates_data[plate][server][0] in ['FAIL', 'DOWN']:
                del plates_data[plate][server]

        # otherwise compare all dates and return the tuple with the latest date
        try:
            relevant_statuses[plate] = max(plates_data[plate].values(), key=lambda x: x[1])
        except (TypeError, ValueError):
            print(plate)
            print(plates_data[plate])
            relevant_statuses[plate] = ('FAIL', None)

    return relevant_statuses
