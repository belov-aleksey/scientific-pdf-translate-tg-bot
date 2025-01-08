import logging
import os

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.error import BadRequest
from pdf2zh import translate
from pdf_compressor import compress


# Replace with your bot token
BOT_TOKEN = '' # add your token

TRANSLATE_PARAMS = {
    'lang_in': 'en',
    'lang_out': 'ru',
    'service': 'google',
    'thread': 4,
    'pages': list(range(0, 10))
}

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot_logs.log"),
        logging.StreamHandler()
    ]
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"User {update.message.from_user} connected")
    await update.message.reply_text("Hi! Send me a PDF file, and I'll translate it for you.")

# File handler
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    file = update.message.document
    if file.mime_type != "application/pdf":
        update.message.reply_text("Please send a valid PDF file.")
        return
    logger.info(
        f"File {file.file_unique_id} received from the user {update.message.from_user.id}. Download..."
    )
    progress_bar_message = await update.message.reply_text("0%")    
    # Download the file
    file_id = file.file_id
    try:
        file = await context.bot.get_file(file_id)
        file_path = await file.download_to_drive()
        logger.info(
            f"The file {file.file_unique_id} has been successfully uploaded. Translate..."
        )
    except BadRequest as e:
        await update.message.reply_text("PDF file is too big. The file size must not exceed 10 MB")
        logger.info(
            f"The file {file.file_unique_id} is too big."
        )        
        return 

    await context.bot.edit_message_text(
        chat_id=progress_bar_message.chat_id,
        message_id=progress_bar_message.message_id,
        text="20%"
    )

    # Temp files names
    translated_file_out_path = 'ru_not_comressed.pdf'
    file_out_path = 'ru.pdf'

    # Perform translation (assuming pdf2zh is a command-line tool)
    try:
        await context.bot.edit_message_text(
            chat_id=progress_bar_message.chat_id,
            message_id=progress_bar_message.message_id,
            text="40%"
        )        
        (file_mono_path, file_dual_path) = translate(files=[str(file_path)], **TRANSLATE_PARAMS)[0]
        os.rename(file_mono_path, translated_file_out_path)
        # Try to compress pdf
        logger.info(
            f"Compress file {file.file_unique_id}..."
        )
        await context.bot.edit_message_text(
            chat_id=progress_bar_message.chat_id,
            message_id=progress_bar_message.message_id,
            text="80%"
        )            
        compress(translated_file_out_path, file_out_path)
        # Send back the translated PDF
        await context.bot.send_document(chat_id=update.message.chat_id, document=open(file_out_path, 'rb'))
        logger.info(
            f"The file {file.file_unique_id} has been successfully sent to user!.."
        )
        await context.bot.edit_message_text(
            chat_id=progress_bar_message.chat_id,
            message_id=progress_bar_message.message_id,
            text="100%"
        )                           
    except Exception as e:
        logger.error(
            f"Error during translation: {e}"
        )
        await update.message.reply_text(f"Error during translation :(")
    finally:
        # Delete progress bar message
        await context.bot.delete_message(
            chat_id=progress_bar_message.chat_id,
            message_id=progress_bar_message.message_id
        )          
        # Clean up temporary files
        # TODO: сохранять в папку и очистить всю папку 
        os.remove(file_path)
        if os.path.exists(file_mono_path):
            os.remove(file_mono_path)
        if os.path.exists(file_dual_path):
            os.remove(file_dual_path)
        if os.path.exists(translated_file_out_path):
            os.remove(translated_file_out_path)                   
        if os.path.exists(file_out_path):
            os.remove(file_out_path)             

# Main function to set up the bot
def main() -> None:
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))

    # on getting file - translate file 
    application.add_handler(
        MessageHandler(filters.Document.MimeType("application/pdf"), 
        handle_file)
    )

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)    

if __name__ == '__main__':
    main()