import os
import shutil
import tempfile
from flask import Flask, render_template, request, redirect, url_for, session, send_file
import pandas as pd
import json
import time
from flask import request, jsonify
from datetime import datetime, timedelta
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
import json
from werkzeug.security import check_password_hash
from io import BytesIO
import numpy as np
app = Flask(__name__, static_url_path='/static')
app.secret_key = os.urandom(24)  # Секретный ключ для сессий

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(BASE_DIR, 'data/baza.xlsx')
sales_path = os.path.join(BASE_DIR, 'data/sales.xlsx')
images_path = os.path.join(BASE_DIR, 'data/images.xlsx')

df = pd.read_excel(data_path, engine='openpyxl')
df = df.where(pd.notnull(df), None)

login_manager = LoginManager()
login_manager.init_app(app)

class User:
    def __init__(self, id, role):
        self.id = id
        self.role = role

    def is_authenticated(self):
        return True

    def is_active(self):
        return True  # Пользователь всегда активен

    def is_anonymous(self):
        return False  # Пользователь не анонимный

    def get_id(self):
        return self.id

    def is_admin(self):
        return self.role == "admin"

def convert_to_serializable(obj):
    if isinstance(obj, np.int64):
        return int(obj)
    elif isinstance(obj, np.float64):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(i) for i in obj]
    return obj

# Функция для загрузки пользователя по ID
@login_manager.user_loader
def load_user(user_id):
    # Здесь можно добавить проверку, например, по базе данных
    if user_id == "admin":
        return User(user_id, "admin")
    else:
        return User(user_id, "user")

# Роут для логина (пример)
# Загрузка конфигурации (хэш пароля)
with open(os.path.join(BASE_DIR, 'config.json')) as f:
    config = json.load(f)
admin_password_hash = config['admin_password_hash']

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password and check_password_hash(admin_password_hash, password):
            session['role'] = 'admin'
            login_user(User('admin', 'admin'))
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Неверный пароль")
    return render_template('login.html')

# Роут для выхода
@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))  # Перенаправляем на страницу входа

# Функция для преобразования русских названий цветов в английские
def get_color(color):
    color_map = {
        'красный': 'red',
        'синий': 'blue',
        'желтый': 'yellow',
        'зеленый': 'green',
        'черный': 'black',
        'белый': 'white',
        'оранжевый': 'orange',
        'фиолетовый': 'purple',
        'розовый': 'pink',
        'серый': 'gray',
        'бежевый': 'beige'
        # Добавьте другие цвета по мере необходимости
    }
    return color_map.get(color.lower(), 'transparent')  # Возвращает прозрачный цвет по умолчанию, если цвет не найден

# Регистрация функции как фильтра в Jinja
app.jinja_env.filters['get_color'] = get_color

def generate_unique_id(category, name, gender):
    category_part = category[:3].upper() if category else ""
    name_part = name[:3].upper() if name else ""
    gender_part = gender[:1].upper() if gender else ""
    base_id = f"{category_part}{name_part}{gender_part}"

    existing_ids = df['ID'].dropna().tolist()
    existing_numbers = [int(id[len(base_id):]) for id in existing_ids if id.startswith(base_id) and id[len(base_id):].isdigit()]
    max_number = max(existing_numbers) if existing_numbers else 0

    unique_id = f"{base_id}{max_number + 1}"
    return unique_id


def generate_unique_filename(filename, directory):
    base, ext = os.path.splitext(filename)
    counter = 1
    unique_filename = filename
    while os.path.exists(os.path.join(directory, unique_filename)):
        unique_filename = f"{base}_{counter}{ext}"
        counter += 1
    return unique_filename

def parse_size_color_quantity(entry):
    parts = entry.split('-')
    if len(parts) == 3:
        size = parts[0].strip()
        color = parts[1].strip()
        quantity = int(parts[2].strip())
    elif len(parts) == 2:
        size = parts[0].strip()
        color = None
        quantity = int(parts[1].strip())
    else:
        size = parts[0].strip() if len(parts) > 0 else None
        color = None
        quantity = None
    return size, color, quantity

