from **future** import annotations
import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(**name**)
CORS(app, origins=”*”)

DB_PATH = os.path.join(os.path.dirname(**file**), ‘medismart.db’)

def get_db():
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
return conn

def init_db():
conn = get_db()
conn.executescript(’’’
CREATE TABLE IF NOT EXISTS patients (
id TEXT PRIMARY KEY,
nom TEXT NOT NULL,
dob TEXT,
sexe TEXT,
groupe_sanguin TEXT,
pays TEXT,
ville TEXT,
telephone TEXT,
email TEXT,
specialite TEXT,
maladie TEXT,
gravite TEXT,
type_consult TEXT,
symptomes TEXT,
antecedents TEXT,
temperature REAL,
pression TEXT,
fc INTEGER,
spo2 INTEGER,
poids REAL,
taille REAL,
type_examen TEXT,
resultats TEXT,
date_creation TEXT,
timestamp INTEGER
);
CREATE TABLE IF NOT EXISTS ordonnances (
id TEXT PRIMARY KEY,
patient_id TEXT,
patient_nom TEXT,
specialite TEXT,
maladie TEXT,
medicaments TEXT,
ai_analysis TEXT,
date_creation TEXT,
FOREIGN KEY (patient_id) REFERENCES patients(id)
);
CREATE TABLE IF NOT EXISTS examens (
id INTEGER PRIMARY KEY AUTOINCREMENT,
patient_id TEXT,
type_examen TEXT,
date_examen TEXT,
resultats TEXT,
medecin TEXT,
date_creation TEXT,
FOREIGN KEY (patient_id) REFERENCES patients(id)
);
‘’’)
conn.commit()
conn.close()

init_db()

@app.route(’/api/health’, methods=[‘GET’])
def health():
conn = get_db()
total = conn.execute(‘SELECT COUNT(*) FROM patients’).fetchone()[0]
conn.close()
return jsonify({‘status’: ‘ok’, ‘total_patients’: total, ‘version’: ‘2.0’})

@app.route(’/api/patients’, methods=[‘GET’])
def get_patients():
conn = get_db()
specialite = request.args.get(‘specialite’)
pays = request.args.get(‘pays’)
gravite = request.args.get(‘gravite’)
search = request.args.get(‘search’)
limit = int(request.args.get(‘limit’, 100))
query = ‘SELECT * FROM patients WHERE 1=1’
params = []
if specialite:
query += ’ AND specialite = ?’
params.append(specialite)
if pays:
query += ’ AND pays = ?’
params.append(pays)
if gravite:
query += ’ AND gravite = ?’
params.append(gravite)
if search:
query += ’ AND (nom LIKE ? OR maladie LIKE ? OR ville LIKE ?)’
params += [’%’ + search + ‘%’, ‘%’ + search + ‘%’, ‘%’ + search + ‘%’]
query += ’ ORDER BY timestamp DESC LIMIT ?’
params.append(limit)
rows = conn.execute(query, params).fetchall()
conn.close()
return jsonify({‘patients’: [dict(r) for r in rows], ‘total’: len(rows)})

@app.route(’/api/patients’, methods=[‘POST’])
def create_patient():
data = request.get_json()
if not data or not data.get(‘nom’) or not data.get(‘maladie’):
return jsonify({‘error’: ‘Champs obligatoires manquants’}), 400
patient_id = ‘PAT-’ + str(int(datetime.now().timestamp() * 1000))
now = datetime.now().strftime(’%d/%m/%Y %H:%M’)
conn = get_db()
conn.execute(’’’
INSERT INTO patients VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
‘’’, (
patient_id,
data.get(‘nom’), data.get(‘dob’), data.get(‘sexe’),
data.get(‘groupe_sanguin’), data.get(‘pays’), data.get(‘ville’),
data.get(‘telephone’), data.get(‘email’), data.get(‘specialite’),
data.get(‘maladie’), data.get(‘gravite’), data.get(‘type_consult’),
data.get(‘symptomes’), data.get(‘antecedents’),
data.get(‘temperature’), data.get(‘pression’),
data.get(‘fc’), data.get(‘spo2’),
data.get(‘poids’), data.get(‘taille’),
data.get(‘type_examen’), data.get(‘resultats’),
now, int(datetime.now().timestamp())
))
medicaments = generate_medicaments(data.get(‘specialite’, ‘’))
ai_text = generate_ai_analysis(data)
ord_id = ‘ORD-’ + str(int(datetime.now().timestamp() * 1000))
conn.execute(’’’
INSERT INTO ordonnances VALUES (?,?,?,?,?,?,?,?)
‘’’, (ord_id, patient_id, data.get(‘nom’), data.get(‘specialite’),
data.get(‘maladie’), json.dumps(medicaments), ai_text, now))
conn.commit()
conn.close()
return jsonify({‘success’: True, ‘patient_id’: patient_id, ‘ordonnance_id’: ord_id}), 201

