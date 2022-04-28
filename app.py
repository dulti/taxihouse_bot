from aiogram import executor

from loader import dp, scheduler, db
import middlewares, filters, handlers

from utils.notify_admins import on_startup_notify
from utils.set_bot_commands import set_default_commands
from utils.schedulers import send_message_to_watchers, send_report_to_watchers, notify_change_max_plates, \
    notify_paid_until


def schedule_jobs():
    scheduler.add_job(send_message_to_watchers, 'cron', hour='6-23', minute=0, args=(dp, db))
    scheduler.add_job(send_report_to_watchers, 'cron', hour=9, args=(dp, db))
    scheduler.add_job(send_report_to_watchers, 'cron', hour=17, minute=40, args=(dp, db))
    scheduler.add_job(notify_change_max_plates, 'cron', minute='*/5', args=(dp, db))
    scheduler.add_job(notify_paid_until, 'cron', minute='*/5', args=(dp, db))


async def on_startup(dispatcher):
    # set default commands
    await set_default_commands(dispatcher)

    # start database
    await db.create()

    # create tables (IF DO NOT EXIST)
    await db.create_table_users()
    await db.create_table_plates()
    await db.create_table_watches()
    await db.create_table_operations()
    await db.create_table_report()
    await db.create_table_notifications()
    await db.create_service_table()

    # run scheduled jobs
    schedule_jobs()

    # notify admins
    await on_startup_notify(dispatcher)


if __name__ == '__main__':
    scheduler.start()
    executor.start_polling(dp, on_startup=on_startup)
