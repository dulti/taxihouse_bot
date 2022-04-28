"""
This file describes functions that only operate on database, without any bot interactions.
"""

from datetime import datetime

from asyncpg import Record

from utils.db_api.postgresql import Database
from utils.textprocessing import plates_rus


async def remove_watch_by_user_id(db: Database, id_: int, user_id: int, plate: str) -> None:
    watch_record_id = id_
    await db.remove_watch(watch_record_id)
    # log watch removal
    await db.add_operation(created_at=datetime.now(), operation='removewatch', user_id=user_id,
                           by_bot=False, plate=plate)


async def add_plate(db: Database, user_id: int, plate: str, status: str, date_: datetime) -> str:

    # check if this user added this plate
    existing_watch = await db.get_watch_by_user_by_plate(user_id, plate)
    # if yes: alert, update status
    if existing_watch:
        existing_plate = await db.get_plate(plate)
        await db.update_plate(plate=plate, status=status, status_date=date_,
                              updated_at=datetime.now(),
                              users_watching=existing_plate['users_watching'])
        return f'\nНомер {plate} уже был добавлен ранее. Новый статус: {status}.'

    # if no:
    else:
        # check if plate exists in plates
        existing_plate = await db.get_plate(plate)
        if existing_plate:
            # increment counter if yes
            await db.update_plate(plate=plate, status=existing_plate['status'],
                                  status_date=existing_plate['status_date'],
                                  updated_at=existing_plate['updated_at'],
                                  users_watching=existing_plate['users_watching'] + 1)
        else:
            # add plate if no
            await db.add_plate(plate=plate, status=status, status_date=date_, first_added_by=user_id,
                               created_at=datetime.now(), updated_at=datetime.now(), users_watching=1)
            # log operation
            await db.add_operation(created_at=datetime.now(),
                                   operation=f'addplate|status:{status}|stdate:{date_}',
                                   user_id=user_id, by_bot=False, plate=plate)

        # add watch
        await db.add_watch(user_id=user_id, plate=plate, created_at=datetime.now())
        # log operation
        await db.add_operation(created_at=datetime.now(), operation='watchplate',
                               user_id=user_id, by_bot=False, plate=plate)

        return f'\nНомер {plate} добавлен. Статус - {status}.'


async def force_delete_plate(db: Database, plate: str, user_id: int) -> str:
    # get all watches of the plate
    existing_watches = await db.get_watch_by_plate(plate=plate)
    # if nobody is watching, return
    if len(existing_watches) == 0:
        return f'Номер {plate} никем не отслеживается. Проверьте, правильно ли введен номер.\n'
    else:
        # remove all watches of the plate
        for watch_record in existing_watches:
            await remove_watch_by_user_id(db, watch_record['id'], user_id, plate)

        # remove from plates completely
        existing_plate = await db.get_plate(plate)
        plates_record_id = existing_plate['id']
        await db.remove_plate(plates_record_id)
        # remove plate from report if exists
        await db.remove_report_by_user(user_id)
        # log operation
        await db.add_operation(created_at=datetime.now(), operation='removeplate', user_id=None,
                               by_bot=True, plate=plate)

        return f'Номер {plate} удален из отслеживания для всех пользователей.\n'


async def delete_plate(db: Database, plate: str, user_id: int, by_bot: bool = False) -> bool:
    # check if watch exists
    existing_watch = await db.get_watch_by_user_by_plate(user_id, plate)
    # if yes, delete plate
    if existing_watch:
        # remove watch
        watch_record_id = existing_watch['id']
        await db.remove_watch(watch_record_id)

        # log operation
        await db.add_operation(created_at=datetime.now(), operation='removewatch', user_id=user_id,
                               by_bot=by_bot, plate=plate)

        # remove plate from report
        await db.remove_report_by_plate_user(plate, user_id)

        # update user count in plates
        existing_plate = await db.get_plate(plate)
        status = existing_plate['status']
        users_watching = existing_plate['users_watching']

        # if other users are watching the same plate, decrement users counter
        if users_watching > 1:
            await db.update_plate(plate=plate, status=status, status_date=existing_plate['status_date'],
                                  updated_at=datetime.now(), users_watching=users_watching - 1)

        # otherwise remove plate from plates
        else:
            plates_record_id = existing_plate['id']
            await db.remove_plate(plates_record_id)

            # log operation
            await db.add_operation(created_at=datetime.now(), operation='removeplate', user_id=None,
                                   by_bot=True, plate=plate)
        return True

    # if no, return
    else:
        return False


async def change_max_plates(db: Database, new_max_plates: int, user_id: int):

    # write to db
    await db.update_user_max_plates(user_id, new_max_plates)
    await db.add_operation(created_at=datetime.now(), operation=f'setmaxplates:{new_max_plates}',
                           user_id=user_id, by_bot=False, plate=None)


async def remove_extra_plates(db: Database, user_id: int, new_max_plates: int):
    # remove extra plates
    user_plates_count = await db.count_watches_by_user(user_id)
    extra_user_plates = await db.get_plates_by_user_with_limit(user_id, user_plates_count - new_max_plates)

    if len(extra_user_plates) > 0:
        msg_text = ''
        for record in extra_user_plates:
            if await delete_plate(db, record['plate'], user_id):
                msg_text += f'Номер {record["plate"]} удален из отслеживания.\n'
            else:
                msg_text += f'Вы не отслеживаете номер {record["plate"]}. Проверьте, правильно ли введен номер.\n'
        return msg_text

    return None


async def demote_user(db_: Database, user: Record) -> list[str]:
    dt_now = datetime.now()
    await db_.update_user(id_=user['id'], user_id=user['user_id'], username=user['username'], is_elevated=False,
                          is_active=True, is_admin=False, watch_on=user['watch_on'], updated_at=datetime.now(),
                          phone=user['phone'], max_plates=0, paid_until=dt_now, delta_paid_until=0)
    # get all plates watched by user
    plates = await db_.get_plates_by_user(user['user_id'])
    deleted_plates = []
    for plate in plates:
        plate = plate['plate']
        deleted_plates.append(plate)
        existing_watch = await db_.get_watch_by_user_by_plate(user['user_id'], plate)
        watch_record_id = existing_watch['id']
        await db_.remove_watch(watch_record_id)
        # update user count in plates
        existing_plate = await db_.get_plate(plate)
        status = existing_plate['status']
        users_watching = existing_plate['users_watching']
        # if other users are watching the same plate, remove watch and decrement users counter
        if users_watching > 1:
            await db_.update_plate(plate=plate, status=status, status_date=existing_plate['status_date'],
                                   updated_at=datetime.now(), users_watching=users_watching - 1)
            # log watch removal
            await db_.add_operation(created_at=datetime.now(), operation='removewatch', user_id=user['user_id'],
                                    by_bot=False, plate=plate)
        # otherwise remove plate from plates
        else:
            plates_record_id = existing_plate['id']
            await db_.remove_plate(plates_record_id)
            await db_.remove_report_by_user(user['user_id'])
            # log plate removal
            await db_.add_operation(created_at=datetime.now(), operation='removeplate', user_id=None,
                                    by_bot=True, plate=plate)
    await db_.add_operation(created_at=datetime.now(), operation='demoteuser', user_id=user['user_id'],
                            by_bot=False, plate=None)

    return deleted_plates