for index, row in df.iterrows():
    size_color_qty = row['Размер_цвет_количество']
    if isinstance(size_color_qty, str):
        entries = size_color_qty.split(',')
        sizes_and_quantities = {}
        for entry in entries:
            size, color, quantity = parse_size_color_quantity(entry)
            if size not in sizes_and_quantities:
                sizes_and_quantities[size] = {}
            if color and quantity:
                sizes_and_quantities[size][color] = quantity
            elif quantity:
                sizes_and_quantities[size][None] = quantity
        df.at[index, 'Размеры_и_количество'] = json.dumps(sizes_and_quantities)

df.to_excel(data_path, index=False, engine='openpyxl')

@app.route('/')
def index():
    try:
        products = df[['ID', 'Наименование_товара', 'Цена']].to_dict('records')
        images_df = pd.read_excel(os.path.join(BASE_DIR, 'data', 'images.xlsx'), engine='openpyxl')
    except Exception as e:
        print(f"Ошибка чтения файла Excel: {e}")
        images_df = pd.DataFrame(columns=['ID', 'Ссылка', 'Цвет', 'Позиция'])

    for product in products:
        product_images = images_df[images_df['ID'] == product['ID']]
        sorted_images = product_images.sort_values(by='Позиция').to_dict('records')
        main_image = sorted_images[0]['Ссылка'] if sorted_images else None
        product['main_image'] = main_image
        product['images'] = sorted_images if sorted_images else []

    user_role = session.get('role', 'user')  # Пример получения роли пользователя (можно установить по авторизации)

    return render_template('index.html', products=products, role=user_role)

@app.route('/cart')
def cart():
    return render_template('cart.html')


@app.route('/upload_temp_image', methods=['POST'])
def upload_temp_image():
    if 'photo' in request.files:
        photo = request.files['photo']
        selected_color = request.form.get('color', 'default')
        product_id = request.form.get('product_id', 'default')

        unique_photo_filename = generate_unique_filename(f"{product_id}_{selected_color}.jpg",
                                                         os.path.join(BASE_DIR, 'static', 'images'))

        try:
            images_dir = os.path.join(BASE_DIR, 'static', 'images')
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)

            temp_file_path = os.path.join(images_dir, unique_photo_filename)
            photo.save(temp_file_path)
            print(f"Временное изображение сохранено по пути: {temp_file_path}, Привязка к цвету: {selected_color}")
            return {"temp_photo_path": unique_photo_filename}, 200
        except Exception as e:
            print(f"Ошибка при сохранении временного файла: {e}")
            return {"error": "Ошибка при сохранении временного файла"}, 500
    else:
        print("Ошибка: Нет предоставленного фото")
        return {"error": "No photo provided"}, 400


