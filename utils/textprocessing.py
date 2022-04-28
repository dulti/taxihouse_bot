import re
from datetime import datetime
from typing import Callable

plate_regexp = r'[А-Яа-яA-Za-z]{1,2}\d{3}([А-Яа-яA-Za-z]{2})?\d{2,3}'


def lattocyr(plate):
    convert_dict = {'A': 'А', 'B': 'В', 'C': 'С', 'E': 'Е',
                    'H': 'Н', 'K': 'К', 'M': 'М', 'O': 'О',
                    'P': 'Р', 'T': 'Т', 'X': 'Х', 'Y': 'У'}
    new_plate = []
    for letter in plate:
        if letter in convert_dict.keys():
            new_plate.append(convert_dict.get(letter))
        else:
            new_plate.append(letter)

    return ''.join(new_plate)


def noun_rus(singular: str, double: str, plural: str) -> Callable[[int], str]:
    def func(amt: int) -> str:
        if amt % 10 == 1 and amt % 100 // 10 != 1:
            form = singular
        elif amt % 10 in (2, 3, 4) and amt % 100 // 10 != 1:
            form = double
        else:
            form = plural
        return form
    return func


users_rus = noun_rus('пользователь', 'пользователя', 'пользователей')
plates_rus = noun_rus('номер', 'номера', 'номеров')
days_rus = noun_rus('день', 'дня', 'дней')
remaining_rus = noun_rus('остался', 'осталось', 'осталось')


def chunks(s, n):
    s_rows = s.split('\n')
    current_len = 0
    this_chunk = []
    for idx, row in enumerate(s_rows):
        current_len += len(row) + 1
        if current_len > n:
            current_len = 0
            yield_chunk = this_chunk.copy()
            this_chunk = []
            yield '\n'.join(yield_chunk)
        this_chunk.append(row)
    if len(this_chunk) > 0:
        yield '\n'.join(this_chunk)


def dt_to_readable(dt: datetime, form: int) -> str:
    """
    form=0: '01.01.1990 в 12:00'
    form=1: '12:00 01.01.1990'
    """
    forms = {0: f'{dt:%d.%m.%Y} в {dt:%H:%M}',
             1: f'{dt:%H:%M} {dt:%d.%m.%Y}'}
    return forms[form]


def process_input(text: str) -> (list, list):
    plates = text.split('\n')
    correct_plates = []
    incorrect_plates = []
    for plate in plates:
        plate = lattocyr(plate.strip().upper())
        if re.match(plate_regexp, plate):
            correct_plates.append(plate)
        else:
            incorrect_plates.append(plate)
    return correct_plates, incorrect_plates, len(plates)


def max_plates_readable(new_max_plates: int):
    # make string readable
    if new_max_plates == -1:
        new_max_plates_str = 'бесконечное количество'
        number_str = 'номеров'
    else:
        new_max_plates_str = str(new_max_plates)
        number_str = plates_rus(new_max_plates)
    return new_max_plates_str, number_str


def parse_date(dt_str: str, dt_now: datetime = None) -> datetime:
    for fmt in ('%d.%m.%Y %H:%M', '%d.%m.%Y'):
        try:
            result = datetime.strptime(dt_str, fmt)
            if fmt == '%d.%m.%Y':
                if dt_now:
                    result = result.replace(hour=dt_now.hour, minute=dt_now.minute, second=dt_now.second,
                                            microsecond=dt_now.microsecond)
            return result
        except ValueError:
            pass
    raise ValueError('Invalid datetime format!')
