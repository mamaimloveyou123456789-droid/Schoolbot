import os
import time
import logging
import json
import csv
from datetime import datetime
from telegram.ext import Application, MessageHandler, filters, CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# БЕЗОПАСНОЕ ПОЛУЧЕНИЕ ДАННЫХ ИЗ ПЕРЕМЕННЫХ СРЕДЫ
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))

if not BOT_TOKEN or not ADMIN_ID:
    raise ValueError("BOT_TOKEN и ADMIN_ID должны быть установлены в переменных окружения")

logging.basicConfig(level=logging.INFO)

# Flask app для Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running"

class AdvancedBot:
    def __init__(self):
        self.user_messages = {}
        self.saved_messages = []
        self.user_limits = {}
        self.default_limit = 3
        self.message_links = {}
    
    def add_saved_message(self, message_data):
        self.saved_messages.append(message_data)
    
    def delete_saved_message(self, message_index):
        if 0 <= message_index < len(self.saved_messages):
            return self.saved_messages.pop(message_index)
        return None
    
    def get_user_limit(self, user_id):
        return self.user_limits.get(str(user_id), self.default_limit)
    
    def set_user_limit(self, user_id, limit):
        self.user_limits[str(user_id)] = limit
    
    def set_default_limit(self, limit):
        self.default_limit = limit
    
    def get_remaining_messages(self, user_id):
        current_time = time.time()
        user_limit = self.get_user_limit(user_id)
        
        if user_id not in self.user_messages:
            return user_limit
        
        last_time, count = self.user_messages[user_id]
        
        if current_time - last_time >= 3600:
            return user_limit
        
        remaining = user_limit - count
        return max(0, remaining)
    
    async def handle_start(self, update, context):
        user = update.effective_user
        user_limit = self.get_user_limit(user.id)
        remaining = self.get_remaining_messages(user.id)
        
        start_message = f"Бот начал работу. Напишите ваше сообщение.\n"
        start_message += f"Лимит: {user_limit} сообщений в час\n"
        start_message += f"Осталось сообщений: {remaining}"
        
        await update.message.reply_text(start_message)
    
    async def handle_admin_commands(self, update, context):
        if update.effective_user.id != ADMIN_ID:
            return
        
        command = update.message.text
        
        if command == "/saved":
            if not self.saved_messages:
                await update.message.reply_text("Нет сохраненных сообщений.")
                return
            
            message_list = "Сохраненные сообщения:\n\n"
            for i, msg in enumerate(self.saved_messages, 1):
                message_text = msg.get('text', 'Медиа-сообщение')
                message_list += f"{i}. {message_text[:50]}...\n"
                message_list += f"   От: {msg['user_name']} (ID: {msg['user_id']})\n"
                message_list += f"   Время: {msg['timestamp']}\n\n"
            
            keyboard_buttons = []
            for i in range(len(self.saved_messages)):
                keyboard_buttons.append([
                    InlineKeyboardButton(f"Удалить {i+1}", callback_data=f"delete_{i}"),
                    InlineKeyboardButton(f"Просмотр {i+1}", callback_data=f"view_{i}"),
                    InlineKeyboardButton(f"Ответить {i+1}", callback_data=f"reply_{i}")
                ])
            
            keyboard_buttons.append([InlineKeyboardButton("Скачать CSV", callback_data="download_csv")])
            keyboard_buttons.append([InlineKeyboardButton("Очистить все", callback_data="clear_all")])
            
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
            await update.message.reply_text(message_list, reply_markup=keyboard)
        
        elif command == "/download":
            if not self.saved_messages:
                await update.message.reply_text("Нет сообщений для скачивания.")
                return
            
            csv_filename = "messages.csv"
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['timestamp', 'user_id', 'user_name', 'username', 'text']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for msg in self.saved_messages:
                    writer.writerow(msg)
            
            await update.message.reply_document(
                document=open(csv_filename, 'rb'),
                filename=csv_filename
            )
        
        elif command == "/stats":
            total_messages = len(self.saved_messages)
            unique_users = len(set(msg['user_id'] for msg in self.saved_messages))
            
            stats_text = f"Статистика:\n"
            stats_text += f"Всего сообщений: {total_messages}\n"
            stats_text += f"Уникальных пользователей: {unique_users}\n"
            stats_text += f"Лимит по умолчанию: {self.default_limit} сообщений/час"
            
            await update.message.reply_text(stats_text)
        
        elif command.startswith("/limit "):
            try:
                parts = command.split()
                if len(parts) == 2:
                    new_limit = int(parts[1])
                    self.set_default_limit(new_limit)
                    await update.message.reply_text(f"Лимит по умолчанию установлен: {new_limit} сообщений/час")
                elif len(parts) == 3:
                    user_id = int(parts[1])
                    new_limit = int(parts[2])
                    self.set_user_limit(user_id, new_limit)
                    await update.message.reply_text(f"Лимит для пользователя {user_id} установлен: {new_limit} сообщений/час")
                else:
                    await update.message.reply_text("Использование: /limit [user_id] <количество>")
            except ValueError:
                await update.message.reply_text("Ошибка: используйте числа")
        
        elif command == "/limits":
            limits_text = f"Лимит по умолчанию: {self.default_limit} сообщений/час\n\n"
            
            if self.user_limits:
                limits_text += "Индивидуальные лимиты:\n"
                for user_id, limit in self.user_limits.items():
                    limits_text += f"Пользователь {user_id}: {limit} сообщений/час\n"
            else:
                limits_text += "Индивидуальных лимитов нет"
            
            await update.message.reply_text(limits_text)
        
        elif command == "/help":
            help_text = "Команды админа:\n"
            help_text += "/saved - список сообщений\n"
            help_text += "/download - скачать CSV\n"
            help_text += "/stats - статистика\n"
            help_text += "/limit <количество> - установить лимит по умолчанию\n"
            help_text += "/limit <user_id> <количество> - лимит для пользователя\n"
            help_text += "/limits - показать лимиты\n"
            help_text += "/help - справка"
            await update.message.reply_text(help_text)
    
    async def handle_message(self, update, context):
        user = update.effective_user
        user_id = user.id
        
        # Обработка ответов админа
        if user_id == ADMIN_ID:
            if 'waiting_reply' in context.user_data:
                target_data = context.user_data['waiting_reply']
                target_user_id = target_data['user_id']
                
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"Ответ: {update.message.text}"
                    )
                    await update.message.reply_text("Ответ отправлен.")
                    
                except Exception as e:
                    await update.message.reply_text("Ошибка отправки ответа.")
                finally:
                    del context.user_data['waiting_reply']
            return
        
        # Проверка лимита для пользователей
        user_limit = self.get_user_limit(user_id)
        remaining = self.get_remaining_messages(user_id)
        
        if remaining <= 0:
            await update.message.reply_text(f"Лимит сообщений исчерпан. Попробуйте через час.")
            return
        
        # Обновление счетчика
        current_time = time.time()
        if user_id in self.user_messages:
            last_time, count = self.user_messages[user_id]
            if current_time - last_time < 3600:
                self.user_messages[user_id] = (last_time, count + 1)
            else:
                self.user_messages[user_id] = (current_time, 1)
        else:
            self.user_messages[user_id] = (current_time, 1)
        
        remaining_after = self.get_remaining_messages(user_id)
        
        try:
            # Пересылаем сообщение админу
            forwarded_msg = await context.bot.forward_message(
                chat_id=ADMIN_ID,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
            
            # Информация для админа
            user_info = f"Новое сообщение\n"
            user_info += f"От: {user.first_name or 'Не указано'}\n"
            user_info += f"ID: {user_id}\n"
            if user.username:
                user_info += f"Username: @{user.username}\n"
            user_info += f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
            user_info += f"Лимит: {user_limit}/час\n"
            user_info += f"Осталось: {remaining_after}\n"
            
            if update.message.text:
                user_info += f"Текст: {update.message.text[:100]}{'...' if len(update.message.text) > 100 else ''}"
            else:
                user_info += f"Тип: {update.message.content_type}"
            
            # Кнопки для админа
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Ответить", callback_data=f"quick_reply_{user_id}_{forwarded_msg.message_id}"),
                    InlineKeyboardButton("Сохранить", callback_data=f"save_{user_id}_{forwarded_msg.message_id}")
                ],
                [InlineKeyboardButton("Удалить", callback_data=f"delete_msg_{forwarded_msg.message_id}")]
            ])
            
            info_msg = await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=user_info,
                reply_markup=keyboard
            )
            
            # Сохраняем связь для удаления
            self.message_links[forwarded_msg.message_id] = {
                'user_id': user_id,
                'user_message_id': update.message.message_id,
                'admin_info_id': info_msg.message_id,
                'chat_id': update.message.chat_id,
                'message_text': update.message.text or "Медиа-сообщение",
                'user_name': user.first_name or 'Не указано',
                'username': user.username or 'Не указан'
            }
            
            # Ответ пользователю
            user_response = f"Сообщение доставлено. Осталось сообщений: {remaining_after}"
            await update.message.reply_text(user_response)
            
        except Exception as e:
            print(f"Ошибка: {e}")
            await update.message.reply_text("Ошибка при отправке сообщения.")
    
    async def handle_callback(self, update, context):
        query = update.callback_query
        data = query.data
        
        if data == "download_csv":
            if not self.saved_messages:
                await query.answer("Нет сообщений")
                return
            
            csv_filename = "messages.csv"
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['timestamp', 'user_id', 'user_name', 'username', 'text']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for msg in self.saved_messages:
                    writer.writerow(msg)
            
            await context.bot.send_document(
                chat_id=ADMIN_ID,
                document=open(csv_filename, 'rb'),
                filename=csv_filename
            )
            await query.answer("Файл отправлен")
        
        elif data == "clear_all":
            self.saved_messages.clear()
            await query.answer("Все сообщения удалены")
            await query.edit_message_text("Все сообщения удалены.")
        
        elif data.startswith("delete_"):
            if data.startswith("delete_msg_"):
                # Удаление из чата
                admin_message_id = int(data.split('_')[2])
                message_link = self.message_links.get(admin_message_id)
                
                if message_link:
                    try:
                        # Удаляем у админа
                        await context.bot.delete_message(ADMIN_ID, admin_message_id)
                        await context.bot.delete_message(ADMIN_ID, message_link['admin_info_id'])
                        # Удаляем у пользователя
                        await context.bot.delete_message(message_link['chat_id'], message_link['user_message_id'])
                    except Exception as e:
                        print(f"Ошибка удаления: {e}")
                    await query.answer("Сообщение удалено")
            else:
                # Удаление из сохраненных
                message_index = int(data.split('_')[1])
                deleted_msg = self.delete_saved_message(message_index)
                if deleted_msg:
                    await query.answer("Сообщение удалено")
                    await query.edit_message_text(f"Сообщение {message_index + 1} удалено.")
        
        elif data.startswith("view_"):
            message_index = int(data.split('_')[1])
            if 0 <= message_index < len(self.saved_messages):
                msg = self.saved_messages[message_index]
                full_text = f"Сообщение {message_index + 1}:\n\n"
                full_text += f"Время: {msg['timestamp']}\n"
                full_text += f"От: {msg['user_name']}\n"
                full_text += f"ID: {msg['user_id']}\n"
                full_text += f"Username: {msg['username']}\n"
                full_text += f"Текст: {msg['text']}"
                
                await query.answer()
                await context.bot.send_message(ADMIN_ID, text=full_text)
        
        elif data.startswith("reply_") or data.startswith("quick_reply_"):
            if data.startswith("quick_reply_"):
                parts = data.split('_')
                user_id = int(parts[2])
            else:
                message_index = int(data.split('_')[1])
                if 0 <= message_index < len(self.saved_messages):
                    user_id = self.saved_messages[message_index]['user_id']
            
            context.user_data['waiting_reply'] = {'user_id': user_id}
            await query.answer("Введите ответ:")
        
        elif data.startswith("save_"):
            parts = data.split('_')
            user_id = int(parts[1])
            admin_message_id = int(parts[2])
            message_link = self.message_links.get(admin_message_id)
            
            if message_link and message_link['message_text'] != "Медиа-сообщение":
                message_data = {
                    'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
                    'user_id': user_id,
                    'user_name': message_link['user_name'],
                    'username': message_link['username'],
                    'text': message_link['message_text']
                }
                self.add_saved_message(message_data)
                await query.answer("Сообщение сохранено")
            else:
                await query.answer("Нельзя сохранить медиа-сообщение")

# Создаем бота
bot = AdvancedBot()

def setup_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", bot.handle_start))
    application.add_handler(CommandHandler("saved", bot.handle_admin_commands))
    application.add_handler(CommandHandler("download", bot.handle_admin_commands))
    application.add_handler(CommandHandler("stats", bot.handle_admin_commands))
    application.add_handler(CommandHandler("limit", bot.handle_admin_commands))
    application.add_handler(CommandHandler("limits", bot.handle_admin_commands))
    application.add_handler(CommandHandler("help", bot.handle_admin_commands))
    application.add_handler(MessageHandler(filters.ALL, bot.handle_message))
    application.add_handler(CallbackQueryHandler(bot.handle_callback))
    
    return application

# Запуск для Render
def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Запускаем бота
    application = setup_bot()
    print("Бот запущен на Render")
    application.run_polling()
