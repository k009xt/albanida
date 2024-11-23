import os
import shutil
import tempfile
from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import json
import time
from flask import request, jsonify
from datetime import datetime
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
import json
from werkzeug.security import check_password_hash

app = Flask(__name__, static_url_path='/static')
app.secret_key = os.urandom(24)  # Секретный ключ для сессий

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(BASE_DIR, 'data/baza.xlsx')
sales_path = os.path.join(BASE_DIR, 'data/sales.xlsx')
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
        'серый': 'gray'
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
        print(f"Получен файл: {photo.filename}, Выбранный цвет: {selected_color}, ID товара: {product_id}")
        try:
            images_dir = os.path.join(BASE_DIR, 'static', 'images')
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)

            temp_file_name = f"{product_id}_{selected_color}.jpg"
            temp_file_path = os.path.join(images_dir, temp_file_name)
            photo.save(temp_file_path)
            print(f"Временное изображение сохранено по пути: {temp_file_path}, Привязка к цвету: {selected_color}")
            return {"temp_photo_path": temp_file_name}, 200
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
    df.at[product_row_index, 'Описание'] = description
    df.at[product_row_index, 'Пол'] = gender
    df.at[product_row_index, 'Сезон'] = season
    df.at[product_row_index, 'Категория'] = category

    size_color_quantity_list = []
    sizes_and_quantities = {}
    for size, color, quantity in zip(sizes, colors_list, quantities):
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

    # Обновляем ID для изображений, если новый ID отличается от старого
    if new_id != product_id:
        images_df.loc[images_df['ID'] == product_id, 'ID'] = new_id

    # Обновляем порядок изображений на основе полученного списка
    for position, photo_link in enumerate(photo_order):
        images_df.loc[images_df['Ссылка'] == photo_link, 'Позиция'] = position

    images_df.to_excel(os.path.join(BASE_DIR, 'data', 'images.xlsx'), index=False, engine='openpyxl')
    df.to_excel(data_path, index=False, engine='openpyxl')
    return redirect(url_for('edit_product', product_name=new_name))

@app.route('/product/<product_id>')
def product(product_id):
    product_row = df[df['ID'] == product_id]
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

    # Ссылка на WhatsApp
    seller_phone = "79280544578"  # Ваш номер телефона
    whatsapp_message = f"Здравствуйте! Я хочу купить товар: {product_data['name']} (ID: {product_data['id']})."
    whatsapp_link = f"https://wa.me/{seller_phone}?text={whatsapp_message}"

    return render_template('product.html',
                           product=product_data,
                           uniqueColors=unique_colors,
                           whatsapp_link=whatsapp_link)


@app.route('/api/product/<product_name>')
def api_product(product_name):
    try:
        product_row = df[df['Наименование_товара'] == product_name].iloc[0]
        product_data = {
            'id': str(product_row['ID']),
            'name': product_row['Наименование_товара'],
            'price': int(product_row['Цена']),
            'description': product_row['Описание'],
            'sizes_and_quantities': json.loads(product_row['Размеры_и_количество']),
            'additional_info': {
                'gender': product_row['Пол'],
                'season': product_row['Сезон']
            }
        }

        images_df = pd.read_excel(os.path.join(BASE_DIR, 'data', 'images.xlsx'), engine='openpyxl')
        product_images = images_df[images_df['ID'] == product_data['id']].to_dict('records')
        product_data['images'] = product_images

        return jsonify(product_data)  # Возвращаем JSON данные
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_product/<product_name>', methods=['POST'])
def delete_product(product_name):
    global df
    df = df[df['Наименование_товара'].str.strip() != product_name.strip()]
    df.to_excel(data_path, index=False, engine='openpyxl')
    return redirect(url_for('index'))

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

