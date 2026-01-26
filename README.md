# KPI Communication Bot

Бот для комунікації орагнів студентського самоврядування Національного технічного університету України "Київський політехнічний інститут імені Ігоря Сікорського".

Основні можливості:

* Зворотній зв'язок.
* Відправка повідомлень між чатами Студрад.
* Комунікація між студрадами.
* Розсилка старостам та академічним групам.

Гайд на бота: <https://docs.google.com/document/d/1cQq8kjiQ21phNy0CUB9gYfMp2-Myo9CjxNG7IypT3WU/edit?tab=t.0>

Докер контейнер: <https://hub.docker.com/repository/docker/maximax67/kpi-communication-bot>

## Гайд розробнику

Програмний код написано на Python, не тестувалось на інших версіях окрім 3.12.

1. Cклонуйте репозиторій:

    ```bash
    git clone https://github.com/Maximax67/kpi-communication-bot
    ```

2. Встановіть залежності:

    ```bash
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    ```

3. Створіть .env файл та заповність його за прикладом в .env.example.
4. Підготуйте базу даних:

    ```bash
    alembic revision --autogenerate -m "create initial tables"
    alembic upgrade head
    ```

5. Запустіть застосунок:

    ```bash
    fastapi dev app/main.py
    ```

## Зворотній зв'язок

* Пошта: [maximax6767@gmail.com](mailto:maximax6767@gmail.com)
* Телеграм: [@Maximax67](https://t.me/Maximax67)
* Бот Студради ФІОТ: [@fice_robot](https://t.me/fice_robot)

## Ліцензія

Цей проєкт ліцензовано за умовами **MIT License**. Деталі можна переглянути у файлі [LICENSE](LICENSE).
