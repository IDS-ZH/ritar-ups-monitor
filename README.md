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
Конфигурация драйвера ИБП с поправкой на LiFePO4 батареи. Используем постоянный путь `by-id`, чтобы избежать проблем при перетыкании USB-кабеля в другие порты.
```ini
[ritar]
    driver = nutdrv_qx
    port = /dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_D-if00-port0
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

## 4. Настройка Web GUI & Базы данных статистики

1. Скрипт веб-интерфейса `ups_gui.py` содержит встроенный фоновый коллектор данных. Каждые 30 секунд он автоматически опрашивает NUT и складывает статистику в локальную базу данных SQLite `/home/mge_engineer/ups_history.db`.
2. База данных содержит следующие метрики:
   * Время замера (UNIX timestamp)
   * Статус ИБП (OL — Сеть, OB — Батарея)
   * Уровень заряда (%)
   * Напряжение батареи (V)
   * Входное и выходное напряжение (V) (для отслеживания работы AVR)
   * Нагрузку на ИБП (%)
   * Температуру ИБП (°C)
3. Скопируй скрипт веб-интерфейса `ups_gui.py` и картинку `ups.png` в домашнюю папку пользователя (например, `/home/mge_engineer/`).
4. Сделай скрипт исполняемым:
   ```bash
   chmod +x /home/mge_engineer/ups_gui.py
   ```

## 5. Автозапуск Web GUI через systemd

Создай файл службы **`/etc/systemd/system/ups_gui.service`**:
```ini
[Unit]
Description=Modern UPS Web GUI and Logger (Port 9009)
# Жесткая привязка к NUT. Если nut-server останавливается, GUI тоже остановится.
BindsTo=nut-server.service
After=network.target nut-server.service

[Service]
Type=simple
User=mge_engineer
ExecStart=/usr/bin/python3 /home/mge_engineer/ups_gui.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Перезагрузи демоны и запусти Web GUI:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ups_gui.service
```

## 6. Возможности интерфейса (доступен на http://localhost:9009)
Сайт представляет собой Single Page Application (SPA), который отлично отображается как на ПК, так и на мобильных устройствах. Включает 3 вкладки:
1. **Мониторинг** — дашборд с текущими показателями в реальном времени (напряжение входа/выхода, нагрузка, заряд LiFePO4, температура, частота сети).
2. **История и Графики** — интерактивные графики Chart.js, показывающие периоды отключения электричества (Сеть vs Батарея), а также графики входного и выходного напряжения (для контроля AVR). Разрывы в логах (когда ПК был выключен) корректно обрабатываются и отображаются как пустое окно на графике.
3. **Нагрузка и Температура** — детальные графики потребления нагрузки на ИБП (в %) и нагрева компонентов ИБП (в °C).
