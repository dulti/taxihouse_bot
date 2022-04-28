from environs import Env

# Теперь используем вместо библиотеки python-dotenv библиотеку environs
env = Env()
env.read_env()

BOT_TOKEN = env.str("BOT_TOKEN")  # Забираем значение типа str
ADMINS = env.list("ADMINS")  # Тут у нас будет список из админов
IP = env.str("ip")  # Тоже str, но для айпи адреса хоста

PGUSER = env.str("PGUSER")
PGPASS = env.str("PGPASS")
PGNAME = env.str("PGNAME")
PGHOST = env.str("PGHOST")

POSTGRES_URI = f"postgresql://{PGUSER}:{PGPASS}@{PGHOST}/{PGNAME}"

N_WORKERS = env.int('NWORKERS')
RECONN_ATTEMPTS = env.int('RECONN_ATTEMPTS')
TOTAL_PLATES = env.int('TOTAL_PLATES')

CONTACT_BOT = env.str('CONTACT_BOT')