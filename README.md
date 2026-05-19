# 1. Actualizar sistema
sudo apt update && sudo apt upgrade -y

# 2. Instalar Python 3 y pip
sudo apt install python3 python3-pip python3-venv -y

# 3. Instalar Node.js y pm2
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs -y
sudo npm install -g pm2

# 4. Clonar el bot
git clone https://github.com/HacheJotaDev/BotUlp.git
cd BotUlp

# 5. Crear entorno virtual e instalar dependencias
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 6. Iniciar el bot con pm2
pm2 start "venv/bin/python3 bot.py" --name ulp-bot

# 7. Guardar pm2 para que sobreviva reinicios
pm2 save
pm2 startup