@app.route('/save_product', methods=['POST'])
def save_product():
    global df

    product_id = request.form.get('product_id')
    new_name = request.form.get('name')
    price = request.form.get('price')
    cost_price = request.form.get('cost_price')  # Новое поле для закупочной цены
    description = request.form.get('description')
    gender = request.form.get('gender')
    season = request.form.get('season')
    category = request.form.get('category')
    sizes = request.form.getlist('sizes[]')
    colors_list = request.form.getlist('colors[]')
    quantities = request.form.getlist('quantities[]')
    temp_photo_paths = json.loads(request.form.get('temp_photo_paths', '[]'))
    photo_order = json.loads(request.form.get('photo_order', '[]'))

    product_row_index = df[df['ID'] == product_id].index[0]

    old_category = df.at[product_row_index, 'Категория']
    old_name = df.at[product_row_index, 'Наименование_товара']
    old_gender = df.at[product_row_index, 'Пол']

    # Генерация нового ID, если категория, имя или пол изменены
    if old_category != category or old_name != new_name or old_gender != gender:
        new_id = generate_unique_id(category, new_name, gender)
    else:
        new_id = product_id

    df.at[product_row_index, 'ID'] = new_id
    df.at[product_row_index, 'Наименование_товара'] = new_name
    df.at[product_row_index, 'Цена'] = int(price)
    df.at[product_row_index, 'Закупочная цена'] = int(cost_price)  # Обновление закупочной цены
    df.at[product_row_index, 'Описание'] = description
    df.at[product_row_index, 'Пол'] = gender
    df.at[product_row_index, 'Сезон'] = season
    df.at[product_row_index, 'Категория'] = category

    size_color_quantity_list = []
    sizes_and_quantities = {}
    for size, color, quantity in zip(sizes, colors_list, quantities):
        size = size if size else "default"
        color = color if color else "default"
        size_color_quantity_list.append(f"{size} - {color} - {quantity}")
        if size not in sizes_and_quantities:
            sizes_and_quantities[size] = {}
        sizes_and_quantities[size][color] = int(quantity)

    size_color_quantity_str = ', '.join(size_color_quantity_list)
    df.at[product_row_index, 'Размер_цвет_количество'] = size_color_quantity_str
    df.at[product_row_index, 'Размеры_и_количество'] = json.dumps(sizes_and_quantities)

    images_df = pd.read_excel(os.path.join(BASE_DIR, 'data', 'images.xlsx'), engine='openpyxl')
    images_dir = os.path.join(BASE_DIR, 'static', 'images')
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)

    # Переименование изображений, если ID изменился
    if new_id != product_id:
        for index, row in images_df[images_df['ID'] == product_id].iterrows():
            old_image_path = os.path.join(images_dir, row['Ссылка'])
            if os.path.exists(old_image_path):
                color_part = row['Цвет'] if row['Цвет'] else 'default'
                new_image_name = f"{new_id}_{color_part}.jpg"
                new_image_path = os.path.join(images_dir, new_image_name)
                os.rename(old_image_path, new_image_path)  # Переименование файла

                # Обновление ссылки в таблице
                images_df.at[index, 'Ссылка'] = new_image_name

        # Обновление ID в таблице изображений
        images_df.loc[images_df['ID'] == product_id, 'ID'] = new_id

    # Обработка новых загруженных изображений
    for temp_file_name in temp_photo_paths:
        try:
            temp_file_path = os.path.join(images_dir, temp_file_name)
            color = temp_file_name.split('_')[-1].replace('.jpg', '').strip()
            color_part = color if color else 'default'
            photo_filename = f"{new_id}_{color_part}.jpg"
            unique_photo_filename = generate_unique_filename(photo_filename, images_dir)
            unique_photo_path = os.path.join(images_dir, unique_photo_filename)

            shutil.move(temp_file_path, unique_photo_path)
            new_image = {
                'ID': new_id,
                'Ссылка': unique_photo_filename,
                'Цвет': color,
                'Позиция': len(images_df[images_df['ID'] == new_id])
            }
            images_df = pd.concat([images_df, pd.DataFrame([new_image])], ignore_index=True)
        except Exception as e:
            print(f"Ошибка при сохранении изображения: {e}")

    # Обновляем порядок изображений на основе полученного списка
    for position, photo_link in enumerate(photo_order):
        images_df.loc[images_df['Ссылка'] == photo_link, 'Позиция'] = position

    # Пересчет порядковых номеров
    df['№'] = range(1, len(df) + 1)

    # Сохранение изменений
    images_df.to_excel(os.path.join(BASE_DIR, 'data', 'images.xlsx'), index=False, engine='openpyxl')
    df.to_excel(data_path, index=False, engine='openpyxl')

    return redirect(url_for('edit_product', product_id=new_id))



