#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نظام إدارة جداول المحاضرات والسكاشن المركزي
PWA - Progressive Web App
تطوير وبرمجة المهندس: Mokhtar Gerges © 2026
"""

import os
import sqlite3
import json
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

# ────────────────────────────────────────────────
# إعداد التطبيق
# ────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'institute-schedule-2026-mokhtar-gerges'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

DB_PATH = os.path.join(os.path.dirname(__file__), 'institute_schedule.db')

# ────────────────────────────────────────────────
# قاعدة البيانات
# ────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year TEXT NOT NULL,
            dept TEXT NOT NULL,
            type TEXT NOT NULL,
            day TEXT NOT NULL,
            name TEXT NOT NULL,
            doctor TEXT,
            time TEXT,
            hall TEXT,
            note TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

# ────────────────────────────────────────────────
# دوال مساعدة
# ────────────────────────────────────────────────
def get_today_arabic():
    days_map = {
        "Saturday": "السبت", "Sunday": "الأحد", "Monday": "الإثنين",
        "Tuesday": "الثلاثاء", "Wednesday": "الأربعاء",
        "Thursday": "الخميس", "Friday": "الجمعة"
    }
    return days_map.get(datetime.now().strftime("%A"), "السبت")

def parse_time_minutes(time_str):
    if not time_str:
        return None
    try:
        time_str = time_str.strip().replace("ص", "").replace("م", "").strip()
        parts = time_str.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        pass
    return None

def times_overlap(time1, time2, buffer_minutes=30):
    t1 = parse_time_minutes(time1)
    t2 = parse_time_minutes(time2)
    if t1 is None or t2 is None:
        return False
    duration = 60
    start1, end1 = t1, t1 + duration
    start2, end2 = t2, t2 + duration
    return not (end1 + buffer_minutes <= start2 or end2 + buffer_minutes <= start1)

# ────────────────────────────────────────────────
# المسارات الرئيسية
# ────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json', mimetype='application/json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('.', 'sw.js', mimetype='application/javascript')

# ────────────────────────────────────────────────
# API - الجداول
# ────────────────────────────────────────────────
@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    day = request.args.get('day', get_today_arabic())
    year = request.args.get('year', 'كل الفرق الدراسية')
    dept = request.args.get('dept', 'كل الشعب والتخصصات')
    type_filter = request.args.get('type', 'كل الأنواع')

    conn = get_db()
    query = "SELECT * FROM schedule WHERE day=?"
    params = [day]

    if year != 'كل الفرق الدراسية':
        query += " AND year=?"
        params.append(year)

    if type_filter == 'نظري فقط':
        query += " AND type='نظري'"
    elif type_filter == 'عملي فقط':
        query += " AND type='عملي'"

    query += " ORDER BY time"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    result = []
    for row in rows:
        row_dept = row['dept']
        if dept == 'كل الشعب والتخصصات' or row_dept in (dept, 'كل الشعب', ''):
            result.append(dict(row))

    return jsonify(result)

@app.route('/api/schedule', methods=['POST'])
def add_schedule():
    data = request.get_json()

    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO schedule (year, dept, type, day, name, doctor, time, hall, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('year', 'الفرقة الأولى'),
        data.get('dept', 'كل الشعب'),
        data.get('type', 'نظري'),
        data.get('day', 'السبت'),
        data['name'],
        data.get('doctor', ''),
        data.get('time', ''),
        data.get('hall', ''),
        data.get('note', ''),
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return jsonify({'success': True, 'id': new_id})

@app.route('/api/schedule/<int:item_id>', methods=['PUT'])
def update_schedule(item_id):
    data = request.get_json()

    conn = get_db()
    conn.execute("""
        UPDATE schedule SET year=?, dept=?, type=?, day=?, name=?,
                          doctor=?, time=?, hall=?, note=?
        WHERE id=?
    """, (
        data.get('year'), data.get('dept'), data.get('type'), data.get('day'),
        data['name'], data.get('doctor', ''), data.get('time', ''),
        data.get('hall', ''), data.get('note', ''), item_id
    ))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/schedule/<int:item_id>', methods=['DELETE'])
def delete_schedule(item_id):
    conn = get_db()
    conn.execute("DELETE FROM schedule WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/schedule/<int:item_id>/note', methods=['PUT'])
def update_note(item_id):
    data = request.get_json()
    conn = get_db()
    conn.execute("UPDATE schedule SET note=? WHERE id=?", (data.get('note', ''), item_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ────────────────────────────────────────────────
# API - التعارضات
# ────────────────────────────────────────────────
@app.route('/api/conflicts', methods=['GET'])
def get_conflicts():
    conn = get_db()
    rows = conn.execute("SELECT * FROM schedule ORDER BY day, time, hall").fetchall()
    conn.close()

    conflicts = []
    by_day_hall = {}

    for row in rows:
        day = row['day']
        hall = (row['hall'] or "").strip()
        if not hall:
            continue
        key = (day, hall)
        if key not in by_day_hall:
            by_day_hall[key] = []
        by_day_hall[key].append(dict(row))

    for (day, hall), sessions in by_day_hall.items():
        sessions_sorted = sorted(sessions, key=lambda x: x.get('time') or "")
        for i in range(len(sessions_sorted)):
            for j in range(i + 1, len(sessions_sorted)):
                r1, r2 = sessions_sorted[i], sessions_sorted[j]
                if r1.get('time') and r2.get('time') and times_overlap(r1['time'], r2['time']):
                    conflicts.append({
                        'day': day, 'hall': hall,
                        'session1': r1, 'session2': r2
                    })

    return jsonify(conflicts)

# ────────────────────────────────────────────────
# API - التنبيهات
# ────────────────────────────────────────────────
@app.route('/api/alerts', methods=['GET'])
def get_upcoming_alerts():
    today = get_today_arabic()
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    alert_window = current_minutes + 20

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM schedule WHERE day=? ORDER BY time",
        (today,)
    ).fetchall()
    conn.close()

    alerts = []
    for row in rows:
        t = parse_time_minutes(row['time'])
        if t and current_minutes <= t <= alert_window:
            alerts.append({
                **dict(row),
                'minutes_until': t - current_minutes
            })

    return jsonify(alerts)

# ────────────────────────────────────────────────
# API - الاستيراد
# ────────────────────────────────────────────────
@app.route('/api/import/excel', methods=['POST'])
def import_excel():
    if 'file' not in request.files:
        return jsonify({'error': 'لم يتم اختيار ملف'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'اسم الملف فارغ'}), 400

    try:
        import openpyxl
        wb = openpyxl.load_workbook(file)
        ws = wb.active
        count = 0

        conn = get_db()
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue

            type_val = "عملي" if "عملي" in str(row[2] or "") else "نظري"

            conn.execute("""
                INSERT INTO schedule (year, dept, type, day, name, doctor, time, hall, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(row[0]) if row[0] else "الفرقة الأولى",
                str(row[1]) if row[1] else "كل الشعب",
                type_val,
                str(row[3]) if row[3] else "السبت",
                str(row[4]) if row[4] else "",
                str(row[5]) if row[5] else "",
                str(row[6]) if row[6] else "",
                str(row[7]) if row[7] else "",
                str(row[8]) if len(row) > 8 and row[8] else "",
            ))
            count += 1

        conn.commit()
        conn.close()
        return jsonify({'success': True, 'count': count})

    except ImportError:
        return jsonify({'error': 'مكتبة openpyxl غير مثبتة'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ────────────────────────────────────────────────
# تشغيل التطبيق
# ────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
