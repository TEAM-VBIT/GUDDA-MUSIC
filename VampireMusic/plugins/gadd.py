import asyncio

from pyrogram import filters, types

from VampireMusic import app, config, db


@app.on_message(filters.command("gadd") & filters.user(config.OWNER_ID))
async def add_allbot(_, message: types.Message):
    command_parts = message.text.split(" ")
    if len(command_parts) != 2:
        await message.reply(
            "❍ ɪɴᴠᴀʟɪᴅ ᴄᴏᴍᴍᴀɴᴅ ғᴏʀᴍᴀᴛ. ᴘʟᴇᴀsᴇ ᴜsᴇ ʟɪᴋᴇ » <code>/gadd Bot_username</code>"
        )
        return

    bot_username = command_parts[1]
    try:
        userbot_client = await db.get_client(message.chat.id)
        bot = await app.get_users(bot_username)
        app_id = bot.id
        done = 0
        failed = 0
        lol = await message.reply("❍ ᴀᴅᴅɪɴɢ ɢɪᴠᴇɴ ʙᴏᴛ ɪɴ ᴀʟʟ ᴄʜᴀᴛs!")
        await userbot_client.send_message(bot_username, f"/start")
        async for dialog in userbot_client.get_dialogs():
            if dialog.chat.id == -1004420371020:
                continue
            try:

                await userbot_client.add_chat_members(dialog.chat.id, app_id)
                done += 1
                await lol.edit(
                    f"❍ ᴀᴅᴅɪɴɢ {bot_username}\n\n➥ ᴀᴅᴅᴇᴅ ɪɴ {done} ᴄʜᴀᴛs ✔\n➥ ғᴀɪʟᴇᴅ ɪɴ {failed} ᴄʜᴀᴛs ✘\n\n➲ ᴀᴅᴅᴇᴅ ʙʏ » @{userbot_client.username}"
                )
            except Exception as e:
                failed += 1
                await lol.edit(
                    f"❍ ᴀᴅᴅɪɴɢ {bot_username}\n\n➥ ᴀᴅᴅᴇᴅ ɪɴ {done} ᴄʜᴀᴛs ✔\n➥ ғᴀɪʟᴇᴅ ɪɴ {failed} ᴄʜᴀᴛs ✘\n\n➲ ᴀᴅᴅɪɴɢ ʙʏ » @{userbot_client.username}"
                )
            await asyncio.sleep(3)

        await lol.edit(
            f"❍ {bot_username} ʙᴏᴛ ᴀᴅᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ🎉**\n\n**➥ ᴀᴅᴅᴇᴅ ɪɴ {done} ᴄʜᴀᴛs ✅\n➥ ғᴀɪʟᴇᴅ ɪɴ {failed} ᴄʜᴀᴛs ✘\n\n➲ ᴀᴅᴅᴇᴅ ʙʏ » @{userbot_client.username}"
        )
    except Exception as e:
        await message.reply(f"Error: {str(e)}")