@app.route('/product/<product_id>')
def product(product_id):
    product_row = df[df['ID'].astype(str) == str(product_id)]
    if product_row.empty:
        return render_template('error.html', message='Товар не найден.')
    product_row = product_row.iloc[0]

    product_data = {
        'id': str(product_row['ID']),  # Преобразование в строку
        'name': product_row['Наименование_товара'],
        'price': int(product_row['Цена']),  # Преобразование в стандартный int
        'description': product_row['Описание'],
        'sizes_and_quantities': json.loads(product_row['Размеры_и_количество']),
        'additional_info': {
            'gender': product_row['Пол'],
            'season': product_row['Сезон'],
            'category': product_row.get('Категория', 'не указано')  # Добавляем категорию
        }
    }

    # Изображения товара
    images_df = pd.read_excel(os.path.join(BASE_DIR, 'data', 'images.xlsx'), engine='openpyxl')
    product_images = images_df[images_df['ID'] == product_data['id']].to_dict('records')
    product_data['images'] = product_images

    # Уникальные цвета
    unique_colors = set()
    for size, colors in product_data['sizes_and_quantities'].items():
        for color, quantity in colors.items():
            if quantity > 0:
                if color and color != 'default':
                    unique_colors.add(color)

    # Преобразуем все значения в сериализуемые типы
    product_data = convert_to_serializable(product_data)

    # Ссылка на WhatsApp
    seller_phone = "79280544578"  # Ваш номер телефона
    product_url = url_for('product', product_id=product_data['id'],
                          _external=True)  # Генерируем URL страницы товара
    whatsapp_message = f"Здравствуйте! Я хочу купить товар: {product_data['name']} (ID: {product_data['id']}). Ссылка: {product_url}"
    whatsapp_link = f"https://wa.me/{seller_phone}?text={whatsapp_message}"

    return render_template('product.html',
                           product=product_data,
                           uniqueColors=unique_colors,
                           whatsapp_link=whatsapp_link)

