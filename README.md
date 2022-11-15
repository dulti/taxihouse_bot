# Taxihouse bot
https://t.me/TaxiHouseLT_bot

Data parsing and notification Telegram bot.

- parses open sources for information on valid taxi licenses issued by Moscow and Moscow Oblast transport authorities
- sets up a regular monitor for license status change
- in case of a status change notifies user of the change
- supports free and paid version
- paid version allows for monitoring of unlimited number of license plates and extra functionality for bulk adding/removing plates
- user management is done through the bot itself
- user data and plates status data done in PostgreSQL

The bot is ran by running app.py.

Specify values in .env before running (.env.dist given as example).
