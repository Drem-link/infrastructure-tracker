# Клонируешь репозиторий
git clone https://github.com/Drem-link/infrastructure-tracker.git tracker_app
cd tracker_app

# Создаешь чистый файл базы данных с правильными правами
touch tracker.db
chmod 666 tracker.db

# Запускаешь контейнер
sudo docker compose up -d --build