@app.route('/api/product/<product_id>')
def api_product(product_id):
    try:
        product_row = df[df['ID'] == product_id].iloc[0]
        product_data = {
            'id': str(product_row['ID']),
            'name': str(product_row['Наименование_товара']),
            'price': int(product_row['Цена']),
            'description': str(product_row['Описание']),
            'sizes_and_quantities': json.loads(product_row['Размеры_и_количество']),
            'additional_info': {
                'gender': str(product_row['Пол']),
                'season': str(product_row['Сезон'])
            }
        }

        images_df = pd.read_excel(os.path.join(BASE_DIR, 'data', 'images.xlsx'), engine='openpyxl')
        product_images = images_df[images_df['ID'] == product_data['id']].to_dict('records')
        product_data['images'] = product_images

        return jsonify(product_data)  # Возвращаем JSON данные
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_product/<product_id>', methods=['POST'])
def delete_product(product_id):
    global df

    try:
        # Удаление из `baza.xlsx`
        df = df[df['ID'] != product_id]
        df.to_excel(data_path, index=False, engine='openpyxl')

        # Удаление из `images.xlsx`
        images_df = pd.read_excel(images_path, engine='openpyxl')
        product_images = images_df[images_df['ID'] == product_id]
        images_df = images_df[images_df['ID'] != product_id]
        images_df.to_excel(images_path, index=False, engine='openpyxl')

        # Удаление изображений из `static/images`
        images_dir = os.path.join(BASE_DIR, 'static', 'images')
        for _, row in product_images.iterrows():
            image_path = os.path.join(images_dir, row['Ссылка'])
            if os.path.exists(image_path):
                os.remove(image_path)

        return '', 204  # Успешный ответ
    except Exception as e:
        # Логирование ошибки
        print(f"Ошибка при удалении товара {product_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/delete_image', methods=['DELETE'])
def delete_image():
    image_path = request.args.get('image')
    image_full_path = os.path.join(BASE_DIR, 'static', 'images', image_path)

    try:
        if os.path.exists(image_full_path):
            os.remove(image_full_path)

        images_df = pd.read_excel(os.path.join(BASE_DIR, 'data', 'images.xlsx'), engine='openpyxl')
        images_df = images_df[images_df['Ссылка'] != image_path]
        images_df.to_excel(os.path.join(BASE_DIR, 'data', 'images.xlsx'), index=False, engine='openpyxl')

        return '', 204
    except Exception as e:
        print(f"Ошибка при удалении изображения: {e}")
        return '', 500


@app.route('/confirm_delete/<product_name>')
def confirm_delete(product_name):
    return render_template('confirm_delete.html', product_name=product_name)


@app.route('/edit_product/<product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    global df
    print(f"Received product ID: {product_id}")

    if isinstance(product_id, str):
        print(f"Product ID is a string: {product_id}")
    else:
        print(f"Product ID is not a string: {product_id}")

    # Проверка на загрузку данных в df
    if df.empty:
        print("DataFrame is empty!")
        return render_template('error.html', message='Ошибка загрузки данных.')

    # Приводим ID к строковому типу и ищем товар
    product_row = df[df['ID'].astype(str) == str(product_id)]

    if product_row.empty:
        print(f"Product with ID {product_id} not found in the DataFrame.")
        return render_template('error.html', message='Товар не найден.')

    product_info = product_row.iloc[0]
    sizes_and_quantities = json.loads(product_info.get('Размеры_и_количество', '{}'))

    images_df = pd.read_excel(os.path.join(BASE_DIR, 'data', 'images.xlsx'), engine='openpyxl')
    product_images = images_df[images_df['ID'] == product_info['ID']].to_dict('records')

    product_data = {
        'id': str(product_info.get('ID', 'не указано')),
        'name': str(product_info.get('Наименование_товара', 'не указано')),
        'price': product_info.get('Цена', 'не указано'),
        'description': str(product_info.get('Описание', 'не указано')),
        'cost_price': product_info.get('Закупочная цена', 'не указано'),
        'sizes_and_quantities': sizes_and_quantities,
        'additional_info': {
            'gender': product_info.get('Пол', 'не указано'),
            'season': product_info.get('Сезон', 'не указано'),
            'category': product_info.get('Категория', 'не указано')
        },
        'images': product_images
    }

    if request.method == 'POST':
        data = request.form
        new_name = data.get('name')
        print(f"Новое имя из формы: {new_name}")

        # Проверка на дублирование имен
        if not df[df['Наименование_товара'].str.strip() == new_name.strip()].empty:
            return render_template('error.html', message='Товар с таким наименованием уже существует.')

        product_row_index = df[df['ID'] == product_id].index[0]
        print(f"Старое наименование: {product_info['Наименование_товара']}, Новое наименование: {new_name}")

        sizes_and_quantities = {}
        for size, color, quantity in zip(data.getlist('sizes[]'), data.getlist('colors[]'), data.getlist('quantities[]')):
            if not size:
                size = 'default'
            if not color:
                color = 'default'
            sizes_and_quantities[size] = {color: int(quantity)}

        # Обновление DataFrame
        df.at[product_row_index, 'Цена'] = int(data['price'])
        df.at[product_row_index, 'Описание'] = str(data['description'])
        df.at[product_row_index, 'Наименование_товара'] = new_name
        df.at[product_row_index, 'Размеры_и_количество'] = json.dumps(sizes_and_quantities)
        df.at[product_row_index, 'Пол'] = str(data['gender'])
        df.at[product_row_index, 'Сезон'] = str(data['season'])
        df.at[product_row_index, 'Категория'] = str(data['category'])
        df.at[product_row_index, 'Закупочная цена'] = int(data['cost_price'])  # Обновление закупочной цены

        print(f"Обновленный DataFrame перед сохранением: {df.iloc[product_row_index]}")

        try:
            df.to_excel(data_path, index=False, engine='openpyxl')
            print(f"Файл Excel успешно сохранен по пути: {data_path}")
        except Exception as e:
            print(f"Ошибка при сохранении файла Excel: {e}")

        try:
            df = pd.read_excel(data_path, engine='openpyxl')
            print(f"Перезагруженный DataFrame: {df[df['ID'] == product_id]}")
        except Exception as e:
            print(f"Ошибка при перезагрузке файла Excel: {e}")

        return redirect(url_for('edit_product', product_id=product_id))

    return render_template('edit_product.html', product=product_data)

@app.route('/add_product', methods=['GET'])
def add_product():
    empty_product_data = {
        'id': '',
        'name': '',
        'price': '',
        'description': '',
        'sizes_and_quantities': {},
        'additional_info': {
            'gender': '',
            'season': '',
            'category': ''
        },
        'images': []
    }
    return render_template('add_product.html', product=empty_product_data)

# Проверяем существование sales.xlsx, создаем его, если отсутствует
if not os.path.exists(sales_path):
    pd.DataFrame(columns=['Дата', 'Наименование', 'Размер', 'Цвет', 'Количество', 'Цена']).to_excel(sales_path, index=False, engine='openpyxl')

@app.route('/confirm_sell', methods=['POST'])
def confirm_sell():
    global df

    # Получаем данные из запроса
    product_id = request.form.get('id')  # Используем ID товара как строку
    size = request.form.get('size')
    color = request.form.get('color')
    quantity = int(request.form.get('quantity'))
    price = float(request.form.get('price'))

    if quantity <= 0:
        return jsonify({'error': 'Количество должно быть больше нуля.'}), 400

    # Поиск товара в базе по ID
    product_row = df[df['ID'].astype(str) == str(product_id)]
    if product_row.empty:
        return jsonify({'error': 'Товар не найден.'}), 404

    product_row = product_row.iloc[0]
    sizes_and_quantities = json.loads(product_row['Размеры_и_количество'])

    # Проверяем наличие размера и цвета
    if size not in sizes_and_quantities or color not in sizes_and_quantities[size]:
        return jsonify({'error': 'Выбранный размер или цвет отсутствует.'}), 400

    available_quantity = sizes_and_quantities[size][color]
    if quantity > available_quantity:
        return jsonify({'error': f'Недостаточно товара на складе. Доступно: {available_quantity} шт.'}), 400

    # Обновляем количество
    sizes_and_quantities[size][color] -= quantity
    if sizes_and_quantities[size][color] == 0:
        del sizes_and_quantities[size][color]
    if not sizes_and_quantities[size]:
        del sizes_and_quantities[size]

    df.loc[df['ID'] == product_id, 'Размеры_и_количество'] = json.dumps(sizes_and_quantities)
    df.to_excel(data_path, index=False, engine='openpyxl')

    # Добавляем запись о продаже в sales.xlsx
    sales_df = pd.read_excel(sales_path, engine='openpyxl')
    cost_price = product_row['Закупочная цена']  # Получаем закупочную цену из исходной таблицы

    new_sale = {
        'Дата': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'Наименование': product_row['Наименование_товара'],
        'Размер': size,
        'Цвет': color,
        'Количество': quantity,
        'Цена': price,
        'Закупочная цена': cost_price  # Добавляем закупочную цену
    }

    sales_df = pd.concat([sales_df, pd.DataFrame([new_sale])], ignore_index=True)
    sales_df.to_excel(sales_path, index=False, engine='openpyxl')

    return jsonify({'success': 'Продажа успешно зарегистрирована.'}), 200


@app.route('/save_new_product', methods=['POST'])
def save_new_product():
    global df

    new_name = request.form.get('name')
    price = request.form.get('price')
    cost_price = request.form.get('cost_price')
    description = request.form.get('description')
    gender = request.form.get('gender')
    season = request.form.get('season')
    category = request.form.get('category')
    sizes = request.form.getlist('sizes[]')
    colors_list = request.form.getlist('colors[]')
    quantities = request.form.getlist('quantities[]')
    temp_photo_paths = json.loads(request.form.get('temp_photo_paths', '[]'))
    photo_order = json.loads(request.form.get('photo_order', '[]'))

    # Заменяем пустые значения цветов на 'default'
    for i in range(len(colors_list)):
        if not colors_list[i] or colors_list[i].lower() == 'null' or colors_list[i] == '':
            colors_list[i] = 'default'

    # Заменяем пустые значения размеров на 'default'
    for i in range(len(sizes)):
        if not sizes[i] or sizes[i].lower() == 'null' or sizes[i] == '':
            sizes[i] = 'default'

    new_id = generate_unique_id(category, new_name, gender)

    sizes_and_quantities = {}
    for size, color, quantity in zip(sizes, colors_list, quantities):
        if not size or size.lower() == 'null':
            size = 'default'
        if not color or color.lower() == 'null':
            color = 'default'

        if size not in sizes_and_quantities:
            sizes_and_quantities[size] = {}
        if color not in sizes_and_quantities[size]:
            sizes_and_quantities[size][color] = 0
        sizes_and_quantities[size][color] += int(quantity)

    size_color_quantity_str = ', '.join(
        f"{size} - {color} - {quantity}"
        for size, colors in sizes_and_quantities.items()
        for color, quantity in colors.items()
    )

    new_row = {
        'ID': new_id,
        'Наименование_товара': new_name,
        'Цена': int(price),
        'Закупочная цена': int(cost_price),
        'Описание': description,
        'Пол': gender,
        'Сезон': season,
        'Категория': category,
        'Размеры_и_количество': json.dumps(sizes_and_quantities),
        'Размер_цвет_количество': size_color_quantity_str
    }

    df = df._append(new_row, ignore_index=True)
    df['№'] = range(1, len(df) + 1)

    images_df = pd.read_excel(os.path.join(BASE_DIR, 'data', 'images.xlsx'), engine='openpyxl')
    images_dir = os.path.join(BASE_DIR, 'static', 'images')
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)

    for temp_file_name in temp_photo_paths:
        try:
            temp_file_path = os.path.join(images_dir, temp_file_name)
            color = temp_file_name.split('_')[-1].replace('.jpg', '').strip()
            if not color or color.lower() == 'null':
                color = 'default'
            photo_filename = f"{new_id}_{color}.jpg"
            unique_photo_filename = generate_unique_filename(photo_filename, images_dir)
            unique_photo_path = os.path.join(images_dir, unique_photo_filename)

            if os.path.exists(temp_file_path):
                shutil.move(temp_file_path, unique_photo_path)
                position = temp_photo_paths.index(temp_file_name)
                new_image = {
                    'ID': new_id,
                    'Ссылка': unique_photo_filename,
                    'Цвет': color,
                    'Позиция': position
                }
                images_df = pd.concat([images_df, pd.DataFrame([new_image])], ignore_index=True)
            else:
                print(f"Файл не найден: {temp_file_path}")
        except Exception as e:
            print(f"Ошибка при сохранении изображения: {e}")

    images_df.to_excel(os.path.join(BASE_DIR, 'data', 'images.xlsx'), index=False, engine='openpyxl')
    df.to_excel(data_path, index=False, engine='openpyxl')
    print("DataFrame after saving to Excel:", df.head())  # Вывод для отладки
    return redirect(url_for('index'))


def load_data_from_excel():
    df = pd.read_excel(data_path, engine='openpyxl')
    for index, row in df.iterrows():
        sizes_and_quantities = json.loads(row.get('Размеры_и_количество', '{}'))
        print(f"Original sizes_and_quantities, row {index}: {sizes_and_quantities}")

        corrected_sizes_and_quantities = {}
        for size, colors in sizes_and_quantities.items():
            if not size or size.lower() == 'null' or size == '':
                corrected_size = 'default'
            else:
                corrected_size = size

            if corrected_size not in corrected_sizes_and_quantities:
                corrected_sizes_and_quantities[corrected_size] = {}

            for color, quantity in colors.items():
                if not color or color.lower() == 'null' or color == '':
                    corrected_color = 'default'
                else:
                    corrected_color = color
                corrected_sizes_and_quantities[corrected_size][corrected_color] = quantity

        df.at[index, 'Размеры_и_количество'] = json.dumps(corrected_sizes_and_quantities)
        print(f"Corrected sizes_and_quantities, row {index}: {corrected_sizes_and_quantities}")
    print("DataFrame after loading and correction:\n", df.head())
    return df

df = load_data_from_excel()


@app.route('/all_products')
def all_products():
    df = pd.read_excel(data_path, engine='openpyxl')

    # Вычисление сводной информации
    total_varieties = len(df)

    def parse_sizes(x):
        if pd.isna(x):
            return 0
        if isinstance(x, str):
            sizes = json.loads(x)
        elif isinstance(x, dict):
            sizes = x
        else:
            return 0
        return sum(sum(colors.values()) for colors in sizes.values())

    total_quantity = df['Размеры_и_количество'].apply(parse_sizes).sum()
    total_by_category = df['Категория'].value_counts().to_dict()
    total_cost_price = df['Закупочная цена'].sum()
    total_price = df['Цена'].sum()

    summary = {
        'total_varieties': total_varieties,
        'total_quantity': total_quantity,
        'total_by_category': total_by_category,
        'total_cost_price': total_cost_price,
        'total_price': total_price
    }

    return render_template('all_products.html', summary=summary, data=df.to_dict(orient='records'))


@app.route('/download_excel', methods=['POST'])
def download_excel():
    df = pd.read_excel(data_path, engine='openpyxl')
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    return send_file(output, download_name='baza.xlsx', as_attachment=True)


@app.route('/sales_report', methods=['GET', 'POST'])
def sales_report():
    # Загрузка данных из sales.xlsx
    sales_df = pd.read_excel(sales_path, engine='openpyxl')

    # Фильтр по диапазону дат, если есть POST-запрос
    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            sales_df = sales_df[sales_df['Дата'] >= start_date.strftime('%Y-%m-%d')]
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            sales_df = sales_df[sales_df['Дата'] <= end_date.strftime('%Y-%m-%d %H:%M:%S')]

    # Вычисление сводной информации
    total_cost_price = (sales_df['Закупочная цена'] * sales_df['Количество']).sum()
    total_sale_price = (sales_df['Цена'] * sales_df['Количество']).sum()
    total_revenue = total_sale_price - total_cost_price

    summary = {
        'total_cost_price': total_cost_price,
        'total_sale_price': total_sale_price,
        'total_revenue': total_revenue
    }

    return render_template('sales_report.html', summary=summary, data=sales_df.to_dict(orient='records'), start_date=request.form.get('start_date'), end_date=request.form.get('end_date'))

@app.route('/download_sales_excel', methods=['POST'])
def download_sales_excel():
    sales_df = pd.read_excel(sales_path, engine='openpyxl')

    # Фильтр по диапазону дат, если есть POST-запрос
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')

    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        sales_df = sales_df[sales_df['Дата'] >= start_date.strftime('%Y-%m-%d')]
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
        sales_df = sales_df[sales_df['Дата'] <= end_date.strftime('%Y-%m-%d %H:%M:%S')]

    output = BytesIO()
    sales_df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    return send_file(output, download_name='filtered_sales.xlsx', as_attachment=True)


if __name__ == '__main__':
    # Получаем порт из переменной окружения или используем 5000 по умолчанию
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

#from werkzeug.security import generate_password_hash
#print(generate_password_hash("ваш_пароль"))