@app.route('/edit_product/<product_name>', methods=['GET', 'POST'])
def edit_product(product_name):
    global df

    # Загрузка строки продукта на основе имени
    product_row = df[df['Наименование_товара'].str.strip() == product_name.strip()]
    if product_row.empty:
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
        'sizes_and_quantities': sizes_and_quantities,
        'additional_info': {
            'gender': product_info.get('Пол', 'не указано'),
            'season': product_info.get('Сезон', 'не указано'),
            'category': product_info.get('Категория', 'не указано')  # Добавляем категорию
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

        product_row_index = df[df['Наименование_товара'].str.strip() == product_name.strip()].index[0]
        print(f"Старое наименование: {product_name}, Новое наименование: {new_name}")

        sizes_and_quantities = {}
        for size, color, quantity in zip(data.getlist('sizes[]'), data.getlist('colors[]'), data.getlist('quantities[]')):
            sizes_and_quantities[size] = {color: int(quantity)}

        # Обновление DataFrame
        df.at[product_row_index, 'Цена'] = int(data['price'])
        df.at[product_row_index, 'Описание'] = str(data['description'])
        df.at[product_row_index, 'Наименование_товара'] = new_name
        df.at[product_row_index, 'Размеры_и_количество'] = json.dumps(sizes_and_quantities)
        df.at[product_row_index, 'Пол'] = str(data['gender'])
        df.at[product_row_index, 'Сезон'] = str(data['season'])
        df.at[product_row_index, 'Категория'] = str(data['category'])  # Добавляем обновление категории

        print(f"Обновленный DataFrame перед сохранением: {df.iloc[product_row_index]}")

        try:
            df.to_excel(data_path, index=False, engine='openpyxl')
            print(f"Файл Excel успешно сохранен по пути: {data_path}")
        except Exception as e:
            print(f"Ошибка при сохранении файла Excel: {e}")

        try:
            df = pd.read_excel(data_path, engine='openpyxl')
            print(f"Перезагруженный DataFrame: {df[df['Наименование_товара'].str.strip() == new_name.strip()]}")
        except Exception as e:
            print(f"Ошибка при перезагрузке файла Excel: {e}")

        return redirect(url_for('edit_product', product_name=new_name))

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
    product_name = request.form.get('name')
    size = request.form.get('size')
    color = request.form.get('color')
    quantity = int(request.form.get('quantity'))
    price = float(request.form.get('price'))

    if quantity <= 0:
        return jsonify({'error': 'Количество должно быть больше нуля.'}), 400

    # Поиск товара в базе
    product_row = df[df['Наименование_товара'] == product_name]
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

    df.loc[df['Наименование_товара'] == product_name, 'Размеры_и_количество'] = json.dumps(sizes_and_quantities)
    df.to_excel(data_path, index=False, engine='openpyxl')

    # Добавляем запись о продаже в sales.xlsx
    sales_df = pd.read_excel(sales_path, engine='openpyxl')
    new_sale = {
        'Дата': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'Наименование': product_name,
        'Размер': size,
        'Цвет': color,
        'Количество': quantity,
        'Цена': price
    }
    sales_df = pd.concat([sales_df, pd.DataFrame([new_sale])], ignore_index=True)
    sales_df.to_excel(sales_path, index=False, engine='openpyxl')

    return jsonify({'success': 'Продажа успешно зарегистрирована.'}), 200

@app.route('/save_new_product', methods=['POST'])
def save_new_product():
    global df  # Объявляем переменную df глобальной

    # Получение данных из формы
    new_name = request.form.get('name')
    price = request.form.get('price')
    description = request.form.get('description')
    gender = request.form.get('gender')
    season = request.form.get('season')
    category = request.form.get('category')
    sizes = request.form.getlist('sizes[]')
    colors_list = request.form.getlist('colors[]')
    quantities = request.form.getlist('quantities[]')
    temp_photo_paths = json.loads(request.form.get('temp_photo_paths', '[]'))
    photo_order = json.loads(request.form.get('photo_order', '[]'))

    # Генерация нового уникального ID для нового товара
    new_id = generate_unique_id(category, new_name, gender)

    # Добавление новой строки в DataFrame
    new_row = {
        'ID': new_id,
        'Наименование_товара': new_name,
        'Цена': int(price),
        'Описание': description,
        'Пол': gender,
        'Сезон': season,
        'Категория': category,
        'Размеры_и_количество': json.dumps({
            size: {color: int(quantity) for color, quantity in zip(colors_list, quantities) if color and quantity}
        }),
        'Размер_цвет_количество': ', '.join(
            f"{size} - {color} - {quantity}" for size, color, quantity in zip(sizes, colors_list, quantities))
    }

    df = df._append(new_row, ignore_index=True)  # Используем _append вместо append

    # Сохранение изображений
    images_df = pd.read_excel(os.path.join(BASE_DIR, 'data', 'images.xlsx'), engine='openpyxl')
    images_dir = os.path.join(BASE_DIR, 'static', 'images')
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)

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
                'Позиция': len(images_df[images_df['ID'] == new_id])  # Устанавливаем позицию для нового фото
            }
            images_df = pd.concat([images_df, pd.DataFrame([new_image])], ignore_index=True)
        except Exception as e:
            print(f"Ошибка при сохранении изображения: {e}")

    # Обновление DataFrame с изображениями и основным DataFrame
    images_df.to_excel(os.path.join(BASE_DIR, 'data', 'images.xlsx'), index=False, engine='openpyxl')
    df.to_excel(data_path, index=False, engine='openpyxl')

    return redirect(url_for('index'))  # Перенаправление на главную страницу


if __name__ == '__main__':
    # Получаем порт из переменной окружения или используем 5000 по умолчанию
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

#from werkzeug.security import generate_password_hash
#print(generate_password_hash("ваш_пароль"))
