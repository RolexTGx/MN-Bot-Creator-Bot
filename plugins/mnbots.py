import os
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pymongo import MongoClient
import datetime
from config import BOT, API, OWNER

# Constants
MAX_BOTS_PER_USER = 2
FOOTER = "\n\nJoin @mnbots for updates!"
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

# MongoDB setup
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["mn_bot_creator_db"]

# States for conversation
USER_STATES = {}

def add_footer(text):
    return text + FOOTER if FOOTER not in text else text

async def get_user_bots(user_id):
    return list(db.user_bots.find({"owner_id": user_id}))

async def get_bot_commands(bot_id):
    return list(db.bot_commands.find({"bot_id": bot_id}))

async def is_owner(user_id):
    return user_id == OWNER.ID

@Client.on_message(filters.command(["start", "help"]) & filters.private)
async def start_command(client, message: Message):
    user_id = message.from_user.id
    USER_STATES[user_id] = "main_menu"
    
    if await is_owner(user_id):
        keyboard = [
            [InlineKeyboardButton("My Bots", callback_data="my_bots")],
            [InlineKeyboardButton("Create New Bot", callback_data="create_bot")],
            [InlineKeyboardButton("Admin Panel", callback_data="admin_panel")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("My Bots", callback_data="my_bots")],
            [InlineKeyboardButton("Create New Bot", callback_data="create_bot")]
        ]
    
    await message.reply_text(
        add_footer(
            "Welcome to MN Bot Creator!\n\n"
            "Create your own Telegram bots with custom commands."
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@Client.on_callback_query(filters.regex(r"^(my_bots|create_bot|back_to_main|manage_bot_|add_command_|delete_command_)"))
async def handle_callbacks(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if data == "my_bots":
        bots = await get_user_bots(user_id)
        if not bots:
            await callback_query.answer(
                add_footer("You don't have any bots yet!"), 
                show_alert=True
            )
            return
        
        keyboard = []
        for bot in bots:
            keyboard.append([InlineKeyboardButton(bot["bot_name"], callback_data=f"manage_bot_{bot['bot_id']}")])
        
        keyboard.append([InlineKeyboardButton("Back", callback_data="back_to_main")])
        
        await callback_query.edit_message_text(
            add_footer("Your Bots:"),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "create_bot":
        user_bots = await get_user_bots(user_id)
        if len(user_bots) >= MAX_BOTS_PER_USER:
            await callback_query.answer(
                add_footer(f"You've reached the maximum limit of {MAX_BOTS_PER_USER} bots per user!"),
                show_alert=True
            )
            return
            
        USER_STATES[user_id] = "awaiting_bot_name"
        await callback_query.edit_message_text(
            add_footer("Please send me a name for your new bot:"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Cancel", callback_data="back_to_main")]
            ])
        )
    
    elif data.startswith("manage_bot_"):
        bot_id = data.split("_")[2]
        USER_STATES[user_id] = f"managing_bot_{bot_id}"
        
        bot = db.user_bots.find_one({"bot_id": bot_id, "owner_id": user_id})
        if not bot:
            await callback_query.answer("Bot not found!", show_alert=True)
            return
        
        commands = await get_bot_commands(bot_id)
        
        text = f"**Managing bot:** {bot['bot_name']}\n\n**Commands:**\n"
        text += "\n".join([f"/{cmd['command']} - {cmd['response']}" for cmd in commands]) if commands else "No commands yet"
        
        await callback_query.edit_message_text(
            add_footer(text),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Command", callback_data=f"add_command_{bot_id}")],
                [InlineKeyboardButton("🗑️ Delete Command", callback_data=f"delete_command_{bot_id}")],
                [InlineKeyboardButton("🔙 Back", callback_data="my_bots")]
            ])
        )
    
    elif data == "back_to_main":
        USER_STATES[user_id] = "main_menu"
        if await is_owner(user_id):
            keyboard = [
                [InlineKeyboardButton("My Bots", callback_data="my_bots")],
                [InlineKeyboardButton("Create New Bot", callback_data="create_bot")],
                [InlineKeyboardButton("Admin Panel", callback_data="admin_panel")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("My Bots", callback_data="my_bots")],
                [InlineKeyboardButton("Create New Bot", callback_data="create_bot")]
            ]
        
        await callback_query.edit_message_text(
            add_footer("Main Menu:"),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

@Client.on_message(filters.private & ~filters.command(["start", "help"]))
async def handle_messages(client, message: Message):
    user_id = message.from_user.id
    current_state = USER_STATES.get(user_id, "")
    
    if current_state == "awaiting_bot_name":
        bot_name = message.text
        
        user_bots = await get_user_bots(user_id)
        if len(user_bots) >= MAX_BOTS_PER_USER:
            await message.reply_text(
                add_footer(f"You've reached the maximum limit of {MAX_BOTS_PER_USER} bots per user!"),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("My Bots", callback_data="my_bots")]
                ])
            )
            return
        
        bot_id = f"mnbot_{user_id}_{datetime.datetime.now().timestamp()}"
        
        db.user_bots.insert_one({
            "bot_id": bot_id,
            "bot_name": bot_name,
            "owner_id": user_id,
            "created_at": datetime.datetime.now(),
            "bot_token": None  # User will need to set this later
        })
        
        USER_STATES[user_id] = "main_menu"
        
        await message.reply_text(
            add_footer(
                f"Bot '{bot_name}' created successfully!\n\n"
                "Next step: Please provide the bot token from @BotFather."
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("My Bots", callback_data="my_bots")],
                [InlineKeyboardButton("Main Menu", callback_data="back_to_main")]
            ])
        )
        USER_STATES[user_id] = f"awaiting_bot_token_{bot_id}"
    
    elif current_state.startswith("awaiting_bot_token_"):
        bot_id = current_state.split("_", 3)[-1]
        bot_token = message.text.strip()
        
        # Basic validation
        if not bot_token.count(":") == 1 or len(bot_token) < 30:
            await message.reply_text(
                add_footer("Invalid bot token format. Please provide a valid token from @BotFather.")
            )
            return
        
        # Update bot with token
        db.user_bots.update_one(
            {"bot_id": bot_id, "owner_id": user_id},
            {"$set": {"bot_token": bot_token}}
        )
        
        USER_STATES[user_id] = "main_menu"
        
        await message.reply_text(
            add_footer(
                "Bot token saved successfully!\n\n"
                "Your bot is now ready to use. You can add commands from the 'My Bots' menu."
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("My Bots", callback_data="my_bots")],
                [InlineKeyboardButton("Main Menu", callback_data="back_to_main")]
            ])
        )

@Client.on_callback_query(filters.regex("^admin_panel$"))
async def admin_panel(client, callback_query):
    if not await is_owner(callback_query.from_user.id):
        await callback_query.answer("Access denied!", show_alert=True)
        return
    
    total_bots = db.user_bots.count_documents({})
    total_users = len(db.user_bots.distinct("owner_id"))
    
    await callback_query.edit_message_text(
        add_footer(
            f"👑 Admin Panel\n\n"
            f"• Total Bots: {total_bots}\n"
            f"• Total Users: {total_users}\n"
            f"• MongoDB: {MONGO_URI.split('@')[-1] if '@' in MONGO_URI else MONGO_URI}"
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
        ])
    )
