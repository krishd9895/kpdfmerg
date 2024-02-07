import os
import telebot
from PyPDF2 import PdfMerger
from webserver import keep_alive

telegram_token = os.environ['TELEGRAM_TOKEN']
bot = telebot.TeleBot(telegram_token)

pdfs_received = []
pdfs_received_messages = []
progress_message = None
merge_in_progress = False

@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, "Welcome to the PDF Merger Bot!\nTry /help for more details.")

@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = """
    This bot can merge multiple PDFs into a single PDF.

    Usage:
    1. Send the '/mergepdf' command to start the merging process.
    2. Send the PDF files one by one.
    3. Send 'done' to start the merge operation.
    """
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['mergepdf'])
def handle_mergepdf(message):
    global pdfs_received, pdfs_received_messages, progress_message, merge_in_progress
    pdfs_received = []
    pdfs_received_messages = []
    progress_message = None
    merge_in_progress = True
    bot.reply_to(message, "Please send the PDFs one by one. Send 'done' when finished.")

@bot.message_handler(content_types=['document'])
def handle_pdf(message):
    global pdfs_received, pdfs_received_messages, progress_message, merge_in_progress
    if merge_in_progress and message.document.mime_type == 'application/pdf':
        file_size = message.document.file_size
        if file_size > 5 * 1024 * 1024:
            bot.reply_to(message, "File size exceeds the limit of 5 MB. Please send a smaller PDF.")
            return

        if len(pdfs_received) >= 5:
            bot.reply_to(message, "Maximum file limit of 5 reached. Please send 'done' to start merging.")
            return

        pdfs_received.append((message.document.file_id, file_size))
        count = len(pdfs_received)
        # Delete earlier message
        if len(pdfs_received_messages) > 0:
            try:
                bot.delete_message(message.chat.id, pdfs_received_messages[-1].message_id)
                pdfs_received_messages.pop()
            except telebot.apihelper.ApiTelegramException:
                pass
        pdfs_received_messages.append(bot.reply_to(message, f"{count} PDFs received so far. Please send 'done' when finished."))

@bot.message_handler(func=lambda message: message.text.lower() == 'done')
def handle_merge(message):
    global pdfs_received, pdfs_received_messages, progress_message, merge_in_progress
    if merge_in_progress:
        merge_in_progress = False
        pdf_dir = 'merged_pdfs'
        merged_file_path = 'merged.pdf'
        merger = PdfMerger()

        # Check if there are PDFs to merge
        if len(pdfs_received) == 0:
            bot.reply_to(message, "No PDFs received. Send the PDFs first.")
            return

        # Check total file size limit
        total_size = sum(size for _, size in pdfs_received)
        if total_size > 15 * 1024 * 1024:
            bot.reply_to(message, "Total file size exceeds the limit of 15 MB. Please send smaller PDFs.")
            return

        # Delete the earlier messages
        for msg in pdfs_received_messages:
            try:
                bot.delete_message(message.chat.id, msg.message_id)
            except telebot.apihelper.ApiTelegramException:
                pass

        progress_message = bot.reply_to(message, "Merging in progress...")

        # Download the PDFs and merge them
        for index, (file_id, _) in enumerate(pdfs_received):
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            file_path = os.path.join(pdf_dir, f"file_{index}.pdf")

            with open(file_path, 'wb') as f:
                f.write(downloaded_file)

            # Merge the PDFs in the order of their merger
            merger.append(file_path)

        # Save the merged PDF
        merged_file_path = get_unique_file_path(merged_file_path)
        merger.write(merged_file_path)
        merger.close()

        # Send the merged PDF to the user
        try:
            with open(merged_file_path, 'rb') as f:
                bot.send_document(message.chat.id, f)

            # Inform the user about the number of PDFs merged
            merged_count = len(pdfs_received)
            bot.reply_to(message, f"Merging completed. {merged_count} PDFs merged.")

        except Exception as e:
            bot.reply_to(message, "Failed to send the merged PDF.")

        # Delete the downloaded PDF files
        for index in range(len(pdfs_received)):
            file_path = os.path.join(pdf_dir, f"file_{index}.pdf")
            if os.path.exists(file_path):
                os.remove(file_path)

        # Delete the merged PDF file
        if os.path.exists(merged_file_path):
            os.remove(merged_file_path)

        # Delete the progress message
        try:
            bot.delete_message(message.chat.id, progress_message.message_id)
        except telebot.apihelper.ApiTelegramException:
            pass

        # Clear the received PDFs and messages
        pdfs_received = []
        pdfs_received_messages = []

    else:
        bot.reply_to(message, "Invalid command. Send '/help' for more information.")

def get_unique_file_path(file_path):
    # Adds a suffix to the file name if it already exists
    base_dir = os.path.dirname(file_path)
    base_name, ext = os.path.splitext(os.path.basename(file_path))
    suffix = 1
    while os.path.exists(file_path):
        file_path = os.path.join(base_dir, f"{base_name}_{suffix}{ext}")
        suffix += 1
    return file_path

@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    bot.reply_to(message, "Invalid command. Send '/help' for more information.")


# Create the merged_pdfs directory if it doesn't exist
pdf_dir = 'merged_pdfs'
if not os.path.exists(pdf_dir):
    os.makedirs(pdf_dir)

# Specify the merged file path
merged_file_path = os.path.join(pdf_dir, 'merged.pdf')

# Within the merge_pdf function
# Remove the previous merged PDF file if it exists
if os.path.exists(merged_file_path):
    os.remove(merged_file_path)

# Start the bot
keep_alive()
bot.polling()

                                   