@app.route(’/api/patients/<patient_id>’, methods=[‘GET’])
def get_patient(patient_id):
conn = get_db()
row = conn.execute(‘SELECT * FROM patients WHERE id = ?’, (patient_id,)).fetchone()
conn.close()
if not row:
return jsonify({‘error’: ‘Patient non trouve’}), 404
return jsonify(dict(row))

@app.route(’/api/patients/<patient_id>’, methods=[‘PUT’])
def update_patient(patient_id):
data = request.get_json()
conn = get_db()
conn.execute(’’’
UPDATE patients SET nom=?, maladie=?, gravite=?, symptomes=?,
temperature=?, fc=?, spo2=?, pression=? WHERE id=?
‘’’, (data.get(‘nom’), data.get(‘maladie’), data.get(‘gravite’),
data.get(‘symptomes’), data.get(‘temperature’), data.get(‘fc’),
data.get(‘spo2’), data.get(‘pression’), patient_id))
conn.commit()
conn.close()
return jsonify({‘success’: True})

@app.route(’/api/patients/<patient_id>/examens’, methods=[‘GET’])
def get_examens(patient_id):
conn = get_db()
rows = conn.execute(‘SELECT * FROM examens WHERE patient_id = ? ORDER BY date_creation DESC’, (patient_id,)).fetchall()
conn.close()
return jsonify({‘examens’: [dict(r) for r in rows]})

@app.route(’/api/patients/<patient_id>/examens’, methods=[‘POST’])
def add_examen(patient_id):
data = request.get_json()
now = datetime.now().strftime(’%d/%m/%Y %H:%M’)
conn = get_db()
conn.execute(’’’
INSERT INTO examens (patient_id, type_examen, date_examen, resultats, medecin, date_creation)
VALUES (?,?,?,?,?,?)
‘’’, (patient_id, data.get(‘type_examen’), data.get(‘date_examen’),
data.get(‘resultats’), data.get(‘medecin’), now))
conn.commit()
conn.close()
return jsonify({‘success’: True}), 201

@app.route(’/api/ordonnances’, methods=[‘GET’])
def get_ordonnances():
conn = get_db()
rows = conn.execute(‘SELECT * FROM ordonnances ORDER BY date_creation DESC’).fetchall()
conn.close()
result = []
for r in rows:
d = dict(r)
try:
d[‘medicaments’] = json.loads(d[‘medicaments’])
except Exception:
pass
result.append(d)
return jsonify({‘ordonnances’: result})

@app.route(’/api/ordonnances/<patient_id>’, methods=[‘GET’])
def get_ordonnance_patient(patient_id):
conn = get_db()
rows = conn.execute(‘SELECT * FROM ordonnances WHERE patient_id = ?’, (patient_id,)).fetchall()
conn.close()
result = []
for r in rows:
d = dict(r)
try:
d[‘medicaments’] = json.loads(d[‘medicaments’])
except Exception:
pass
result.append(d)
return jsonify({‘ordonnances’: result})

