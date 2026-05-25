# Памятка: Установка и настройка NUT + Web GUI (ИБП Ritar RTSW 1500)

## 1. Установка базовых компонентов
Устанавливаем сервер мониторинга NUT:
```bash
sudo apt update
sudo apt install nut -y
```

## 2. Настройка NUT (/etc/nut/)

**Файл `/etc/nut/nut.conf`**:
Определяет режим работы.
```ini
MODE=standalone
```

**Файл `/etc/nut/ups.conf`**:
Конфигурация драйвера ИБП с поправкой на LiFePO4 батареи. 
```ini
[ritar]
    driver = nutdrv_qx
    port = /dev/ttyUSB0
    desc = "Ritar RTSW 1500"
    
    # Игнорировать "железный" статус разряда батареи от ИБП (настроенный на свинец)
    ignorelb
    
    # Задаем рабочее окно напряжений (для 24V LiFePO4 сборки)
    default.battery.voltage.high = 27.2
    default.battery.voltage.low = 25.8
    
    # Триггер экстренного выключения: при 15% расчетного заряда (около 26.0V)
    override.battery.charge.low = 15
```

## 3. Права доступа
Драйверу `nut` нужен доступ к USB-порту. Добавляем пользователя `nut` в группу `dialout`:
```bash
sudo usermod -a -G dialout nut
```

Перезапускаем службу NUT, чтобы подхватить изменения:
```bash
sudo systemctl restart nut-server nut-client nut-driver@ritar
```

*(Проверить, что ИБП отвечает: `upsc ritar`)*

---

## 4. Настройка Web GUI

1. Скопируй скрипт веб-интерфейса `ups_gui.py` и картинку `ups.png` в домашнюю папку пользователя (например, `/home/mge_engineer/`).
2. Сделай скрипт исполняемым:
   ```bash
   chmod +x /home/mge_engineer/ups_gui.py
   ```

## 5. Автозапуск Web GUI через systemd

Создай файл службы **`/etc/systemd/system/ups_gui.service`**:
```ini
[Unit]
Description=Modern UPS Web GUI (Port 9009)
After=network.target nut-server.service

[Service]
Type=simple
User=mge_engineer
ExecStart=/usr/bin/python3 /home/mge_engineer/ups_gui.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Перезагрузи демоны и запусти Web GUI:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ups_gui.service
```

**Готово!** Интерфейс доступен по адресу: `http://localhost:9009`
