from data import config
from keyboards.default.admin_kb import admin_kb
from keyboards.default.elevated_kb import elevated_kb
from keyboards.default.regular_kb import regular_kb
from loader import db


async def get_keyboard(user_id):
    if str(user_id) in config.ADMINS:
        keyboard = admin_kb
    else:
        try:
            if (await db.get_user_by_user_id(user_id))['is_elevated']:
                keyboard = elevated_kb
            else:
                keyboard = regular_kb
        except TypeError:
            keyboard = regular_kb
    return keyboard