@app.route(’/api/stats’, methods=[‘GET’])
def get_stats():
conn = get_db()
total = conn.execute(‘SELECT COUNT(*) FROM patients’).fetchone()[0]
par_specialite = conn.execute(’SELECT specialite, COUNT(*) as count FROM patients GROUP BY specialite’).fetchall()
par_pays = conn.execute(‘SELECT pays, COUNT(*) as count FROM patients GROUP BY pays ORDER BY count DESC LIMIT 10’).fetchall()
par_gravite = conn.execute(’SELECT gravite, COUNT(*) as count FROM patients GROUP BY gravite’).fetchall()
par_maladie = conn.execute(‘SELECT maladie, COUNT(*) as count FROM patients GROUP BY maladie ORDER BY count DESC LIMIT 10’).fetchall()
avg_temp = conn.execute(‘SELECT AVG(temperature) FROM patients WHERE temperature IS NOT NULL’).fetchone()[0]
avg_fc = conn.execute(‘SELECT AVG(fc) FROM patients WHERE fc IS NOT NULL’).fetchone()[0]
avg_spo2 = conn.execute(‘SELECT AVG(spo2) FROM patients WHERE spo2 IS NOT NULL’).fetchone()[0]
conn.close()
return jsonify({
‘total_patients’: total,
‘par_specialite’: [dict(r) for r in par_specialite],
‘par_pays’: [dict(r) for r in par_pays],
‘par_gravite’: [dict(r) for r in par_gravite],
‘par_maladie’: [dict(r) for r in par_maladie],
‘avg_temperature’: round(avg_temp, 1) if avg_temp else None,
‘avg_fc’: round(avg_fc) if avg_fc else None,
‘avg_spo2’: round(avg_spo2) if avg_spo2 else None,
})

@app.route(’/api/carnet/login’, methods=[‘POST’])
def carnet_login():
data = request.get_json()
patient_id = data.get(‘patient_id’)
conn = get_db()
patient = conn.execute(‘SELECT * FROM patients WHERE id = ?’, (patient_id,)).fetchone()
examens = conn.execute(‘SELECT * FROM examens WHERE patient_id = ? ORDER BY date_creation DESC’, (patient_id,)).fetchall()
ordonnances = conn.execute(‘SELECT * FROM ordonnances WHERE patient_id = ?’, (patient_id,)).fetchall()
conn.close()
if not patient:
return jsonify({‘error’: ‘Patient non trouve’}), 404
return jsonify({
‘patient’: dict(patient),
‘examens’: [dict(e) for e in examens],
‘ordonnances’: [dict(o) for o in ordonnances]
})

def generate_medicaments(specialite):
meds = {
‘Cardiologie’: [‘Amlodipine 5mg - 1cp/jour matin’, ‘Bisoprolol 5mg - 1cp/jour’, ‘Aspirine 100mg - 1cp/jour repas’],
‘Neurologie’: [‘Gabapentine 300mg - 1cp x3/jour’, ‘Vitamine B12 1000ug - 1cp/jour’],
‘Pneumologie’: [‘Salbutamol spray - 2 bouff. si besoin’, ‘Beclometasone 200ug - 2 bouff. x2/jour’],
‘Pediatrie’: [‘Paracetamol 250mg - 1 supp. x3/jour’, ‘Vitamine D 800UI - 1cp/jour’],
‘Oncologie’: [‘Selon protocole oncologique specifique’, ‘Antiemetiques selon tolerance’],
‘default’: [‘Paracetamol 1g - 1cp x3/jour si douleur’, ‘Repos et hydratation suffisante’]
}
return meds.get(specialite, meds[‘default’])

def generate_ai_analysis(data):
nom = data.get(‘nom’, ‘Patient’)
sp = data.get(‘specialite’, ‘Medecine generale’)
gravite = data.get(‘gravite’, ‘moderee’)
symptomes = (data.get(‘symptomes’) or ‘’)[:100]
temp = data.get(‘temperature’)
fc = data.get(‘fc’)
alerts = []
if temp and float(temp) > 38:
alerts.append(‘Fievre detectee - bilan infectieux conseille.’)
if fc and int(fc) > 100:
alerts.append(‘Tachycardie - surveillance cardiaque recommandee.’)
if fc and int(fc) < 50:
alerts.append(‘Bradycardie - consultation urgente.’)
alert_text = ’ ’.join(alerts)
return ’Analyse IA - Patient ’ + nom + ’, ’ + sp + ’. Gravite ’ + gravite + ’. Symptomes : ’ + symptomes + ‘. ’ + alert_text + ’ Protocole therapeutique recommande avec reevaluation dans 4 semaines.’

if **name** == ‘**main**’:
port = int(os.environ.get(‘PORT’, 5000))
app.run(host=‘0.0.0.0’, port=port, debug=False)
