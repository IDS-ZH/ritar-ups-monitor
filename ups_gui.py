#!/usr/bin/env python3
import http.server
import socketserver
import subprocess
import json
import sqlite3
import threading
import time
from urllib.parse import urlparse, parse_qs
from datetime import datetime

PORT = 9009
DB_PATH = '/home/mge_engineer/ups_history.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS ups_log (
                    timestamp INTEGER PRIMARY KEY,
                    status TEXT,
                    charge REAL,
                    voltage REAL,
                    load REAL,
                    in_volt REAL
                )''')
    try:
        c.execute('ALTER TABLE ups_log ADD COLUMN out_volt REAL DEFAULT 0')
    except:
        pass
    try:
        c.execute('ALTER TABLE ups_log ADD COLUMN temperature REAL DEFAULT 0')
    except:
        pass
    conn.commit()
    conn.close()

def log_data_loop():
    # Ждем пару секунд перед стартом, чтобы NUT точно поднялся
    time.sleep(2)
    while True:
        try:
            output = subprocess.check_output(['upsc', 'ritar'], stderr=subprocess.STDOUT).decode('utf-8')
            data = {}
            for line in output.split('\n'):
                if ':' in line:
                    k, v = line.split(':', 1)
                    data[k.strip()] = v.strip()
            
            status = data.get('ups.status', '')
            if status:
                charge = float(data.get('battery.charge', 0))
                voltage = float(data.get('battery.voltage', 0))
                load = float(data.get('ups.load', 0))
                in_volt = float(data.get('input.voltage', 0))
                out_volt = float(data.get('output.voltage', 0))
                temp = float(data.get('ups.temperature', 0))
                
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO ups_log (timestamp, status, charge, voltage, load, in_volt, out_volt, temperature) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                          (int(time.time()), status, charge, voltage, load, in_volt, out_volt, temp))
                conn.commit()
                conn.close()
        except Exception:
            pass # Если NUT упал, процесс просто не пишет в БД (будет "пустое окно")
        
        time.sleep(30)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ritar RTSW 1500 Status</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;500;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.7);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-blue: #3b82f6;
        }
        body {
            margin: 0; padding: 2rem;
            background: linear-gradient(135deg, #020617 0%, #0f172a 100%);
            color: var(--text-main);
            font-family: 'Outfit', sans-serif;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .header {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-bottom: 2rem;
        }
        .ups-image {
            max-height: 250px;
            margin-bottom: 1.5rem;
            border-radius: 20px;
            filter: drop-shadow(0 0 25px rgba(56, 189, 248, 0.2));
            animation: float 6s ease-in-out infinite;
        }
        @keyframes float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
            100% { transform: translateY(0px); }
        }
        h1 {
            font-weight: 700;
            background: -webkit-linear-gradient(45deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0;
            margin-bottom: 1rem;
        }
        .tabs {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
            background: rgba(255, 255, 255, 0.05);
            padding: 0.5rem;
            border-radius: 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .tab-btn {
            background: transparent;
            color: var(--text-muted);
            border: none;
            padding: 0.5rem 1.5rem;
            border-radius: 20px;
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s;
        }
        .tab-btn.active {
            background: var(--accent-blue);
            color: #fff;
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.5);
        }
        .dashboard, .stats-view {
            width: 100%;
            max-width: 900px;
        }
        .stats-view {
            display: none;
        }
        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
        }
        .card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 1.5rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .label {
            font-size: 0.9rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.5rem;
        }
        .value {
            font-size: 2.5rem;
            font-weight: 700;
            display: flex;
            align-items: baseline;
            gap: 0.5rem;
        }
        .unit {
            font-size: 1.2rem;
            color: var(--text-muted);
        }
        .progress-bar {
            width: 100%;
            height: 12px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 10px;
            margin-top: 1rem;
            overflow: hidden;
            position: relative;
        }
        .progress-fill {
            height: 100%;
            background: var(--accent-green);
            width: 0%;
            border-radius: 10px;
            transition: width 1s ease-in-out, background-color 0.5s ease;
            box-shadow: 0 0 15px var(--accent-green);
        }
        .status-badge {
            display: inline-block;
            padding: 0.5rem 1.2rem;
            border-radius: 30px;
            font-weight: 500;
            background: rgba(16, 185, 129, 0.2);
            color: var(--accent-green);
            border: 1px solid var(--accent-green);
            margin-bottom: 2rem;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
            100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }
        .error { color: var(--accent-red); }
        .chart-container {
            position: relative;
            height: 400px;
            width: 100%;
        }
        .date-picker {
            background: rgba(0,0,0,0.2);
            border: 1px solid rgba(255,255,255,0.2);
            color: #fff;
            padding: 0.5rem;
            border-radius: 8px;
            font-family: inherit;
            margin-bottom: 1rem;
        }
    </style>
</head>
<body>
    <div class="header">
        <img src="/ups.png" alt="Ritar Schematic" class="ups-image">
        <h1>Ritar RTSW 1500</h1>
        
        <div class="tabs" style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; width: 100%; max-width: 900px; padding: 0.5rem; background: rgba(255, 255, 255, 0.05); border-radius: 30px; border: 1px solid rgba(255, 255, 255, 0.1); margin-bottom: 2rem; gap: 1rem;">
            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                <button class="tab-btn active" onclick="switchTab('dashboard')">Мониторинг</button>
                <button class="tab-btn" onclick="switchTab('stats')">История и Графики</button>
                <button class="tab-btn" onclick="switchTab('load_stats')">Нагрузка и Температура</button>
                <button class="tab-btn" onclick="switchTab('battery_stats')">Батарея</button>
            </div>
            <input type="date" id="datePicker" class="date-picker" style="margin-bottom: 0;" onchange="loadStats()">
        </div>

        <div id="statusBadge" class="status-badge">Загрузка данных...</div>
    </div>
    
    <div id="dashboard" class="dashboard">
        <div class="card">
            <div class="label">Заряд батареи (LiFePO4)</div>
            <div class="value"><span id="battCharge">--</span><span class="unit">%</span></div>
            <div class="progress-bar"><div id="battProgress" class="progress-fill"></div></div>
            <div class="label" style="margin-top: 1.5rem;">Текущее Напряжение</div>
            <div class="value" style="font-size: 1.8rem; color: var(--accent-blue);"><span id="battVolt">--</span><span class="unit">V</span></div>
        </div>
        <div class="card">
            <div class="label">Нагрузка</div>
            <div class="value"><span id="load">--</span><span class="unit">%</span></div>
            <div class="progress-bar"><div id="loadProgress" class="progress-fill" style="background: var(--accent-blue); box-shadow: 0 0 15px var(--accent-blue);"></div></div>
        </div>
        <div class="card">
            <div class="label">Входное напряжение</div>
            <div class="value"><span id="inVolt">--</span><span class="unit">V</span></div>
        </div>
        <div class="card">
            <div class="label">Выходное напряжение</div>
            <div class="value"><span id="outVolt">--</span><span class="unit">V</span></div>
        </div>
        <div class="card">
            <div class="label">Температура ИБП</div>
            <div class="value"><span id="upsTemp">--</span><span class="unit">°C</span></div>
        </div>
        <div class="card">
            <div class="label">Входная частота</div>
            <div class="value"><span id="inFreq">--</span><span class="unit">Hz</span></div>
        </div>
    </div>

    <div id="stats" class="stats-view card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <div class="label">График работы (Сеть vs Батарея)</div>
        </div>
        <div class="chart-container">
            <canvas id="historyChart"></canvas>
        </div>
    </div>

    <div id="load_stats" class="stats-view card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <div class="label">Нагрузка на ИБП (%)</div>
        </div>
        <div class="chart-container" style="margin-bottom: 2rem;">
            <canvas id="loadChart"></canvas>
        </div>
        
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 1.5rem;">
            <div class="label">Температура ИБП (°C)</div>
        </div>
        <div class="chart-container">
            <canvas id="tempChart"></canvas>
        </div>
    </div>

    <div id="battery_stats" class="stats-view card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <div class="label">Напряжение аккумулятора (V)</div>
        </div>
        <div class="chart-container" style="margin-bottom: 2rem;">
            <canvas id="battVoltChart"></canvas>
        </div>
        
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 1.5rem;">
            <div class="label">Заряд аккумулятора (%)</div>
        </div>
        <div class="chart-container">
            <canvas id="battChargeChart"></canvas>
        </div>
    </div>

    <script>
        let currentTab = 'dashboard';
        let chartInstance = null;
        let loadChartInstance = null;
        let tempChartInstance = null;
        let battVoltChartInstance = null;
        let battChargeChartInstance = null;

        // Установим сегодняшнюю дату по умолчанию
        document.getElementById('datePicker').valueAsDate = new Date();
        document.getElementById('datePicker').style.display = 'none'; // Скрыт на дашборде

        function switchTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            document.getElementById('dashboard').style.display = tab === 'dashboard' ? 'grid' : 'none';
            document.getElementById('stats').style.display = tab === 'stats' ? 'block' : 'none';
            document.getElementById('load_stats').style.display = tab === 'load_stats' ? 'block' : 'none';
            document.getElementById('battery_stats').style.display = tab === 'battery_stats' ? 'block' : 'none';
            
            document.getElementById('datePicker').style.display = tab === 'dashboard' ? 'none' : 'block';

            if(tab === 'stats' || tab === 'load_stats' || tab === 'battery_stats') loadStats();
        }

        async function loadStats() {
            const date = document.getElementById('datePicker').value;
            const res = await fetch(`/api/history?date=${date}`);
            const data = await res.json();
            
            const ctx = document.getElementById('historyChart').getContext('2d');
            
            // Если разрыв больше 2 минут (120 сек), вставляем null, чтобы Chart.js разорвал линию!
            let processedData = [];
            let inVoltData = [];
            let outVoltData = [];
            let loadData = [];
            let tempData = [];
            let battVoltData = [];
            let battChargeData = [];
            
            for(let i = 0; i < data.length; i++) {
                const pt = data[i];
                const timeStr = new Date(pt.ts * 1000).toLocaleTimeString('ru-RU', {hour: '2-digit', minute:'2-digit'});
                
                if (i > 0 && (pt.ts - data[i-1].ts > 120)) {
                    // Пустое окно (ПК был выключен) - вставляем разрыв
                    processedData.push({x: 'Разрыв', y: null});
                    inVoltData.push({x: 'Разрыв', y: null});
                    outVoltData.push({x: 'Разрыв', y: null});
                    loadData.push({x: 'Разрыв', y: null});
                    tempData.push({x: 'Разрыв', y: null});
                    battVoltData.push({x: 'Разрыв', y: null});
                    battChargeData.push({x: 'Разрыв', y: null});
                }
                
                // Статус: если OL (Сеть) = 1, если OB (Батарея) = 0
                const stateVal = pt.st.includes('OL') ? 1 : 0;
                processedData.push({x: timeStr, y: stateVal, rawStatus: pt.st});
                inVoltData.push({x: timeStr, y: pt.in_volt});
                outVoltData.push({x: timeStr, y: pt.out_volt === undefined ? null : pt.out_volt});
                loadData.push({x: timeStr, y: pt.load});
                tempData.push({x: timeStr, y: pt.temp === undefined ? null : pt.temp});
                battVoltData.push({x: timeStr, y: pt.batt_volt === undefined ? null : pt.batt_volt});
                battChargeData.push({x: timeStr, y: pt.charge === undefined ? null : pt.charge});
            }

            if(chartInstance) chartInstance.destroy();

            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    datasets: [
                        {
                            label: 'Наличие сети (1=Сеть, 0=Батарея)',
                            data: processedData,
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            borderWidth: 2,
                            fill: false,
                            stepped: true, // Ступенчатый график для состояний
                            spanGaps: false // ВАЖНО: не соединять разрывы (пустые окна)
                        },
                        {
                            label: 'Входное напряжение (V)',
                            data: inVoltData,
                            borderColor: '#3b82f6',
                            borderWidth: 2,
                            pointRadius: 0,
                            tension: 0.3, // Сглаживание линии напряжения
                            spanGaps: false,
                            yAxisID: 'y1'
                        },
                        {
                            label: 'Выходное напряжение (V)',
                            data: outVoltData,
                            borderColor: '#f59e0b', // Оранжевый
                            borderWidth: 2,
                            pointRadius: 0,
                            tension: 0.3,
                            spanGaps: false,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            min: -0.1, max: 1.1,
                            ticks: { callback: function(value) { return value === 1 ? 'Сеть' : (value === 0 ? 'Батарея' : ''); } }
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            min: 0, max: 270,
                            grid: { drawOnChartArea: false }
                        }
                    }
                }
            });

            if(loadChartInstance) loadChartInstance.destroy();
            
            const ctxLoad = document.getElementById('loadChart').getContext('2d');
            loadChartInstance = new Chart(ctxLoad, {
                type: 'line',
                data: {
                    datasets: [
                        {
                            label: 'Нагрузка на ИБП (%)',
                            data: loadData,
                            borderColor: '#8b5cf6', // Фиолетовый
                            backgroundColor: 'rgba(139, 92, 246, 0.2)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.3,
                            spanGaps: false
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            min: 0, max: 100
                        }
                    }
                }
            });

            if(tempChartInstance) tempChartInstance.destroy();
            
            const ctxTemp = document.getElementById('tempChart').getContext('2d');
            tempChartInstance = new Chart(ctxTemp, {
                type: 'line',
                data: {
                    datasets: [
                        {
                            label: 'Температура ИБП (°C)',
                            data: tempData,
                            borderColor: '#ef4444', // Красный
                            backgroundColor: 'rgba(239, 68, 68, 0.2)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.3,
                            spanGaps: false
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            min: 20, max: 70
                        }
                    }
                }
            });

            if(battVoltChartInstance) battVoltChartInstance.destroy();
            const ctxBattVolt = document.getElementById('battVoltChart').getContext('2d');
            battVoltChartInstance = new Chart(ctxBattVolt, {
                type: 'line',
                data: {
                    datasets: [
                        {
                            label: 'Напряжение АКБ (V)',
                            data: battVoltData,
                            borderColor: '#3b82f6',
                            backgroundColor: 'rgba(59, 130, 246, 0.2)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.3,
                            spanGaps: false
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            min: 20, max: 30
                        }
                    }
                }
            });

            if(battChargeChartInstance) battChargeChartInstance.destroy();
            const ctxBattCharge = document.getElementById('battChargeChart').getContext('2d');
            battChargeChartInstance = new Chart(ctxBattCharge, {
                type: 'line',
                data: {
                    datasets: [
                        {
                            label: 'Заряд АКБ (%)',
                            data: battChargeData,
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.2)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.3,
                            spanGaps: false
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            min: 0, max: 100
                        }
                    }
                }
            });
        }

        async function fetchData() {
            if (currentTab !== 'dashboard') return; // Не спамим запросами, если открыта статистика
            try {
                const res = await fetch('/api/data');
                const data = await res.json();
                
                if (data.error) {
                    document.getElementById('statusBadge').className = 'status-badge error';
                    document.getElementById('statusBadge').innerText = 'Ошибка связи с ИБП';
                    return;
                }

                const stat = data['ups.status'] || '';
                const isOnline = stat.includes('OL');
                const isBattery = stat.includes('OB');
                
                let badge = document.getElementById('statusBadge');
                if (isOnline) {
                    badge.innerText = '⚡ Работает от сети';
                    badge.style.background = 'rgba(16, 185, 129, 0.2)';
                    badge.style.color = 'var(--accent-green)';
                    badge.style.borderColor = 'var(--accent-green)';
                } else if (isBattery) {
                    badge.innerText = '🔋 РАБОТАЕТ ОТ БАТАРЕИ!';
                    badge.style.background = 'rgba(239, 68, 68, 0.2)';
                    badge.style.color = 'var(--accent-red)';
                    badge.style.borderColor = 'var(--accent-red)';
                } else {
                    badge.innerText = 'Статус: ' + stat;
                }

                const charge = data['battery.charge'] || 0;
                document.getElementById('battCharge').innerText = charge;
                let battBar = document.getElementById('battProgress');
                battBar.style.width = charge + '%';
                battBar.style.background = charge < 30 ? 'var(--accent-red)' : 'var(--accent-green)';
                battBar.style.boxShadow = charge < 30 ? '0 0 15px var(--accent-red)' : '0 0 15px var(--accent-green)';

                document.getElementById('battVolt').innerText = data['battery.voltage'] || '--';

                const load = data['ups.load'] || 0;
                document.getElementById('load').innerText = load;
                document.getElementById('loadProgress').style.width = load + '%';

                document.getElementById('inVolt').innerText = data['input.voltage'] || '--';
                document.getElementById('outVolt').innerText = data['output.voltage'] || '--';
                document.getElementById('upsTemp').innerText = data['ups.temperature'] || '--';
                document.getElementById('inFreq').innerText = data['input.frequency'] || '--';

            } catch (err) {
                console.error(err);
            }
        }
        
        fetchData();
        setInterval(fetchData, 2000);
    </script>
</body>
</html>
"""

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

class UPSHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        
        if parsed_url.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
            
        elif parsed_url.path == '/ups.png':
            try:
                with open("/home/mge_engineer/ups.png", "rb") as f:
                    self.send_response(200)
                    self.send_header("Content-type", "image/png")
                    self.end_headers()
                    self.wfile.write(f.read())
            except Exception:
                self.send_response(404)
                self.end_headers()
                
        elif parsed_url.path == '/api/history':
            qs = parse_qs(parsed_url.query)
            date_str = qs.get('date', [''])[0]
            if not date_str:
                date_str = datetime.now().strftime('%Y-%m-%d')
            
            try:
                dt_start = int(datetime.strptime(date_str, '%Y-%m-%d').timestamp())
                dt_end = dt_start + 86400
                
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT timestamp, status, in_volt, load, out_volt, temperature, charge, voltage FROM ups_log WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp ASC", (dt_start, dt_end))
                rows = c.fetchall()
                conn.close()
                
                data = [{"ts": r[0], "st": r[1], "in_volt": r[2], "load": r[3], "out_volt": r[4], "temp": r[5], "charge": r[6], "batt_volt": r[7]} for r in rows]
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                
        elif parsed_url.path == '/api/data':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            try:
                output = subprocess.check_output(['upsc', 'ritar'], stderr=subprocess.STDOUT).decode('utf-8')
                data = {}
                for line in output.split('\n'):
                    if ':' in line:
                        k, v = line.split(':', 1)
                        data[k.strip()] = v.strip()
                self.wfile.write(json.dumps(data).encode('utf-8'))
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    # Инициализация БД
    init_db()
    
    # Запуск фонового сборщика статистики (Daemon-поток завершится при выходе)
    t = threading.Thread(target=log_data_loop, daemon=True)
    t.start()
    
    with ReusableTCPServer(("", PORT), UPSHandler) as httpd:
        print(f"Сервер Web GUI и логгер запущены на порту {PORT}...")
        httpd.serve_forever()
