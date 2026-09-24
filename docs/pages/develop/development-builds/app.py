"""
Sistema Integrado de Calidad de Paneles - Kingspan | LTN
-----------------------------------------------------------
"""

import os
import io
import json
import base64
import html
import traceback
import zipfile
import math
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (
    Flask, render_template_string, request, jsonify, Response, send_file, session, redirect, url_for
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, text
from werkzeug.security import generate_password_hash, check_password_hash

# ------------------------------------------------------------------
# Helper de Zona Horaria (Buenos Aires UTC-3)
# ------------------------------------------------------------------
def bsas_now():
    """Retorna la fecha y hora exacta de Buenos Aires (Argentina) sin importar dónde esté el servidor"""
    return datetime.utcnow() - timedelta(hours=3)

# ------------------------------------------------------------------
# Configuración de la app / base de datos
# ------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="static")
application = app  

app.secret_key = os.environ.get("SECRET_KEY", "llave-super-secreta-kingspan-ltn")
app.config['PERMANENT_SESSION_LIFETIME'] = 43200 

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

if not DATABASE_URL:
    DATABASE_URL = "sqlite:///" + os.path.join(BASE_DIR, "local_dev.db")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 280,
    "pool_timeout": 10,
    "pool_size": 10,
    "max_overflow": 20
}
db = SQLAlchemy(app)

DEFECTOS_RECLAMO = [
    "Ancho útil fuera de tolerancia", "Chapa marcada / rayada", "Chapa sin pintura",
    "Cresta vacía deformada", "Defecto visual en espuma", "Defecto visual en foil",
    "Desborde de espuma", "Encastre macho chico", "Enrase fuera de tolerancia",
    "Espesor fuera de tolerancia", "Panel ondulaciones / rechupes", "Paneles sin adherencia",
    "Otro defecto (detallar en observaciones)"
]

DEFAULT_CONFIG = {
    "personal": ["LE", "OF", "LG", "GW", "GR", "MS", "Pasante", "Otro Operario"],
    "nucleos": ["I (PIR Estandar)", "U (PUR Estandar)", "LR (Lana de Roca)", "EPS", "PRUEBA"],
    "tolerancias": {
        "AP60":   {"e_min": 56.0,  "e_max": 59.0,  "E_min": 58.0,  "E_max": 61.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 1149.0, "ancho_tol": 3.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "AP100":  {"e_min": 95.0,  "e_max": 100.0, "E_min": 97.0,  "E_max": 102.0, "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 1149.0, "ancho_tol": 3.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "CW40":   {"e_min": 36.0,  "e_max": 39.0,  "E_min": 38.0,  "E_max": 41.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 998.0,  "ancho_tol": 2.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "CW50":   {"e_min": 46.0,  "e_max": 49.0,  "E_min": 48.0,  "E_max": 51.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 998.0,  "ancho_tol": 2.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "CW60":   {"e_min": 56.0,  "e_max": 59.0,  "E_min": 58.0,  "E_max": 61.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 998.0,  "ancho_tol": 2.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "CW80":   {"e_min": 76.0,  "e_max": 79.0,  "E_min": 78.0,  "E_max": 81.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 998.0,  "ancho_tol": 2.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "FR10":   {"e_min": 6.0,   "e_max": 9.0,   "E_min": 8.0,   "E_max": 11.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 998.0,  "ancho_tol": 3.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},  
        "FR30":   {"e_min": 26.0,  "e_max": 29.0,  "E_min": 28.0,  "E_max": 31.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 998.0,  "ancho_tol": 3.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "FR50":   {"e_min": 46.0,  "e_max": 49.0,  "E_min": 48.0,  "E_max": 51.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 998.0,  "ancho_tol": 3.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "MC30":   {"e_min": 26.0,  "e_max": 29.0,  "E_min": 28.0,  "E_max": 31.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 1149.0, "ancho_tol": 1.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "MC40":   {"e_min": 36.0,  "e_max": 39.0,  "E_min": 38.0,  "E_max": 41.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 1149.0, "ancho_tol": 1.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "MC50":   {"e_min": 46.0,  "e_max": 49.0,  "E_min": 48.0,  "E_max": 51.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 1149.0, "ancho_tol": 1.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "MC60":   {"e_min": 56.0,  "e_max": 59.0,  "E_min": 58.0,  "E_max": 61.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 1149.0, "ancho_tol": 1.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "MC80":   {"e_min": 76.0,  "e_max": 79.0,  "E_min": 78.0,  "E_max": 81.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 1149.0, "ancho_tol": 1.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "MC100":  {"e_min": 95.0,  "e_max": 100.0, "E_min": 97.0,  "E_max": 102.0, "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 1149.0, "ancho_tol": 1.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "MC120":  {"e_min": 115.0, "e_max": 120.0, "E_min": 117.0, "E_max": 122.0, "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 1149.0, "ancho_tol": 1.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "MC150":  {"e_min": 145.0, "e_max": 150.0, "E_min": 147.0, "E_max": 152.0, "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 1149.0, "ancho_tol": 1.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "MC180":  {"e_min": 175.0, "e_max": 180.0, "E_min": 177.0, "E_max": 182.0, "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 1149.0, "ancho_tol": 1.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "MC200":  {"e_min": 195.0, "e_max": 200.0, "E_min": 197.0, "E_max": 202.0, "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 1149.0, "ancho_tol": 1.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "MR30":   {"e_min": 26.0,  "e_max": 29.0,  "E_min": 28.0,  "E_max": 31.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 998.0,  "ancho_tol": 3.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "MR40":   {"e_min": 36.0,  "e_max": 39.0,  "E_min": 38.0,  "E_max": 41.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 998.0,  "ancho_tol": 3.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
        "MR50":   {"e_min": 46.0,  "e_max": 49.0,  "E_min": 48.0,  "E_max": 51.0,  "gc_max": 3.0, "gn_max": 2.0, "r_max": 2.0, "ancho_nom": 998.0,  "ancho_tol": 3.0, "r_foil_min": 1.0, "r_foil_max": 7.0, "hmi_min": None, "hmi_max": None, "hme_min": None, "hme_max": None, "hhi_min": None, "hhi_max": None, "hhe_min": None, "hhe_max": None, "escuadra_nom": 90.0, "escuadra_tol": 3.0},
    }
}

HEADERS = [
    "ID", "Tipo", "Fecha", "Hora Control", "Modelo", "Resp./Operario", "PV", "Ppto",
    "Cliente", "Etiqueta", "Núcleo", "Defecto Reclamo",
    "Reposo [hs]", "Densidad [kg/cm³]", "Vel [m/min]", "Largo Muestra [m]",
    "Aspecto", "m² Controlados", "m² Rechazados", "Ancho Útil [mm]",
    "Hmi [mm]", "Hme [mm]", "Hhi [mm]", "Hhe [mm]",
    "E [mm]", "e1 [mm]", "e2 [mm]", "e3 [mm]", "Media e [mm]", "E+C [mm]",
    "Gc [mm]", "Gci [mm]", "Gce [mm]", "Gn [mm]", "R [mm]", "R1 [mm]", "R2 [mm]", "Escuadra [º]",
    "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "N9",
    "Dictamen", "Desvíos", "Observaciones", "Cantidad Fotos",
]

# ------------------------------------------------------------------
# Modelos de base de datos
# ------------------------------------------------------------------

class Usuario(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), default="operador")
    permisos = db.Column(db.String(255), default="escribir,editar,excel")
    activo = db.Column(db.Boolean, default=True)

class Auditoria(db.Model):
    __tablename__ = "auditoria"
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=bsas_now)
    usuario = db.Column(db.String(50))
    accion = db.Column(db.String(50))
    detalle = db.Column(db.Text)

class Configuracion(db.Model):
    __tablename__ = "configuracion"
    id = db.Column(db.Integer, primary_key=True)
    datos_json = db.Column(db.Text, nullable=False)

class Registro(db.Model):
    __tablename__ = "registros"
    id = db.Column(db.Integer, primary_key=True)
    creado_en = db.Column(db.DateTime, default=bsas_now)
    activo = db.Column(db.Boolean, default=True)

    tipo = db.Column(db.String(20), default="proceso")
    fecha = db.Column(db.String(40))
    hora_control = db.Column(db.String(20))
    modelo = db.Column(db.String(20))
    resp = db.Column(db.String(60))
    pv = db.Column(db.String(40))
    ppto = db.Column(db.String(40))
    cliente = db.Column(db.String(200))
    etiqueta = db.Column(db.String(100))
    nucleo = db.Column(db.String(80))
    defecto_reclamo = db.Column(db.String(150))

    reposo = db.Column(db.Float)
    densidad = db.Column(db.Float)
    vel = db.Column(db.Float)
    largo = db.Column(db.Float)
    aspecto = db.Column(db.String(20))
    m2_controlados = db.Column(db.Float) 
    m2_rechazados = db.Column(db.Float) 
    ancho = db.Column(db.Float)

    hmi = db.Column(db.Float)
    hme = db.Column(db.Float)
    hhi = db.Column(db.Float)
    hhe = db.Column(db.Float)

    E = db.Column(db.Float)
    e1 = db.Column(db.Float)
    e2 = db.Column(db.Float)
    e3 = db.Column(db.Float)
    prom_e = db.Column(db.Float)
    e_c = db.Column(db.Float)

    gc = db.Column(db.Float)
    gci = db.Column(db.Float)
    gce = db.Column(db.Float)
    gn = db.Column(db.Float)
    r = db.Column(db.Float)
    rc1 = db.Column(db.Float)
    rc2 = db.Column(db.Float)
    escuadra = db.Column(db.Float)
    
    n1 = db.Column(db.Float); n2 = db.Column(db.Float); n3 = db.Column(db.Float)
    n4 = db.Column(db.Float); n5 = db.Column(db.Float); n6 = db.Column(db.Float)
    n7 = db.Column(db.Float); n8 = db.Column(db.Float); n9 = db.Column(db.Float)

    estado = db.Column(db.String(50))
    desvios = db.Column(db.Text)
    obs = db.Column(db.Text)

    fotos = db.relationship("Foto", backref="registro", cascade="all, delete-orphan")

    def to_row(self):
        esc_excel = ""
        if self.escuadra is not None and self.escuadra > 0:
            deg_ex = int(self.escuadra)
            mnt_ex = int(round((self.escuadra - deg_ex) * 100))
            esc_excel = f"{deg_ex}º {mnt_ex:02d}'"

        return [
            self.id, self.tipo, self.fecha, self.hora_control, self.modelo, self.resp,
            self.pv, self.ppto, self.cliente, self.etiqueta, self.nucleo, self.defecto_reclamo,
            self.reposo, self.densidad, self.vel, self.largo,
            self.aspecto, self.m2_controlados, self.m2_rechazados, self.ancho,
            self.hmi, self.hme, self.hhi, self.hhe,
            self.E, self.e1, self.e2, self.e3, self.prom_e, self.e_c,
            self.gc, self.gci, self.gce, self.gn, self.r, self.rc1, self.rc2, esc_excel,
            self.n1, self.n2, self.n3, self.n4, self.n5, self.n6, self.n7, self.n8, self.n9,
            self.estado, self.desvios, self.obs, "Ver en sistema",
        ]
    
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class Foto(db.Model):
    __tablename__ = "fotos"
    id = db.Column(db.Integer, primary_key=True)
    registro_id = db.Column(db.Integer, db.ForeignKey("registros.id"), nullable=False)
    nombre = db.Column(db.String(255))
    mime = db.Column(db.String(80))
    contenido = db.Column(db.LargeBinary)

class AlertaLog(db.Model):
    __tablename__ = "alerta_log"
    id = db.Column(db.Integer, primary_key=True)
    fecha_generacion = db.Column(db.DateTime, default=bsas_now)
    usuario = db.Column(db.String(50))
    registro_id = db.Column(db.Integer, db.ForeignKey("registros.id"))

def _safe_add_column(table, column, datatype):
    try:
        with db.engine.connect() as conn:
            if conn.engine.url.drivername.startswith('postgres'):
                conn.execute(text("SET statement_timeout = '2s';"))
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {datatype};"))
            conn.commit()
    except Exception:
        pass

with app.app_context():
    db.create_all()
    try:
        if not Usuario.query.first():
            hashed = generate_password_hash("Fede123")
            admin = Usuario(username="admin", password_hash=hashed, rol="admin", permisos="escribir,editar,borrar,excel")
            db.session.add(admin)
            db.session.commit()
    except Exception:
        db.session.rollback()

# ------------------------------------------------------------------
# Decoradores y Helpers
# ------------------------------------------------------------------

def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: return jsonify({"status": "error", "message": "No autorizado"}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('rol') != 'admin': return jsonify({"status": "error", "message": "Permisos insuficientes"}), 403
        return f(*args, **kwargs)
    return decorated_function

def log_auditoria(usuario, accion, detalle):
    try:
        log = Auditoria(usuario=usuario, accion=accion, detalle=detalle)
        db.session.add(log)
        db.session.commit()
    except:
        db.session.rollback()

def load_config():
    try:
        row = Configuracion.query.first()
        if not row:
            cfg = dict(DEFAULT_CONFIG)
            row = Configuracion(datos_json=json.dumps(cfg, ensure_ascii=False))
            db.session.add(row)
            db.session.commit()
            return cfg
    except Exception:
        db.session.rollback()
        return dict(DEFAULT_CONFIG)
        
    try:
        d = json.loads(row.datos_json)
    except Exception: 
        d = dict(DEFAULT_CONFIG)
        
    d.setdefault("tolerancias", {})
    if "CW40" in d["tolerancias"] and d["tolerancias"]["CW40"].get("ancho_nom") == 1150.0:
        d["tolerancias"]["CW40"]["ancho_nom"] = 998.0
        
    for mod, tols in list(d["tolerancias"].items()):
        for k in list(tols.keys()):
            if k.startswith("H") and k[1] in ["m", "h"]:
                tols[k.lower()] = tols.pop(k)

    for mod, tols in DEFAULT_CONFIG["tolerancias"].items():
        base = dict(tols)
        if mod in d["tolerancias"]:
            base.update(d["tolerancias"][mod])
        d["tolerancias"][mod] = base
        
    d.setdefault("personal", DEFAULT_CONFIG["personal"])
    d.setdefault("nucleos", DEFAULT_CONFIG["nucleos"])
    return d

def save_config(d):
    try:
        row = Configuracion.query.first()
        if not row: db.session.add(Configuracion(datos_json=json.dumps(d, ensure_ascii=False)))
        else: row.datos_json = json.dumps(d, ensure_ascii=False)
        db.session.commit()
    except:
        db.session.rollback()

def _f(data, key, default=0.0):
    try:
        val = data.get(key)
        if val is None or str(val).strip() == "": return default 
        val = str(val).replace(',', '.') 
        return float(val)
    except (TypeError, ValueError): return default

def guardar_registro(data, archivos, edit_id=None):
    tipo = data.get("tipo", "proceso")
    
    if edit_id:
        reg = Registro.query.get(edit_id)
        if not reg: raise Exception("Registro no encontrado")
        log_auditoria(session.get('username'), "EDICION", f"Editó registro #{reg.id} de {tipo}")
    else:
        reg = Registro(tipo=tipo)
        db.session.add(reg)
    
    pv_raw = str(data.get("pv", "")).strip()
    ppto_raw = str(data.get("ppto", "")).strip()
    etq_raw = str(data.get("etiqueta", "")).strip()

    if pv_raw and not pv_raw.isdigit(): raise Exception("ERROR DE SEGURIDAD: El campo PV recibió caracteres no numéricos.")
    if ppto_raw and not ppto_raw.isdigit(): raise Exception("ERROR DE SEGURIDAD: El campo Presupuesto recibió caracteres no numéricos.")
    if tipo in ["terminado", "reclamo"] and etq_raw and not etq_raw.isdigit(): raise Exception("ERROR DE SEGURIDAD: El campo Etiqueta recibió caracteres no numéricos.")

    reg.fecha = data.get("fecha")
    reg.hora_control = data.get("hora_control")
    reg.modelo = data.get("modelo")
    reg.resp = data.get("resp")
    reg.pv = pv_raw[:6]
    reg.ppto = ppto_raw[:6]
    reg.etiqueta = etq_raw[:10] if tipo in ["terminado", "reclamo"] else None

    reg.cliente = data.get("cliente")
    reg.nucleo = data.get("nucleo")
    reg.defecto_reclamo = data.get("defecto_reclamo") if tipo in ["terminado", "reclamo"] else None
    
    reg.reposo = _f(data, "reposo", 0.0); reg.densidad = _f(data, "densidad", 0.0)
    reg.vel = _f(data, "vel", 0.0); reg.largo = _f(data, "largo", 0.0); reg.aspecto = data.get("aspecto")
    reg.m2_controlados = _f(data, "m2_controlados", 0.0) if tipo in ["terminado", "reclamo"] else None
    reg.m2_rechazados = _f(data, "m2_rechazados", 0.0) if tipo in ["terminado", "reclamo"] else None
    
    reg.ancho = _f(data, "ancho", 0.0); reg.hmi = _f(data, "hmi", 0.0); reg.hme = _f(data, "hme", 0.0)
    reg.hhi = _f(data, "hhi", 0.0); reg.hhe = _f(data, "hhe", 0.0); reg.E = _f(data, "E", 0.0)
    reg.e1 = _f(data, "e1", 0.0); reg.e2 = _f(data, "e2", 0.0); reg.e3 = _f(data, "e3", 0.0)
    reg.prom_e = _f(data, "prom_e", 0.0); reg.e_c = _f(data, "e_c")
    reg.gc = _f(data, "gc"); reg.gci = _f(data, "gci"); reg.gce = _f(data, "gce")
    reg.gn = _f(data, "gn", 0.0); reg.r = _f(data, "r", 0.0)
    reg.rc1 = _f(data, "rc1"); reg.rc2 = _f(data, "rc2")
    reg.escuadra = _f(data, "escuadra", 0.0)
    
    reg.n1 = _f(data, "n1"); reg.n2 = _f(data, "n2"); reg.n3 = _f(data, "n3")
    reg.n4 = _f(data, "n4"); reg.n5 = _f(data, "n5"); reg.n6 = _f(data, "n6")
    reg.n7 = _f(data, "n7"); reg.n8 = _f(data, "n8"); reg.n9 = _f(data, "n9")
    
    reg.estado = data.get("estado"); reg.desvios = data.get("desvios"); reg.obs = data.get("obs")

    db.session.flush() 

    if archivos and any(f.filename for f in archivos):
        from PIL import Image as PILImage
        if edit_id: Foto.query.filter_by(registro_id=reg.id).delete()
        
        fecha_safe = str(reg.fecha).replace("/", "-").replace(":", "-").replace(" ", "_")
        for idx, f in enumerate(archivos[:12]): 
            if f and f.filename:
                ext = os.path.splitext(f.filename)[1] or ".jpg"
                nombre = f"{reg.id}_{reg.pv}_{fecha_safe}_{idx+1}{ext}"
                
                img_buf = io.BytesIO(f.read())
                try:
                    pil_img = PILImage.open(img_buf).convert("RGB")
                    pil_img.thumbnail((1200, 1200)) 
                    out_img = io.BytesIO()
                    pil_img.save(out_img, format="JPEG", quality=75)
                    contenido_final = out_img.getvalue()
                    mime_final = "image/jpeg"
                except Exception:
                    contenido_final = img_buf.getvalue()
                    mime_final = f.mimetype or "image/jpeg"

                db.session.add(Foto(registro_id=reg.id, nombre=nombre, mime=mime_final, contenido=contenido_final))

    db.session.commit()
    if not edit_id: log_auditoria(session.get('username'), "CREACION", f"Creó registro #{reg.id} de {tipo} para PV {reg.pv}")
    return reg.id

# ------------------------------------------------------------------
# Exportación a Excel (.xlsx) / Failsafe
# ------------------------------------------------------------------

def _llenar_hoja(ws, registros):
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    header_fill = PatternFill(start_color="002D62", end_color="002D62", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    ws.append(HEADERS)
    for col in range(1, len(HEADERS) + 1):
        c = ws.cell(row=1, column=col)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center")

    for reg in registros:
        ws.append(reg.to_row())
        estado_cell = ws.cell(row=ws.max_row, column=45) 
        if reg.estado == "CONFORME": estado_cell.font = Font(color="2E7D32", bold=True)
        elif reg.estado == "RECLAMO CLIENTE": estado_cell.font = Font(color="EF6C00", bold=True)
        else: estado_cell.font = Font(color="C62828", bold=True)

    for col in range(1, len(HEADERS) + 1): ws.column_dimensions[get_column_letter(col)].width = 15
    ws.freeze_panes = "A2"

def generar_excel_bytes(tipo):
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws1 = wb.active
        
        if tipo == "reclamo": ws1.title = "Reclamos de Clientes"
        elif tipo == "terminado": ws1.title = "Producto Terminado"
        else: ws1.title = "Proceso (En Línea)"
        
        try:
            registros = Registro.query.filter_by(tipo=tipo, activo=True).order_by(Registro.id.asc()).all()
        except Exception:
            db.session.rollback()
            registros = [] 

        _llenar_hoja(ws1, registros)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
    except ImportError:
        import csv
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=';')
        writer.writerow(HEADERS)
        try:
            registros = Registro.query.filter_by(tipo=tipo, activo=True).order_by(Registro.id.asc()).all()
            for reg in registros: writer.writerow(reg.to_row())
        except Exception:
            db.session.rollback()
        out = io.BytesIO()
        out.write(b'\xef\xbb\xbf')
        out.write(buf.getvalue().encode('utf-8'))
        out.seek(0)
        return out

def generar_excel_alertas_bytes():
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws1 = wb.active
        ws1.title = "Alertas Emitidas"
        
        logs = AlertaLog.query.order_by(desc(AlertaLog.id)).all()
        registros = []
        vistos = set()
        
        for log in logs:
            reg = Registro.query.get(log.registro_id)
            if reg and reg.activo:
                clave = f"{reg.pv}-{reg.modelo}-{reg.tipo}"
                if clave not in vistos:
                    vistos.add(clave)
                    registros.append(reg)
                    
        _llenar_hoja(ws1, registros[::-1])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
    except ImportError:
        import csv
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=';')
        writer.writerow(HEADERS)
        try:
            logs = AlertaLog.query.order_by(desc(AlertaLog.id)).all()
            vistos = set()
            registros = []
            for log in logs:
                reg = Registro.query.get(log.registro_id)
                if reg and reg.activo:
                    clave = f"{reg.pv}-{reg.modelo}-{reg.tipo}"
                    if clave not in vistos:
                        vistos.add(clave)
                        registros.append(reg)
            for reg in registros[::-1]: 
                writer.writerow(reg.to_row())
        except Exception:
            db.session.rollback()
        out = io.BytesIO()
        out.write(b'\xef\xbb\xbf')
        out.write(buf.getvalue().encode('utf-8'))
        out.seek(0)
        return out

# ------------------------------------------------------------------
# Certificado PDF Profesional (Grilla Dinámica y Marca de Agua)
# ------------------------------------------------------------------

def generar_pdf_certificado(reg: Registro, es_alerta=False):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from PIL import Image as PILImage, ImageEnhance
    from reportlab.platypus import Image as RLImage
    from reportlab.lib.utils import ImageReader

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm, leftMargin=15*mm, rightMargin=15*mm)
    styles = getSampleStyleSheet()
    normal = styles["Normal"]

    def add_watermark(canvas, doc):
        canvas.saveState()
        img_path = os.path.join(BASE_DIR, "static", "logo.jpg")
        if os.path.exists(img_path):
            try:
                pil_img = PILImage.open(img_path).convert("RGBA")
                alpha = pil_img.split()[3]
                alpha = ImageEnhance.Brightness(alpha).enhance(0.12)
                pil_img.putalpha(alpha)
                img_io = io.BytesIO()
                pil_img.save(img_io, format='PNG')
                img_io.seek(0)
                watermark = ImageReader(img_io)
                page_width = doc.pagesize[0]
                page_height = doc.pagesize[1]
                img_w = 140 * mm
                img_h = img_w * (pil_img.height / pil_img.width)
                canvas.translate(page_width/2, page_height/2)
                canvas.rotate(45)
                canvas.drawImage(watermark, -img_w/2, -img_h/2, width=img_w, height=img_h, mask='auto')
            except:
                pass
        canvas.restoreState()

    elems = []
    if es_alerta:
        titulo = "ALERTA DE CALIDAD - PRODUCTO NO CONFORME"
        color_cabecera = colors.HexColor("#C62828") 
    else:
        if reg.tipo == "reclamo": titulo = "INFORME DE RECLAMO DE CLIENTE"
        elif reg.tipo == "terminado": titulo = "CERTIFICADO DE INSPECCIÓN DE PRODUCTO TERMINADO"
        else: titulo = "CERTIFICADO DE INSPECCIÓN DE CALIDAD (EN LÍNEA)"
        color_cabecera = colors.HexColor("#002D62") 

    title_p = Paragraph(f"<b>{titulo}</b>", ParagraphStyle(name="Title", fontSize=16, textColor=colors.white, alignment=1))
    t_header = Table([[title_p]], colWidths=[180*mm])
    t_header.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), color_cabecera), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 15), ('BOTTOMPADDING', (0,0), (-1,-1), 15)]))
    elems.append(t_header)
    elems.append(Spacer(1, 10))
    
    def bar_sec(txt): return Table([[Paragraph(f"<b>{txt}</b>", ParagraphStyle(name="SH", fontSize=11, textColor=colors.white))]], colWidths=[180*mm], style=TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#455A64")), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    elems.append(bar_sec("1. DATOS DE TRAZABILIDAD"))
    elems.append(Spacer(1, 5))
    p_bold = lambda t: Paragraph(f"<b>{t}</b>", normal)
    p_val = lambda t: Paragraph(str(t), normal)
    
    if reg.tipo in ["reclamo", "terminado"]:
        dia_lbl = "Día de Reclamo" if reg.tipo == "reclamo" else "Día de Control"
        cliente_lbl = "Cliente / Obra" if reg.tipo == "reclamo" else "Cliente"
        datos_tabla = [
            [p_bold(dia_lbl), p_val(reg.fecha or "-"), p_bold("Operario / Resp."), p_val(reg.resp or "-")],
            [p_bold(cliente_lbl), p_val(reg.cliente or "-"), p_bold("Etiqueta"), p_val(reg.etiqueta or "-")],
            [p_bold("Pedido Venta (PV)"), p_val(reg.pv or "-"), p_bold("Presupuesto"), p_val(reg.ppto or "-")],
            [p_bold("Modelo / Núcleo"), p_val(f"{reg.modelo or '-'} / {reg.nucleo or '-'}"), p_bold("Motivo / Defecto"), p_val(reg.defecto_reclamo or "-")],
            [p_bold("m² Controlados"), p_val(f"{reg.m2_controlados} m²" if reg.m2_controlados is not None else "-"), p_bold("m² Rechazados"), p_val(f"{reg.m2_rechazados} m²" if reg.m2_rechazados is not None else "-")],
            [p_bold("Largo de Panel"), p_val(f"{reg.largo} m" if reg.largo else "-"), "", ""],
        ]
    else:
        datos_tabla = [
            [p_bold("Fecha Fab."), p_val(reg.fecha or "-"), p_bold("Hora / Resp."), p_val(f"{reg.hora_control or '-'} / {reg.resp or '-'} ")],
            [p_bold("Pedido Venta (PV)"), p_val(reg.pv or "-"), p_bold("Presupuesto"), p_val(reg.ppto or "-")],
            [p_bold("Cliente / Destino"), p_val(reg.cliente or "-"), p_bold("Modelo / Núcleo"), p_val(f"{reg.modelo or '-'} / {reg.nucleo or '-'} ")],
            [p_bold("Reposo / Densidad"), p_val(f"{reg.reposo} hs / {reg.densidad} kg/m³"), p_bold("Velocidad / Largo"), p_val(f"{reg.vel} m/min / {reg.largo} m")],
        ]
        
    t1 = Table(datos_tabla, colWidths=[40*mm, 50*mm, 40*mm, 50*mm])
    t1.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CFD8DC")), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#ECEFF1")), ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#ECEFF1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 6)]))
    elems.append(t1)
    elems.append(Spacer(1, 10))

    if not es_alerta:
        elems.append(bar_sec("2. RESULTADOS DE METROLOGÍA"))
        elems.append(Spacer(1, 5))
        e_str = f"{reg.prom_e} mm"
        if reg.e1 or reg.e2 or reg.e3: e_str += f"\n(e1:{reg.e1}, e2:{reg.e2}, e3:{reg.e3})"
        metrologia = [[p_bold("Aspecto Visual"), p_val(reg.aspecto or "-"), p_bold("Ancho Útil"), p_val(f"{reg.ancho} mm")], [p_bold("Espesor Conf. (E)"), p_val(f"{reg.E} mm"), p_bold("Espesor Prom. (e)"), p_val(e_str)]]
        
        if reg.modelo and (reg.modelo.startswith("MR") or reg.modelo.startswith("FR")): 
            if reg.e_c is not None: metrologia.append([p_bold("E+C (Esp. + Cresta)"), p_val(f"{reg.e_c} mm"), "", ""])
            
        texto_gap = "Gap de Foil" if reg.modelo and reg.modelo.startswith("FR") else "Gap de Chapa"
        if reg.modelo and (reg.modelo.startswith("MC") or reg.modelo.startswith("CW")):
            metrologia.append([p_bold("Encastre Macho"), p_val(f"Int: {reg.hmi} / Ext: {reg.hme}"), p_bold("Encastre Hembra"), p_val(f"Int: {reg.hhi} / Ext: {reg.hhe}")])
            metrologia.append([p_bold(f"{texto_gap}"), p_val(f"Int: {reg.gci} / Ext: {reg.gce} mm"), p_bold("Enrase (R)"), p_val(f"{reg.r} mm")])
            
            escuadra_val_str = "-"
            if reg.escuadra is not None and reg.escuadra > 0:
                deg = int(reg.escuadra)
                mnt = int(round((reg.escuadra - deg) * 100))
                escuadra_val_str = f"{deg}º {mnt:02d}'"
                
            if reg.modelo.startswith("MC"): metrologia.append([p_bold("Escuadra (ºP)"), p_val(escuadra_val_str), "", ""])
        else:
            metrologia.append([p_bold(f"{texto_gap} (Gc)"), p_val(f"{reg.gc} mm"), p_bold("Enrase (R)"), p_val(f"{reg.r} mm")])
            metrologia.append([p_bold("Gap de Núcleo (Gn)"), p_val(f"{reg.gn} mm"), "", ""])
                
        if reg.modelo and reg.modelo.startswith("FR"): metrologia.append([p_bold("R1 (Cresta Vacía)"), p_val(f"{reg.rc1} mm"), p_bold("R2 (Cresta Llena)"), p_val(f"{reg.rc2} mm")])
        if reg.modelo in ["MC120", "MC150", "MC180", "MC200"]: metrologia.append([p_bold("Mediciones N (1-5)"), p_val(f"{reg.n1}, {reg.n2}, {reg.n3}, {reg.n4}, {reg.n5}"), p_bold("Mediciones N (6-9)"), p_val(f"{reg.n6}, {reg.n7}, {reg.n8}, {reg.n9}")])

        t2 = Table(metrologia, colWidths=[40*mm, 50*mm, 40*mm, 50*mm])
        t2.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CFD8DC")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECEFF1")), ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#ECEFF1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 6)]))
        elems.append(t2)
        elems.append(Spacer(1, 15))
    else:
        elems.append(bar_sec("2. DICTAMEN Y NOVEDADES"))
        elems.append(Spacer(1, 5))

    if reg.estado == "CONFORME": estado_color, bg_color = colors.HexColor("#2E7D32"), colors.HexColor("#E8F5E9")
    elif reg.estado == "RECLAMO CLIENTE": estado_color, bg_color = colors.HexColor("#EF6C00"), colors.HexColor("#FFF3E0")
    else: estado_color, bg_color = colors.HexColor("#C62828"), colors.HexColor("#FFEBEE")
    
    dictamen_data = [
        [Paragraph(f"<font size=14 color='{estado_color.hexval()}'><b>DICTAMEN: {reg.estado}</b></font>", normal)],
        [Spacer(1, 2)],
        [Paragraph(f"<b>Desvíos Detectados:</b> {html.escape(reg.desvios or 'Ninguno.')}", normal)],
        [Paragraph(f"<b>Observaciones:</b> {html.escape(reg.obs or 'Ninguna.')}", normal)]
    ]
    t_dictamen = Table(dictamen_data, colWidths=[176*mm])
    t_dictamen.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1.5, estado_color), ('BACKGROUND', (0,0), (-1,-1), bg_color), ('PADDING', (0,0), (-1,-1), 12), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
    elems.append(t_dictamen)

    if reg.fotos:
        elems.append(Spacer(1, 15))
        elems.append(bar_sec(f"{'2' if es_alerta else '3'}. EVIDENCIA FOTOGRÁFICA"))
        elems.append(Spacer(1, 5))
        filas_fotos, fila_actual = [], []
        for foto in reg.fotos:
            try:
                img_buf = io.BytesIO(foto.contenido)
                pil_img = PILImage.open(img_buf).convert("RGB")
                pil_img.thumbnail((800, 800))
                max_w, max_h = 42*mm, 42*mm
                w, h = pil_img.size
                ratio = min(max_w/w, max_h/h)
                out_img = io.BytesIO()
                pil_img.save(out_img, format="JPEG", quality=85)
                out_img.seek(0)
                rl_img = RLImage(out_img, width=w*ratio, height=h*ratio)
                lbl = Paragraph(f"<para align=center><font size=7 color='#546E7A'>{html.escape(foto.nombre)}</font></para>", normal)
                fila_actual.append([rl_img, Spacer(1, 2), lbl])
                if len(fila_actual) == 4:
                    filas_fotos.append(fila_actual)
                    fila_actual = []
            except Exception: continue
                
        if fila_actual: 
            while len(fila_actual) < 4: fila_actual.append("")
            filas_fotos.append(fila_actual)
            
        if filas_fotos:
            t_fotos = Table(filas_fotos, colWidths=[45*mm, 45*mm, 45*mm, 45*mm])
            t_fotos.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")), ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CFD8DC")), ('PADDING', (0,0), (-1,-1), 4)]))
            elems.append(t_fotos)

    doc.build(elems, onFirstPage=add_watermark, onLaterPages=add_watermark)
    buf.seek(0)
    return buf

# ------------------------------------------------------------------
# HTML (Interfaz Premium Web)
# ------------------------------------------------------------------

HTML_MAIN = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
<title>Control de Calidad - Kingspan LTN</title>
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#002D62">
<style>
  :root { --primary: #002D62; --secondary: #455A64; --success: #2E7D32; --danger: #C62828; --bg-color: #F0F4F8; --card-bg: #FFFFFF; --border: #CFD8DC; --text-main: #263238; --req-color: #D32F2F; }
  * { box-sizing: border-box; }
  body { font-family: 'Segoe UI', Roboto, Arial, sans-serif; margin: 0; padding: 0; background: var(--bg-color); color: var(--text-main); }
  .login-wrapper { display:flex; justify-content:center; align-items:center; height:100vh; background: var(--primary); padding:20px; }
  .login-box { background:white; padding: 40px 30px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.3); width:100%; max-width:400px; text-align:center; }
  .login-box h2 { color: var(--primary); margin-top:0; margin-bottom:25px; font-weight:700; font-size: 20px; letter-spacing: 1px; }
  .login-box input { width: 100%; margin-bottom: 15px; padding: 14px; border: 1px solid var(--border); border-radius: 6px; font-size:14px; outline:none; transition: border 0.3s, box-shadow 0.3s; }
  .login-box input:focus { border-color: var(--primary); box-shadow: 0 0 5px rgba(0,45,98,0.2); }
  .login-box button { width: 100%; padding: 15px; background: var(--primary); color: white; border: none; border-radius: 6px; font-weight:bold; cursor:pointer; font-size:15px; letter-spacing: 1px; transition: background 0.3s; margin-top: 10px;}
  .login-box button:hover { background: #001f45; }
  .app-wrapper { padding: 20px 15px; }
  .app-container { max-width: 1050px; margin: 0 auto; background: var(--card-bg); border-radius: 10px; box-shadow: 0 8px 25px rgba(0,0,0,0.08); overflow: hidden; }
  .user-bar { background: var(--secondary); color: white; padding: 10px 20px; font-size: 13px; display: flex; justify-content: space-between; align-items: center; }
  .user-bar a { color: #FFF; text-decoration: none; font-weight: bold; background: rgba(255,255,255,0.2); padding: 5px 12px; border-radius: 6px; transition: background 0.3s; }
  .user-bar a:hover { background: rgba(255,255,255,0.3); }
  .excel-header { background: #FFFFFF; color: var(--primary); border-bottom: 3px solid var(--primary); padding: 30px 20px; text-align: center; }
  .excel-header h1 { margin:0; font-size: 24px; font-weight: 800; letter-spacing: 1px; }
  .excel-header h2 { margin: 8px 0 0 0; font-size: 15px; font-weight: 500; color: var(--secondary); }
  .model-selector-bar { background: #F8FAFC; padding: 15px 20px; border-bottom: 1px solid var(--border); text-align: center; }
  .model-selector-bar select { padding: 10px; font-size: 15px; font-weight: bold; border-radius: 6px; border: 1px solid var(--primary); color: var(--primary); outline: none; background: white; cursor: pointer; }
  .toolbar { background: #FFFFFF; padding: 15px 20px; border-bottom: 1px solid var(--border); display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; align-items: center; }
  .tab-btn { background: #ECEFF1; border: 1px solid transparent; color: var(--secondary); padding: 10px 18px; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; text-decoration: none; display: inline-block; transition: all 0.2s; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  .tab-btn:hover { background: #CFD8DC; }
  .tab-btn.active { background: var(--primary) !important; color: white !important; box-shadow: 0 4px 10px rgba(0,45,98,0.3); }
  .btn-download { background: var(--success); color: white; }
  .btn-download:hover { background: #1B5E20; }
  .btn-download[style*="display: none"] { display: none !important; }
  .table-scroll { width: 100%; overflow-x: auto; padding: 20px; }
  table.sheet-table { width: 100%; min-width: 800px; border-collapse: separate; border-spacing: 0; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.02); }
  table.sheet-table td, table.sheet-table th { border-bottom: 1px solid var(--border); border-right: 1px solid var(--border); padding: 12px; font-size: 14px; }
  table.sheet-table tr:last-child td { border-bottom: none; }
  table.sheet-table td:last-child, table.sheet-table th:last-child { border-right: none; }
  .sec-header { background: #E3F2FD; color: var(--primary); font-weight: 700; text-align: left; font-size: 15px; padding: 14px 12px !important; }
  .col-label { background: #F8FAFC; font-weight: 600; color: var(--secondary); width: 25%; }
  .req-mark { color: var(--req-color); font-weight: bold; margin-left: 3px; }
  .excel-input, .excel-select { width: 100%; border: 1px solid #B0BEC5; padding: 10px; font-size: 14px; border-radius: 6px; outline:none; transition: border 0.3s, box-shadow 0.3s; box-shadow: inset 0 1px 3px rgba(0,0,0,0.04); background: white; }
  .excel-input:focus, .excel-select:focus { border-color: var(--primary); box-shadow: 0 0 5px rgba(0,45,98,0.2); }
  .excel-input { text-align: right; }
  .excel-input[type="datetime-local"], .excel-input[type="time"], .excel-input[type="text"] { text-align: left; }
  .excel-input.is-invalid, .excel-select.is-invalid { border-color: var(--req-color) !important; background: #FFEBEE !important; }
  .auto-prom { background: #E8F5E9 !important; color: var(--success) !important; font-weight: bold; border-color: #81C784; }
  .action-bar { padding: 25px; background: #FFFFFF; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 15px; box-shadow: 0 -4px 10px rgba(0,0,0,0.02); }
  .btn-save-excel { background: var(--primary); color: white; border: none; padding: 18px; font-size: 16px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%; text-transform: uppercase; letter-spacing: 1px; box-shadow: 0 4px 15px rgba(0,45,98,0.3); transition: transform 0.1s, background 0.3s; }
  .btn-save-excel:hover { background: #001f45; }
  .btn-save-excel:active { transform: scale(0.98); }
  .btn-save-excel:disabled { background: #9E9E9E; box-shadow: none; cursor: not-allowed; transform: none; }
  .card { border: 1px solid var(--border); padding: 25px; margin-bottom: 20px; border-radius: 8px; background: var(--card-bg); box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
  .card h3 { margin: 0 0 18px 0; font-size: 16px; color: var(--primary); border-bottom: 2px solid #E3F2FD; padding-bottom: 10px; }
  .pagination { display: flex; justify-content: center; gap: 10px; margin-top: 15px; align-items: center; font-size: 14px; font-weight: bold; color: var(--primary); }
  .btn-small { padding: 6px 12px; font-size: 12px; cursor: pointer; border-radius: 5px; border: 1px solid var(--border); background: white; font-weight:bold; transition: background 0.2s; }
  .btn-small:hover { background: #F5F7FA; }
  .btn-admin-edit { background: #E3F2FD; color: #002D62; border: 1px solid #90CAF9; padding: 6px 14px; border-radius: 6px; font-weight: bold; box-shadow: 0 1px 3px rgba(0,0,0,0.05); display: flex; align-items: center; gap: 5px; cursor: pointer; transition: 0.2s; }
  .btn-admin-edit:hover { background: #BBDEFB !important; }
  .btn-admin-del { background: #FFEBEE; color: #C62828; border: 1px solid #EF9A9A; padding: 6px 14px; border-radius: 6px; font-weight: bold; box-shadow: 0 1px 3px rgba(0,0,0,0.05); display: flex; align-items: center; gap: 5px; cursor: pointer; transition: 0.2s; }
  .btn-admin-del:hover { background: #FFCDD2 !important; }
  .btn-admin-special { display: block; width: 100%; background: #002D62; color: white; text-align: center; padding: 16px; font-size: 15px; font-weight: bold; text-decoration: none; border-radius: 8px; margin-bottom: 20px; border: 2px solid #001f45; box-shadow: 0 4px 12px rgba(0,0,0,0.15); transition: background 0.3s; }
  .btn-admin-special:hover { background: #001f45; }
  .perm-box { display: flex; flex-wrap: wrap; gap: 15px; background: #F8FAFC; padding: 10px 15px; border-radius: 6px; border: 1px solid #CFD8DC; font-size: 14px; font-weight: bold; color: var(--secondary); align-items: center; flex: 2; }
  .perm-box label { display: flex; align-items: center; gap: 5px; cursor: pointer; }
  .perm-box input { width: 16px !important; height: 16px; margin: 0 !important; cursor: pointer; }

  @media (max-width: 768px) {
    .app-wrapper { padding: 10px 5px; }
    .toolbar { flex-direction: column; gap: 5px; }
    .tab-btn { width: 100%; text-align: center; margin-left: 0 !important; }
    .model-selector-bar { display: flex; flex-direction: column; align-items: center; }
    .model-selector-bar select { width: 100%; margin-top: 10px; }
    .table-scroll { padding: 5px; margin-top: 5px; }
    table.form-table { min-width: 100%; border: none; box-shadow: none; background: transparent; }
    table.form-table > tbody > tr { display: flex; flex-direction: column; margin-bottom: 12px; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--card-bg); box-shadow: 0 2px 6px rgba(0,0,0,0.04); }
    table.form-table > tbody > tr > th.sec-header { display: block; width: 100%; border-bottom: none; }
    table.form-table > tbody > tr > td { display: block; width: 100% !important; border: none !important; }
    table.form-table > tbody > tr > td.col-label { background: #F0F4F8; padding: 10px 12px 4px 12px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
    table.form-table > tbody > tr > td:not(.col-label) { padding: 0 12px 12px 12px; border-bottom: 1px solid #E0E0E0 !important; }
    table.form-table > tbody > tr > td:last-child { border-bottom: none !important; }
    #wrapper_gci_gce { flex-direction: column; gap: 8px; }
    #wrapper_gci_gce input { width: 100% !important; }
    table.form-table > tbody > tr[style*="display: none"] { display: none !important; }
    .history-table td { white-space: nowrap; }
    .history-table td:last-child { white-space: normal; }
    #seccion_admin .card div[style*="display:grid"] { grid-template-columns: 1fr 1fr !important; }
    .perm-box { flex-direction: column; align-items: flex-start; gap: 8px; }
  }
</style>
</head>
<body>

{% if not current_user %}
<div class="login-wrapper">
  <div class="login-box">
    <h2>Sistema de Calidad</h2>
    <form action="/login" method="POST" id="formLogin">
      <input type="text" id="loginUser" name="username" placeholder="Usuario" required autocomplete="off">
      <div style="position:relative; width:100%; margin-bottom:15px; display:flex; align-items:center;">
          <input type="password" id="loginPass" name="password" placeholder="Contraseña" required autocomplete="new-password" style="width:100%; padding-right:40px; margin-bottom:0; box-sizing:border-box;">
          <span onclick="togglePassword('loginPass')" title="Mostrar/Ocultar" style="position:absolute; right:12px; cursor:pointer; font-size:18px; color:var(--secondary); user-select:none;">👁️</span>
      </div>
      <button type="submit" id="btnLoginSubmit">INICIAR SESIÓN</button>
    </form>
    {% if error_login %}
    <div style="color:var(--danger); margin-top:15px; font-size:14px; font-weight:bold;">{{ error_login }}</div>
    {% endif %}
  </div>
</div>
<script>
  function togglePassword(inputId) {
      var input = document.getElementById(inputId);
      if (input && input.type === "password") { input.type = "text"; } 
      else if (input) { input.type = "password"; }
  }
  window.onload = function() {
      try {
          var lu = document.getElementById("loginUser");
          var lp = document.getElementById("loginPass");
          if(lu) lu.value = "";
          if(lp) lp.value = "";
      } catch(e) {}
  };
  document.addEventListener('keypress', function (e) {
      if (e.key === 'Enter') {
          var btn = document.getElementById('btnLoginSubmit');
          if (btn && document.activeElement.tagName === "INPUT") btn.click();
      }
  });
</script>
{% else %}
<div class="app-wrapper">
<div class="app-container">
  <div class="user-bar">
    <div>Operador Activo: <b>{{ current_user }}</b> ({{ current_rol }})</div>
    <a href="/logout">🚪 Cerrar Sesión</a>
  </div>

  <div class="excel-header">
    <h1>DEPARTAMENTO DE CALIDAD</h1>
    <h2 id="txt_subtitulo">Control de Calidad de Paneles</h2>
  </div>
  
  <div class="model-selector-bar">
      <label style="font-size:14px; font-weight:bold; color:var(--secondary); margin-right:10px;">LÍNEA / MODELO:</label>
      <select id="sel_modelo" class="excel-select" style="width:auto; display:inline-block;" onchange="verificarVisibilidadCampos()">
        <optgroup label="Aislacion de Piso (AP)">
          <option value="AP60">AP60 (60mm)</option><option value="AP100">AP100 (100mm)</option>
        </optgroup>
        <optgroup label="Classwall (CW)">
          <option value="CW40">CW40 (40mm)</option><option value="CW50">CW50 (50mm)</option>
          <option value="CW60">CW60 (60mm)</option><option value="CW80">CW80 (80mm)</option>
        </optgroup>
        <optgroup label="FoilRoof (FR)">
          <option value="FR10">FR10 (10mm)</option><option value="FR30">FR30 (30mm)</option>
          <option value="FR50">FR50 (50mm)</option>
        </optgroup>
        <optgroup label="MaxiRoof (MR)">
          <option value="MR30">MR30 (30mm)</option><option value="MR40">MR40 (40mm)</option>
          <option value="MR50">MR50 (50mm)</option><option value="MR60">MR60 (60mm)</option>
          <option value="MR80">MR80 (80mm)</option>
        </optgroup>
        <optgroup label="Megacold (MC)">
          <option value="MC30">MC30 (30mm)</option><option value="MC40">MC40 (40mm)</option>
          <option value="MC50" selected>MC50 (50mm)</option><option value="MC60">MC60 (60mm)</option>
          <option value="MC80">MC80 (80mm)</option><option value="MC100">MC100 (100mm)</option><option value="MC120">MC120 (120mm)</option>
          <option value="MC150">MC150 (150mm)</option><option value="MC180">MC180 (180mm)</option><option value="MC200">MC200 (200mm)</option>
        </optgroup>
      </select>
  </div>

  <div class="toolbar">
    <button type="button" class="tab-btn active" id="btnHoja1" onclick="cambiarTipoHoja('proceso')">📋 Proceso Continuo</button>
    <button type="button" class="tab-btn" id="btnHoja2" onclick="cambiarTipoHoja('terminado')">📦 Producto Terminado</button>
    <button type="button" class="tab-btn" id="btnHoja3" onclick="cambiarTipoHoja('reclamo')">⚠️ Reclamo Cliente</button>
    <button type="button" class="tab-btn" id="btnBuscar" onclick="activarPestana('buscar')">🔍 Historial</button>
    
    <a href="javascript:void(0)" id="btn_descarga_excel" onclick="descargarExcelActual()" class="tab-btn btn-download" {% if current_rol != 'admin' and 'excel' not in current_permisos %}style="display:none;"{% endif %}>📊 Descargar Planilla</a>
    <a href="/descargar_alertas_excel" class="tab-btn btn-download" style="background: var(--danger); margin-left:10px; {% if current_rol != 'admin' and 'excel' not in current_permisos %}display:none;{% endif %}">🚨 Excel de Alertas</a>
    
    {% if current_rol == 'admin' %}
    <button type="button" class="tab-btn" id="btnAdmin" onclick="activarPestana('admin')" style="margin-left:auto;">⚙️ Panel Admin</button>
    {% endif %}
  </div>

  <div id="seccion_hoja">
    <input type="hidden" id="inp_edit_id" value="">
    <div class="table-scroll">
      <table class="sheet-table form-table">
        <tr><th colspan="4" class="sec-header" id="th_sec_a">1. TRAZABILIDAD Y PROCESO</th></tr>
        <tr>
          <td class="col-label" id="lbl_fecha">Fecha y Hora de Fabricación<span class="req-mark">*</span></td>
          <td><input type="datetime-local" id="inp_fecha" class="excel-input req-input req-both" value="{{ fecha_hoy }}"></td>
          <td class="col-label" id="lbl_hora_ctrl">Hora control de muestra<span class="req-mark">*</span></td>
          <td><input type="time" id="inp_hora_control" class="excel-input req-input req-proceso" value="{{ hora_hoy }}"></td>
        </tr>
        <tr>
          <td class="col-label fila-proceso-solo" id="lbl_reposo">Tiempo de Reposo [hs]<span class="req-mark">*</span></td>
          <td class="fila-proceso-solo"><input type="number" step="0.1" min="0" id="inp_reposo" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)"></td>
          <td class="col-label" id="lbl_resp">Responsable<span class="req-mark">*</span></td>
          <td id="td_resp_container">
            <select id="sel_resp" class="excel-select req-input req-both">
              <option value="">Seleccione...</option>
              {% for p in config.personal %}<option value="{{ p }}">{{ p }}</option>{% endfor %}
            </select>
          </td>
        </tr>
        <tr>
          <td class="col-label">Pedido de Venta (PV)<span class="req-mark">*</span></td>
          <td><input type="text" id="inp_pv" class="excel-input req-input req-both" placeholder="Ej: 123456" inputmode="numeric" maxlength="6" oninput="validarDigitos(this, 6)"></td>
          <td class="col-label">Presupuesto (Ppto)<span class="req-mark">*</span></td>
          <td><input type="text" id="inp_ppto" class="excel-input req-input req-both" placeholder="Ej: 123456" inputmode="numeric" maxlength="6" oninput="validarDigitos(this, 6)"></td>
        </tr>
        <tr>
          <td class="col-label" id="lbl_cliente">Cliente<span class="req-mark">*</span></td>
          <td><input type="text" id="inp_cliente" class="excel-input req-input req-both"></td>
          <td class="col-label">Núcleo<span class="req-mark">*</span></td>
          <td>
            <select id="sel_nucleo" class="excel-select req-input req-both">
              <option value="">Seleccione...</option>
              {% for n in config.nucleos %}<option value="{{ n }}">{{ n }}</option>{% endfor %}
            </select>
          </td>
        </tr>
        <tr id="fila_etiqueta" style="display:none; background:#E8EAF6;">
          <td class="col-label">Etiqueta<span class="req-mark">*</span></td>
          <td colspan="3"><input type="text" id="inp_etiqueta" class="excel-input req-input req-both" placeholder="Ej: 1234567890" inputmode="numeric" maxlength="10" oninput="validarDigitos(this, 10)"></td>
        </tr>
        <tr class="fila-proceso-solo">
          <td class="col-label">Densidad [kg/m³]<span class="req-mark">*</span></td>
          <td><input type="number" step="0.1" min="0" id="inp_densidad" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)"></td>
          <td class="col-label">Velocidad [m/min]<span class="req-mark">*</span></td>
          <td><input type="number" step="0.1" min="0" id="inp_vel" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)"></td>
        </tr>
        <tr>
          <td class="col-label">Largo de panel [m]<span class="req-mark">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_largo" class="excel-input req-input req-both" oninput="sanitizarPositivo(this)"></td>
          <td class="col-label">Aspecto Visual<span class="req-mark">*</span></td>
          <td id="td_aspecto_container">
            <select id="sel_aspecto" class="excel-select req-input req-both">
              <option value="OK">OK (Conforme)</option>
              <option value="NC">NC (No Conforme)</option>
            </select>
          </td>
        </tr>
        <tr id="fila_m2" style="display:none; background:#E8EAF6;">
          <td class="col-label">m² Controlados<span class="req-mark">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_m2_controlados" class="excel-input req-input req-both" oninput="sanitizarPositivo(this)"></td>
          <td class="col-label">m² Rechazados<span class="req-mark">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_m2_rechazados" class="excel-input req-input req-both" oninput="sanitizarPositivo(this)"></td>
        </tr>

        <tr><th colspan="4" class="sec-header" id="th_sec_b">2. COTAS DIMENSIONALES Y DEFECTO</th></tr>
        <tr id="fila_defecto_reclamo" style="display:none; background:#FFF3E0;">
          <td class="col-label" style="color:var(--danger);">Motivo / Defecto<span class="req-mark">*</span></td>
          <td colspan="3">
            <select id="sel_tipo_defecto" class="excel-select req-input" style="border-color:var(--danger);">
              {% for d in defectos %}<option value="{{ d }}">{{ d }}</option>{% endfor %}
            </select>
          </td>
        </tr>
        <tr>
          <td class="col-label">Ancho útil [mm]<span class="req-mark">*</span></td>
          <td><input type="number" step="0.1" min="0" id="inp_ancho" class="excel-input req-input req-both" oninput="sanitizarPositivo(this)"></td>
          <td class="col-label">Espesor E [mm]<span class="req-mark">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_E" class="excel-input req-input req-both" oninput="sanitizarPositivo(this)"></td>
        </tr>
        <tr id="fila_e_c" style="display:none;">
          <td class="col-label">E+C (Espesor + Cresta) [mm]<span class="req-mark req-mark-proceso">*</span></td>
          <td><input type="number" step="0.1" min="0" id="inp_e_c" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)"></td>
          <td class="col-label" style="border:none;"></td>
          <td style="border:none;"></td>
        </tr>
        <tr>
          <td class="col-label">e1 [mm]<span class="req-mark req-mark-proceso">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_e1" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this); calcularPromedio();"></td>
          <td class="col-label">e2 [mm]<span class="req-mark req-mark-proceso">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_e2" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this); calcularPromedio();"></td>
        </tr>
        <tr>
          <td class="col-label">e3 [mm]<span class="req-mark req-mark-proceso">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_e3" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this); calcularPromedio();"></td>
          <td class="col-label">Media e [Auto]</td>
          <td><input type="text" id="inp_prom_e" class="excel-input auto-prom" readonly></td>
        </tr>
        
        <tr id="fila_escuadra" style="display:none;">
          <td class="col-label">Escuadra (ºP)<span class="req-mark req-mark-proceso">*</span></td>
          <td>
            <div style="display:flex; gap:8px;">
              <input type="text" id="inp_escuadra_deg" placeholder="Grados (º)" class="excel-input req-input req-proceso" inputmode="numeric" maxlength="2" oninput="validarDigitos(this, 2)" style="width:48%;">
              <input type="text" id="inp_escuadra_min" placeholder="Minutos (')" class="excel-input req-input req-proceso" inputmode="numeric" maxlength="2" oninput="validarDigitos(this, 2)" style="width:48%;">
            </div>
          </td>
          <td class="col-label" style="border:none;"></td>
          <td style="border:none;"></td>
        </tr>
        
        <tr id="fila_encastre_macho" style="display:none;">
          <td class="col-label">Hmi (Macho Int.)<span class="req-mark req-mark-proceso">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_hmi" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)"></td>
          <td class="col-label">Hme (Macho Ext.)<span class="req-mark req-mark-proceso">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_hme" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)"></td>
        </tr>
        <tr id="fila_encastre_hembra" style="display:none;">
          <td class="col-label">Hhi (Hembra Int.)<span class="req-mark req-mark-proceso">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_hhi" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)"></td>
          <td class="col-label">Hhe (Hembra Ext.)<span class="req-mark req-mark-proceso">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_hhe" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)"></td>
        </tr>
        <tr>
          <td class="col-label"><span id="txt_gap_label">Gap de Chapa</span> [mm]<span class="req-mark req-mark-proceso">*</span></td>
          <td>
            <div id="wrapper_gc"><input type="number" step="0.01" min="0" id="inp_gc" placeholder="Gc" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)"></div>
            <div id="wrapper_gci_gce" style="display:none; gap:8px;">
              <input type="number" step="0.01" min="0" id="inp_gci" placeholder="Int. (Gci)" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)" style="width:48%;">
              <input type="number" step="0.01" min="0" id="inp_gce" placeholder="Ext. (Gce)" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)" style="width:48%;">
            </div>
          </td>
          <td class="col-label">Gap de Núcleo (Gn)<span class="req-mark req-mark-proceso">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_gn" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)"></td>
        </tr>
        <tr>
          <td class="col-label">R (Enrase) [mm]<span class="req-mark req-mark-proceso">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_r" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)"></td>
          <td class="col-label" style="border:none;"></td>
          <td style="border:none;"></td>
        </tr>
        
        <tr id="fila_radios_foil" style="display:none;">
          <td class="col-label">R1 (Cresta Vacía) [mm]<span class="req-mark req-mark-proceso">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_rc1" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)"></td>
          <td class="col-label">R2 (Cresta Llena) [mm]<span class="req-mark req-mark-proceso">*</span></td>
          <td><input type="number" step="0.01" min="0" id="inp_rc2" class="excel-input req-input req-proceso" oninput="sanitizarPositivo(this)"></td>
        </tr>

        <tr id="fila_n1_n5" style="display:none;">
          <td class="col-label">Mediciones N (1-5) [mm]<span class="req-mark req-mark-proceso">*</span></td>
          <td colspan="3">
            <div style="display:flex; gap:8px;">
                <input type="number" step="0.1" id="inp_n1" placeholder="N1" class="excel-input req-input req-proceso">
                <input type="number" step="0.1" id="inp_n2" placeholder="N2" class="excel-input req-input req-proceso">
                <input type="number" step="0.1" id="inp_n3" placeholder="N3" class="excel-input req-input req-proceso">
                <input type="number" step="0.1" id="inp_n4" placeholder="N4" class="excel-input req-input req-proceso">
                <input type="number" step="0.1" id="inp_n5" placeholder="N5" class="excel-input req-input req-proceso">
            </div>
          </td>
        </tr>
        <tr id="fila_n6_n9" style="display:none;">
          <td class="col-label">Mediciones N (6-9) [mm]<span class="req-mark req-mark-proceso">*</span></td>
          <td colspan="3">
             <div style="display:flex; gap:8px;">
                <input type="number" step="0.1" id="inp_n6" placeholder="N6" class="excel-input req-input req-proceso">
                <input type="number" step="0.1" id="inp_n7" placeholder="N7" class="excel-input req-input req-proceso">
                <input type="number" step="0.1" id="inp_n8" placeholder="N8" class="excel-input req-input req-proceso">
                <input type="number" step="0.1" id="inp_n9" placeholder="N9" class="excel-input req-input req-proceso">
             </div>
          </td>
        </tr>
      </table>
    </div>
    <div class="action-bar">
      
      <div id="div_dictamen_manual" style="background:#F5F5F5; padding:15px; border-radius:8px; border:2px solid #B0BEC5; transition: 0.3s;">
        <label style="font-size:15px; font-weight:800; color:var(--primary);">⚖️ DICTAMEN FINAL DEL CONTROL:<span class="req-mark">*</span></label>
        <select id="sel_estado_manual" class="excel-select req-input req-both" style="margin-top:8px; font-weight:bold; font-size:16px; border: 2px solid #B0BEC5; color:var(--primary); cursor:pointer;" onchange="cambiarColorDictamen(this)">
          <option value="">-- ELIJA EL ESTADO FINAL --</option>
          <option value="CONFORME">✅ CONFORME</option>
          <option value="NO CONFORME">❌ NO CONFORME</option>
        </select>
        <p style="margin:6px 0 0 0; font-size:12px; color:var(--secondary); font-weight:bold;">Tú decides el estado final del registro. Ya no se calculará automáticamente.</p>
      </div>

      <div>
        <label style="font-size:14px; font-weight:700; color:var(--primary);">📷 Evidencia Fotográfica (Hasta 12 fotos):</label><br>
        <input type="file" id="inp_fotos" accept="image/*" multiple style="margin-top:10px; font-size:14px; padding: 10px; border: 1px dashed var(--secondary); border-radius: 6px; width: 100%; background: #FAFAFA;">
        <span id="lbl_cant_fotos" style="font-size:12px; color:var(--secondary); font-weight:600; margin-left:5px;"></span>
      </div>
      <div>
        <label style="font-size:14px; font-weight:700; color:var(--primary);">📝 Observaciones Adicionales:</label>
        <textarea id="inp_obs" rows="3" style="width:100%; padding:12px; font-size:14px; border:1px solid var(--border); border-radius:6px; margin-top:8px; resize:vertical; outline:none; box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);"></textarea>
      </div>
      
      <div id="msg_solo_lectura" style="display:none; padding:15px; background:#FFF3E0; color:#EF6C00; border-radius:6px; font-weight:bold; text-align:center;">⚠️ Acceso restringido. No tienes permisos para esta acción.</div>
      <button type="button" class="btn-save-excel" id="btn_guardar_hoja" onclick="ejecutarGuardado()">💾 GUARDAR REGISTRO</button>
      <button type="button" class="tab-btn" id="btn_cancelar_edicion" style="display:none; width:100%; margin-top:5px; text-align:center; background:#EF9A9A; color:#C62828;" onclick="cancelarEdicion()">❌ CANCELAR EDICIÓN</button>
      
    </div>
  </div>

  <!-- HISTORIAL -->
  <div id="seccion_buscar" style="display:none; padding:20px;">
    <div class="card">
      <h3 id="txt_titulo_historial">🔍 Búsqueda de Mediciones (Proceso)</h3>
      <div style="display:flex; gap:10px; flex-wrap:wrap;">
        <input type="text" id="filtro_busqueda" placeholder="Buscar por PV o Cliente..." style="flex:1; padding:12px; font-size:14px; border:1px solid var(--border); border-radius:6px; outline:none; box-shadow: inset 0 1px 3px rgba(0,0,0,0.04);">
        <button type="button" class="tab-btn active" style="padding: 12px 25px;" onclick="cargarHistorial(1)">🔄 Refrescar</button>
      </div>
    </div>
    <div class="table-scroll" style="padding:0; margin-top:0;">
      <table class="sheet-table history-table">
        <thead><tr style="background:#E3F2FD; color:var(--primary);">
          <th>ID</th><th>Fecha</th><th>Modelo</th><th>PV</th><th>Cliente</th><th>Estado</th><th>Acciones</th>
        </tr></thead>
        <tbody id="tbodyHistorial"><tr><td colspan="7" style="text-align:center; padding:20px;">Cargando registros...</td></tr></tbody>
      </table>
    </div>
    <div class="pagination">
      <button class="tab-btn" id="btn_pag_prev" onclick="cambiarPagina(-1)">&laquo; Anterior</button>
      <span id="lbl_pagina_actual" style="background:#E3F2FD; padding: 6px 15px; border-radius: 20px;">Página 1</span>
      <button class="tab-btn" id="btn_pag_next" onclick="cambiarPagina(1)">Siguiente &raquo;</button>
    </div>
  </div>

  <!-- ADMIN -->
  {% if current_rol == 'admin' %}
  <div id="seccion_admin" style="display:none; padding:20px;">
    <div id="adminContenido">
      
      <div class="card" style="border: 2px solid #002D62; background: #E3F2FD;">
        <h3 style="color:#002D62; border-bottom: 2px solid #BBDEFB;">📊 Explorador Avanzado de Servidor</h3>
        <p style="font-size:14px; color:var(--secondary); margin-bottom: 15px;">Acceso directo a la base de datos cruda para extraer fotos originales y gestionar el almacenamiento.</p>
        <a href="/api/admin_dump?page=1" target="_blank" class="btn-admin-special">🛡️ ABRIR EXPLORADOR DE BASE DE DATOS</a>
      </div>

      <div class="card">
        <h3>👥 Gestión de Usuarios y Permisos</h3>
        <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:15px; align-items:center;">
          <input type="text" id="usr_name" placeholder="Nombre Usuario" class="excel-input" style="flex:1;">
          <div style="position:relative; flex:1; min-width: 150px;">
             <input type="password" id="usr_pass" placeholder="Contraseña" class="excel-input" style="width:100%; padding-right:35px; margin-bottom:0; box-sizing:border-box;">
             <span class="toggle-password" onclick="togglePassword('usr_pass')" title="Mostrar/Ocultar" style="position:absolute; right:10px; top:50%; transform:translateY(-50%); cursor:pointer; font-size:16px; user-select:none; z-index:10;">👁️</span>
          </div>
          <select id="usr_rol" class="excel-select" style="width:auto;" onchange="togglePermisosUI()">
              <option value="operador">Operador (Permisos Personalizados)</option>
              <option value="admin">Administrador (Acceso Total)</option>
          </select>
          
          <div id="div_permisos" class="perm-box">
             <label><input type="checkbox" id="chk_escribir" checked> Escribir</label>
             <label><input type="checkbox" id="chk_editar" checked> Editar</label>
             <label><input type="checkbox" id="chk_borrar"> Borrar</label>
             <label><input type="checkbox" id="chk_excel" checked> Bajar Excel</label>
          </div>
          
          <button type="button" class="tab-btn active" id="btn_guardar_usr" onclick="crearUsuario()">+ Guardar Usuario</button>
        </div>
        <div class="table-scroll" style="padding:0;">
          <table class="sheet-table">
            <thead style="background:#ECEFF1;"><tr><th>Usuario</th><th>Rol</th><th>Permisos (Si es operador)</th><th>Acción</th></tr></thead>
            <tbody id="tbodyUsuarios"></tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h3>📜 Auditoría del Sistema (Últimos 30 eventos)</h3>
        <button class="tab-btn" style="margin-bottom:15px;" onclick="cargarAuditoria()">🔄 Actualizar Log</button>
        <div class="table-scroll" style="padding:0; max-height:300px; overflow-y:auto; border-radius:8px;">
          <table class="sheet-table" style="font-size:13px; margin:0; border:none;">
            <thead style="position:sticky; top:0; background:#ECEFF1;"><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Detalle</th></tr></thead>
            <tbody id="tbodyAuditoria"></tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h3>📐 Calibración de Tolerancias</h3>
        <select id="sel_adm_mod" class="excel-select" style="width:auto; margin-bottom:20px; font-weight:bold;" onchange="cargarTolsAdmin()">
          <option value="MC50" selected>MC50</option>
          <option value="MC30">MC30</option><option value="MC40">MC40</option><option value="MC60">MC60</option>
          <option value="MC80">MC80</option><option value="MC100">MC100</option><option value="MC120">MC120</option>
          <option value="MC150">MC150</option><option value="MC180">MC180</option><option value="MC200">MC200</option>
          <option value="CW40">CW40</option><option value="CW50">CW50</option><option value="CW60">CW60</option><option value="CW80">CW80</option>
          <option value="MR30">MR30</option><option value="MR40">MR40</option><option value="MR50">MR50</option>
          <option value="FR10">FR10</option><option value="FR30">FR30</option><option value="FR50">FR50</option>
          <option value="AP60">AP60</option><option value="AP100">AP100</option>
        </select>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap:15px;">
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">e Mín:</label><input type="number" step="0.1" id="adm_e_min" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">e Máx:</label><input type="number" step="0.1" id="adm_e_max" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">E Mín:</label><input type="number" step="0.1" id="adm_E_min" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">E Máx:</label><input type="number" step="0.1" id="adm_E_max" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">Gc Máx:</label><input type="number" step="0.1" id="adm_gc_max" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">Gn Máx:</label><input type="number" step="0.1" id="adm_gn_max" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">R Máx:</label><input type="number" step="0.1" id="adm_r_max" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">Ancho Nom:</label><input type="number" step="1" id="adm_ancho_nom" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">Tol Ancho (±):</label><input type="number" step="0.5" id="adm_ancho_tol" class="excel-input"></div>
          <div style="grid-column: span 2; border-top: 1px dashed var(--border); padding-top: 15px; margin-top: 5px;">
             <label style="font-size:13px; color:var(--primary); font-weight:bold;">Tolerancia R1 / R2 (Foil):</label>
          </div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">R1/R2 Mín:</label><input type="number" step="0.1" id="adm_r_foil_min" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">R1/R2 Máx:</label><input type="number" step="0.1" id="adm_r_foil_max" class="excel-input"></div>
          <div style="grid-column: span 2; border-top: 1px dashed var(--border); padding-top: 15px; margin-top: 5px;">
             <label style="font-size:13px; color:var(--primary); font-weight:bold;">Tolerancias Especiales (MC / CW):</label>
          </div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">Escuadra Nom:</label><input type="number" step="0.1" id="adm_escuadra_nom" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">Escuadra Tol:</label><input type="number" step="0.1" id="adm_escuadra_tol" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">hmi Mín:</label><input type="number" step="0.1" id="adm_hmi_min" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">hmi Máx:</label><input type="number" step="0.1" id="adm_hmi_max" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">hme Mín:</label><input type="number" step="0.1" id="adm_hme_min" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">hme Máx:</label><input type="number" step="0.1" id="adm_hme_max" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">hhi Mín:</label><input type="number" step="0.1" id="adm_hhi_min" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">hhi Máx:</label><input type="number" step="0.1" id="adm_hhi_max" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">hhe Mín:</label><input type="number" step="0.1" id="adm_hhe_min" class="excel-input"></div>
          <div><label style="font-size:13px; color:var(--secondary); font-weight:600;">hhe Máx:</label><input type="number" step="0.1" id="adm_hhe_max" class="excel-input"></div>
        </div>
        <button type="button" class="tab-btn active" style="margin-top:20px; width:100%; padding:12px; font-size:15px;" onclick="guardarTolsAdmin()">💾 Guardar Tolerancias</button>
      </div>

      <div class="card">
        <h3>📋 Personal y Tipos de Núcleo</h3>
        <label style="font-size:14px; font-weight:600; color:var(--secondary);">Inspectores (separados por coma):</label>
        <textarea id="adm_txt_personal" rows="2" style="width:100%; font-size:14px; padding:12px; border-radius:6px; border:1px solid var(--border); margin-bottom:15px; box-shadow: inset 0 1px 3px rgba(0,0,0,0.04);"></textarea>
        <label style="font-size:14px; font-weight:600; color:var(--secondary);">Tipos de Núcleo (separados por coma):</label>
        <textarea id="adm_txt_nucleos" rows="2" style="width:100%; font-size:14px; padding:12px; border-radius:6px; border:1px solid var(--border); box-shadow: inset 0 1px 3px rgba(0,0,0,0.04);"></textarea>
        <button type="button" class="tab-btn active" style="margin-top:20px; width:100%; padding:12px; font-size:15px;" onclick="guardarListasAdmin()">💾 Guardar Listas</button>
      </div>
    </div>
  </div>
  {% endif %}
</div>
</div>

<script>
function togglePassword(inputId) {
    var input = document.getElementById(inputId);
    if (input && input.type === "password") { input.type = "text"; } 
    else if (input) { input.type = "password"; }
}

function togglePermisosUI() {
    var rol = document.getElementById("usr_rol").value;
    var divPerm = document.getElementById("div_permisos");
    if(rol === 'admin') {
        divPerm.style.opacity = '0.4';
        divPerm.style.pointerEvents = 'none';
    } else {
        divPerm.style.opacity = '1';
        divPerm.style.pointerEvents = 'auto';
    }
}

function cambiarColorDictamen(sel) {
    var div = document.getElementById("div_dictamen_manual");
    if(!div) return;
    if(sel.value === "CONFORME") {
        div.style.background = "#E8F5E9";
        div.style.borderColor = "#81C784";
        sel.style.borderColor = "#81C784";
    } else if (sel.value === "NO CONFORME") {
        div.style.background = "#FFEBEE";
        div.style.borderColor = "#E57373";
        sel.style.borderColor = "#E57373";
    } else {
        div.style.background = "#F5F5F5";
        div.style.borderColor = "#B0BEC5";
        sel.style.borderColor = "#B0BEC5";
    }
}

try {
  var CONFIG = {{ config_json | safe }};
  var registrosHistorial = [];
  var modoActual = "proceso";
  var paginaActual = 1;
  var usrRol = '{{ current_rol }}';
  var usrPermisos = '{{ current_permisos }}';
  var isAdmin = usrRol === 'admin';
  var canWrite = isAdmin || usrPermisos.includes('escribir');
  var canEdit = isAdmin || usrPermisos.includes('editar');
  var canDelete = isAdmin || usrPermisos.includes('borrar');

  var filtroInput = document.getElementById('filtro_busqueda');
  if(filtroInput) filtroInput.addEventListener('input', filtrarHistorial);

  function validarDigitos(el, maxLen) {
    if(!el) return;
    if (el.value.length > maxLen) {
        el.value = el.value.substring(0, maxLen);
    }
    if (el.value !== "" && !/^\d+$/.test(el.value)) {
        el.classList.add("is-invalid");
    } else {
        el.classList.remove("is-invalid");
    }
  }

  function sanitizarPositivo(el) {
    if(!el) return;
    if (el.value < 0 || el.value.indexOf('-') !== -1) el.value = el.value.replace(/-/g, '');
    el.classList.remove("is-invalid");
  }

  function verificarVisibilidadCampos() {
    var selMod = document.getElementById("sel_modelo");
    if(!selMod) return;
    var mod = selMod.value;
    
    var txtGap = document.getElementById("txt_gap_label");
    if (txtGap) {
        if (mod.indexOf("FR") === 0) { txtGap.innerText = "Gap de Foil"; } 
        else { txtGap.innerText = "Gap de Chapa"; }
    }
    
    var filaRadios = document.getElementById("fila_radios_foil");
    if (filaRadios) {
        if (mod.indexOf("FR") === 0) { filaRadios.style.display = ""; } 
        else { 
            filaRadios.style.display = "none"; 
            if(document.getElementById("inp_rc1")) document.getElementById("inp_rc1").value = ""; 
            if(document.getElementById("inp_rc2")) document.getElementById("inp_rc2").value = ""; 
        }
    }

    var filaEC = document.getElementById("fila_e_c");
    if (filaEC) {
        if (mod.indexOf("MR") === 0 || mod.indexOf("FR") === 0) { filaEC.style.display = ""; } 
        else { 
            filaEC.style.display = "none"; 
            if(document.getElementById("inp_e_c")) document.getElementById("inp_e_c").value = ""; 
        }
    }

    var filaN1_5 = document.getElementById("fila_n1_n5");
    var filaN6_9 = document.getElementById("fila_n6_n9");
    if (filaN1_5 && filaN6_9) {
        if ((mod === "MC120" || mod === "MC150" || mod === "MC180" || mod === "MC200") && modoActual === "proceso") {
          filaN1_5.style.display = ""; filaN6_9.style.display = "";
        } else {
          filaN1_5.style.display = "none"; filaN6_9.style.display = "none";
          for(var i=1; i<=9; i++) { var el = document.getElementById("inp_n"+i); if(el) el.value = ""; }
        }
    }

    var wrapGc = document.getElementById("wrapper_gc");
    var wrapGciGce = document.getElementById("wrapper_gci_gce");
    var filaMacho = document.getElementById("fila_encastre_macho");
    var filaHembra = document.getElementById("fila_encastre_hembra");
    var filaEscuadra = document.getElementById("fila_escuadra");

    if (mod.indexOf("MC") === 0 || mod.indexOf("CW") === 0) {
      if(wrapGc) wrapGc.style.display = "none"; 
      if(document.getElementById("inp_gc")) document.getElementById("inp_gc").value = ""; 
      if(wrapGciGce) wrapGciGce.style.display = "flex";
      if(filaMacho) filaMacho.style.display = ""; 
      if(filaHembra) filaHembra.style.display = "";
      if(filaEscuadra && mod.indexOf("MC") === 0) { filaEscuadra.style.display = ""; }
      else { 
          if(filaEscuadra) { 
              filaEscuadra.style.display = "none"; 
              if(document.getElementById("inp_escuadra_deg")) document.getElementById("inp_escuadra_deg").value = ""; 
              if(document.getElementById("inp_escuadra_min")) document.getElementById("inp_escuadra_min").value = ""; 
          } 
      }
    } else {
      if(wrapGc) wrapGc.style.display = ""; 
      if(wrapGciGce) wrapGciGce.style.display = "none"; 
      if(document.getElementById("inp_gci")) document.getElementById("inp_gci").value = ""; 
      if(document.getElementById("inp_gce")) document.getElementById("inp_gce").value = "";
      
      if(filaMacho) filaMacho.style.display = "none"; 
      if(filaHembra) filaHembra.style.display = "none"; 
      if(document.getElementById("inp_hmi")) document.getElementById("inp_hmi").value = ""; 
      if(document.getElementById("inp_hme")) document.getElementById("inp_hme").value = "";
      if(document.getElementById("inp_hhi")) document.getElementById("inp_hhi").value = ""; 
      if(document.getElementById("inp_hhe")) document.getElementById("inp_hhe").value = "";
      if(filaEscuadra) { 
          filaEscuadra.style.display = "none"; 
          if(document.getElementById("inp_escuadra_deg")) document.getElementById("inp_escuadra_deg").value = ""; 
          if(document.getElementById("inp_escuadra_min")) document.getElementById("inp_escuadra_min").value = ""; 
      }
    }
  }

  function actualizarBotonDescarga() {
    var btn = document.getElementById("btn_descarga_excel");
    if(!btn) return;
    if (modoActual === "reclamo") { 
        btn.innerText = "📊 Descargar Planilla (Reclamos)"; btn.href = "/descargar_excel?tipo=reclamo"; 
    } else if (modoActual === "terminado") {
        btn.innerText = "📊 Descargar Planilla (PT)"; btn.href = "/descargar_excel?tipo=terminado"; 
    } else { 
        btn.innerText = "📊 Descargar Planilla (Proceso)"; btn.href = "/descargar_excel?tipo=proceso"; 
    }
  }

  function actualizarBotonesFormulario(modoEdit) {
      var btnGuardar = document.getElementById("btn_guardar_hoja");
      var msgLectura = document.getElementById("msg_solo_lectura");
      var inpFotos = document.getElementById("inp_fotos");
      var tienePermiso = modoEdit ? canEdit : canWrite;
      
      if (btnGuardar) {
          btnGuardar.innerText = modoEdit ? "🔄 ACTUALIZAR REGISTRO" : "💾 GUARDAR REGISTRO";
          btnGuardar.style.display = tienePermiso ? "block" : "none";
      }
      if (msgLectura) {
          msgLectura.style.display = tienePermiso ? "none" : "block";
          msgLectura.innerText = modoEdit 
              ? "⚠️ Acceso restringido. No tienes permisos para editar registros." 
              : "⚠️ Acceso restringido. No tienes permisos para crear nuevos registros.";
      }
      if (inpFotos) inpFotos.disabled = !tienePermiso;
  }

  function activarPestana(p) {
    var secHoja = document.getElementById("seccion_hoja");
    var secBuscar = document.getElementById("seccion_buscar");
    var secAdm = document.getElementById("seccion_admin");
    
    if(secHoja) secHoja.style.display = (p === 'hoja' ? 'block' : 'none');
    if(secBuscar) secBuscar.style.display = (p === 'buscar' ? 'block' : 'none');
    if(secAdm) secAdm.style.display = (p === 'admin' ? 'block' : 'none');
    
    var btnBuscar = document.getElementById("btnBuscar");
    var btnAdm = document.getElementById("btnAdmin");
    var btnHoja1 = document.getElementById("btnHoja1");
    var btnHoja2 = document.getElementById("btnHoja2");
    var btnHoja3 = document.getElementById("btnHoja3");
    
    if(btnBuscar) btnBuscar.className = p === 'buscar' ? 'tab-btn active' : 'tab-btn';
    if(btnAdm) btnAdm.className = p === 'admin' ? 'tab-btn active' : 'tab-btn';
    
    if (p === 'hoja') {
      if(btnHoja1) btnHoja1.className = modoActual === 'proceso' ? 'tab-btn active' : 'tab-btn';
      if(btnHoja2) btnHoja2.className = modoActual === 'terminado' ? 'tab-btn active' : 'tab-btn';
      if(btnHoja3) btnHoja3.className = modoActual === 'reclamo' ? 'tab-btn active' : 'tab-btn';
    } else {
      if(btnHoja1) btnHoja1.className = 'tab-btn';
      if(btnHoja2) btnHoja2.className = 'tab-btn';
      if(btnHoja3) btnHoja3.className = 'tab-btn';
    }
    
    if (p === 'buscar') cargarHistorial(1);
    if (p === 'admin') { cargarTolsAdmin(); cargarUsuariosAdmin(); cargarAuditoria(); }
  }

  function cambiarTipoHoja(tipo) {
    if (modoActual !== tipo) {
        resetearCeldas();
    }
    modoActual = tipo;
    activarPestana('hoja');
    
    var reqProcesoMarks = document.querySelectorAll('.req-mark-proceso');
    if (tipo === 'reclamo' || tipo === 'terminado') {
        for (var i=0; i<reqProcesoMarks.length; i++) reqProcesoMarks[i].style.display = 'none';
    } else {
        for (var i=0; i<reqProcesoMarks.length; i++) reqProcesoMarks[i].style.display = 'inline';
    }

    var filasProceso = document.querySelectorAll('.fila-proceso-solo');
    var filaDefecto = document.getElementById("fila_defecto_reclamo");
    var filaEtiqueta = document.getElementById("fila_etiqueta");
    var filaM2 = document.getElementById("fila_m2");
    var tdResp = document.getElementById("td_resp_container");
    var tdAspecto = document.getElementById("td_aspecto_container");
    
    var divDictamen = document.getElementById("div_dictamen_manual");
    var selDictamen = document.getElementById("sel_estado_manual");
    
    if (tipo === 'reclamo') {
      if(document.getElementById("txt_subtitulo")) document.getElementById("txt_subtitulo").innerText = "CONTROL DE RECLAMOS DE CLIENTES";
      if(document.getElementById("th_sec_a")) document.getElementById("th_sec_a").innerText = "1. DATOS DE RECLAMO";
      if(document.getElementById("th_sec_b")) document.getElementById("th_sec_b").innerText = "2. COTAS DIMENSIONALES Y DEFECTO";
      if(document.getElementById("lbl_fecha")) document.getElementById("lbl_fecha").innerHTML = "Día de Reclamo<span class='req-mark'>*</span>";
      if(document.getElementById("lbl_hora_ctrl")) document.getElementById("lbl_hora_ctrl").style.display = "none";
      if(document.getElementById("inp_hora_control")) document.getElementById("inp_hora_control").style.display = "none";
      if(document.getElementById("lbl_resp")) document.getElementById("lbl_resp").innerHTML = "Operario / Resp.<span class='req-mark'>*</span>";
      if(document.getElementById("lbl_cliente")) document.getElementById("lbl_cliente").innerHTML = "Cliente / Obra<span class='req-mark'>*</span>";
      if(document.getElementById("txt_titulo_historial")) document.getElementById("txt_titulo_historial").innerText = "🔍 Búsqueda de Mediciones (Reclamos)";
      
      for (var i=0; i<filasProceso.length; i++) filasProceso[i].style.display = 'none';
      if (tdResp) tdResp.colSpan = 3;
      if (tdAspecto) tdAspecto.colSpan = 3;
      if (filaDefecto) filaDefecto.style.display = '';
      if (filaEtiqueta) filaEtiqueta.style.display = '';
      if (filaM2) filaM2.style.display = '';
      if (divDictamen) divDictamen.style.display = 'none';
      
    } else if (tipo === 'terminado') {
      if(document.getElementById("txt_subtitulo")) document.getElementById("txt_subtitulo").innerText = "CONTROL DE PRODUCTO TERMINADO";
      if(document.getElementById("th_sec_a")) document.getElementById("th_sec_a").innerText = "1. DATOS DE PRODUCTO TERMINADO";
      if(document.getElementById("th_sec_b")) document.getElementById("th_sec_b").innerText = "2. COTAS DIMENSIONALES Y DEFECTO";
      if(document.getElementById("lbl_fecha")) document.getElementById("lbl_fecha").innerHTML = "Día de Control<span class='req-mark'>*</span>";
      if(document.getElementById("lbl_hora_ctrl")) document.getElementById("lbl_hora_ctrl").style.display = "none";
      if(document.getElementById("inp_hora_control")) document.getElementById("inp_hora_control").style.display = "none";
      if(document.getElementById("lbl_resp")) document.getElementById("lbl_resp").innerHTML = "Operario / Resp.<span class='req-mark'>*</span>";
      if(document.getElementById("lbl_cliente")) document.getElementById("lbl_cliente").innerHTML = "Cliente<span class='req-mark'>*</span>";
      if(document.getElementById("txt_titulo_historial")) document.getElementById("txt_titulo_historial").innerText = "🔍 Búsqueda de Mediciones (P. Terminado)";
      
      for (var i=0; i<filasProceso.length; i++) filasProceso[i].style.display = 'none';
      if (tdResp) tdResp.colSpan = 3;
      if (tdAspecto) tdAspecto.colSpan = 3;
      if (filaDefecto) filaDefecto.style.display = '';
      if (filaEtiqueta) filaEtiqueta.style.display = '';
      if (filaM2) filaM2.style.display = '';
      if (divDictamen) divDictamen.style.display = 'block';
      
    } else {
      if(document.getElementById("txt_subtitulo")) document.getElementById("txt_subtitulo").innerText = "Control de Calidad de Paneles (Proceso Continuo)";
      if(document.getElementById("th_sec_a")) document.getElementById("th_sec_a").innerText = "1. TRAZABILIDAD Y PROCESO";
      if(document.getElementById("th_sec_b")) document.getElementById("th_sec_b").innerText = "2. CONTROL DIMENSIONAL";
      if(document.getElementById("lbl_fecha")) document.getElementById("lbl_fecha").innerHTML = "Fecha y Hora de Fabricación<span class='req-mark'>*</span>";
      if(document.getElementById("lbl_hora_ctrl")) document.getElementById("lbl_hora_ctrl").style.display = "";
      if(document.getElementById("inp_hora_control")) document.getElementById("inp_hora_control").style.display = "";
      if(document.getElementById("lbl_resp")) document.getElementById("lbl_resp").innerHTML = "Responsable<span class='req-mark'>*</span>";
      if(document.getElementById("lbl_cliente")) document.getElementById("lbl_cliente").innerHTML = "Cliente<span class='req-mark'>*</span>";
      if(document.getElementById("txt_titulo_historial")) document.getElementById("txt_titulo_historial").innerText = "🔍 Búsqueda de Mediciones (Proceso)";
      
      for (var k=0; k<filasProceso.length; k++) filasProceso[k].style.display = '';
      if (tdResp) tdResp.colSpan = 1;
      if (tdAspecto) tdAspecto.colSpan = 1;
      if (filaDefecto) filaDefecto.style.display = 'none';
      if (filaEtiqueta) filaEtiqueta.style.display = 'none';
      if (filaM2) filaM2.style.display = 'none';
      if (divDictamen) divDictamen.style.display = 'block';
    }
    
    actualizarBotonesFormulario(false);
    verificarVisibilidadCampos();
    actualizarBotonDescarga();
  }

  function calcularPromedio() {
    var e1_el = document.getElementById("inp_e1");
    var e2_el = document.getElementById("inp_e2");
    var e3_el = document.getElementById("inp_e3");
    var e_prom = document.getElementById("inp_prom_e");
    
    if(!e1_el || !e2_el || !e3_el || !e_prom) return;
    
    var e1 = parseFloat(e1_el.value.replace(',', '.'));
    var e2 = parseFloat(e2_el.value.replace(',', '.'));
    var e3 = parseFloat(e3_el.value.replace(',', '.'));
    
    if (!isNaN(e1) && !isNaN(e2) && !isNaN(e3) && e1 >= 0 && e2 >= 0 && e3 >= 0) {
      e_prom.value = ((e1 + e2 + e3) / 3).toFixed(2);
    } else { e_prom.value = ""; }
  }

  function resetearCeldas() {
    var editInp = document.getElementById("inp_edit_id");
    var btnCancel = document.getElementById("btn_cancelar_edicion");
    
    if(editInp) editInp.value = "";
    if(btnCancel) btnCancel.style.display = "none";
    
    actualizarBotonesFormulario(false);
    
    var inputs = document.querySelectorAll('.excel-input, .excel-select');
    for (var i = 0; i < inputs.length; i++) {
      var el = inputs[i];
      if (el.id !== "inp_fecha" && el.id !== "inp_hora_control" && el.id !== "sel_modelo") {
        el.value = ""; el.classList.remove("is-invalid");
      }
    }
    
    var selEstadoManual = document.getElementById("sel_estado_manual");
    if (selEstadoManual) {
        selEstadoManual.value = "";
        cambiarColorDictamen(selEstadoManual);
    }
    
    var obsInp = document.getElementById("inp_obs");
    if (obsInp) obsInp.value = "";

    var hoy = new Date();
    hoy.setHours(hoy.getHours() - 3);
    var horaInp = document.getElementById("inp_hora_control");
    if(horaInp) horaInp.value = ("0" + hoy.getHours()).slice(-2) + ":" + ("0" + hoy.getMinutes()).slice(-2);
    
    var fotosInp = document.getElementById("inp_fotos");
    if(fotosInp) fotosInp.value = "";
    
    var lblFotos = document.getElementById("lbl_cant_fotos");
    if(lblFotos) lblFotos.innerText = "";
    
    var selAsp = document.getElementById("sel_aspecto");
    if(selAsp) selAsp.value = "OK";
    
    verificarVisibilidadCampos();
  }

  function validarObligatorios() {
    var claseRequerida = modoActual === 'proceso' ? '.req-proceso, .req-both' : '.req-both';
    var camposCriticos = document.querySelectorAll(claseRequerida);
    var hayError = false;
    for (var i = 0; i < camposCriticos.length; i++) {
      var el = camposCriticos[i];
      if (el.id === "inp_prom_e") continue;
      
      // Si el elemento está visible en pantalla, se valida. Si está oculto, se ignora.
      if (el.offsetWidth > 0 || el.offsetHeight > 0) {
        var val = el.value ? el.value.trim() : "";
        if (val === "" || (el.type === "number" && parseFloat(val.replace(',','.')) < 0) || el.classList.contains("is-invalid")) {
          el.classList.add('is-invalid');
          hayError = true;
        } else {
          el.classList.remove('is-invalid');
        }
      } else {
        el.classList.remove('is-invalid');
      }
    }
    return !hayError;
  }

  document.addEventListener('input', function(e) {
    if (e.target && e.target.classList && e.target.classList.contains('is-invalid')) {
       if (e.target.id === "inp_pv" || e.target.id === "inp_ppto" || e.target.id === "inp_etiqueta") {
           if (e.target.value === "" || /^\d+$/.test(e.target.value)) e.target.classList.remove('is-invalid');
       } else {
           e.target.classList.remove('is-invalid');
       }
    }
  });

  function ejecutarGuardado() {
    try {
      var pv_el = document.getElementById("inp_pv");
      if (pv_el && pv_el.value !== "" && !/^\d+$/.test(pv_el.value)) {
          alert("🚨 ERROR: El campo Pedido de Venta (PV) contiene letras o símbolos. Solo se permiten hasta 6 NÚMEROS.");
          pv_el.classList.add("is-invalid");
          return;
      }
      
      var ppto_el = document.getElementById("inp_ppto");
      if (ppto_el && ppto_el.value !== "" && !/^\d+$/.test(ppto_el.value)) {
          alert("🚨 ERROR: El campo Presupuesto (Ppto) contiene letras o símbolos. Solo se permiten hasta 6 NÚMEROS.");
          ppto_el.classList.add("is-invalid");
          return;
      }
      
      var etq_el = document.getElementById("inp_etiqueta");
      if (etq_el && etq_el.offsetWidth > 0 && etq_el.value !== "" && !/^\d+$/.test(etq_el.value)) {
          alert("🚨 ERROR: El campo Etiqueta contiene letras o símbolos. Solo se permiten hasta 10 NÚMEROS.");
          etq_el.classList.add("is-invalid");
          return;
      }

      if (!validarObligatorios()) { alert("⚠️ Por favor completá todos los campos obligatorios y corregí los errores marcados en rojo."); return; }

      var selMod = document.getElementById("sel_modelo");
      var mod = selMod ? selMod.value : "";
      var t = (CONFIG && CONFIG.tolerancias && CONFIG.tolerancias[mod]) ? CONFIG.tolerancias[mod] : {};
      
      var prom_e_el = document.getElementById("inp_prom_e");
      var E_el = document.getElementById("inp_E");
      var ancho_el = document.getElementById("inp_ancho");
      var aspecto_el = document.getElementById("sel_aspecto");
      
      var prom_e = prom_e_el ? parseFloat(prom_e_el.value.replace(',', '.')) || 0 : 0;
      var E = E_el ? parseFloat(E_el.value.replace(',', '.')) || 0 : 0;
      var ancho = ancho_el ? parseFloat(ancho_el.value.replace(',', '.')) || 0 : 0;
      var aspecto = aspecto_el ? aspecto_el.value : "OK";
      var desvios = [];

      var r_el = document.getElementById("inp_r");
      if (r_el && r_el.value !== "") {
          var r = parseFloat(r_el.value.replace(',', '.'));
          if (t.r_max !== undefined && r > t.r_max) desvios.push("R: " + r + " (Max: " + t.r_max + ")");
      }
      
      var gn_el = document.getElementById("inp_gn");
      if (gn_el && gn_el.value !== "") {
          var gn = parseFloat(gn_el.value.replace(',', '.'));
          if (t.gn_max !== undefined && gn > t.gn_max) desvios.push("Gn: " + gn + " (Max: " + t.gn_max + ")");
      }
      
      var val_escuadra = "";

      if (mod.indexOf("MC") === 0 || mod.indexOf("CW") === 0) {
         var gci_el = document.getElementById("inp_gci");
         if (gci_el && gci_el.value !== "") {
             var gci = parseFloat(gci_el.value.replace(',', '.'));
             if (t.gc_max !== undefined && gci > t.gc_max) desvios.push("Gci: " + gci + " (Max: " + t.gc_max + ")");
         }
         var gce_el = document.getElementById("inp_gce");
         if (gce_el && gce_el.value !== "") {
             var gce = parseFloat(gce_el.value.replace(',', '.'));
             if (t.gc_max !== undefined && gce > t.gc_max) desvios.push("Gce: " + gce + " (Max: " + t.gc_max + ")");
         }
         
         var hmi_el = document.getElementById("inp_hmi");
         if (hmi_el && hmi_el.value !== "") {
             var hmi = parseFloat(hmi_el.value.replace(',', '.'));
             if (t.hmi_min != null && hmi < t.hmi_min) desvios.push("Hmi: " + hmi + " (Min: " + t.hmi_min + ")");
             if (t.hmi_max != null && hmi > t.hmi_max) desvios.push("Hmi: " + hmi + " (Max: " + t.hmi_max + ")");
         }
         var hme_el = document.getElementById("inp_hme");
         if (hme_el && hme_el.value !== "") {
             var hme = parseFloat(hme_el.value.replace(',', '.'));
             if (t.hme_min != null && hme < t.hme_min) desvios.push("Hme: " + hme + " (Min: " + t.hme_min + ")");
             if (t.hme_max != null && hme > t.hme_max) desvios.push("Hme: " + hme + " (Max: " + t.hme_max + ")");
         }
         var hhi_el = document.getElementById("inp_hhi");
         if (hhi_el && hhi_el.value !== "") {
             var hhi = parseFloat(hhi_el.value.replace(',', '.'));
             if (t.hhi_min != null && hhi < t.hhi_min) desvios.push("Hhi: " + hhi + " (Min: " + t.hhi_min + ")");
             if (t.hhi_max != null && hhi > t.hhi_max) desvios.push("Hhi: " + hhi + " (Max: " + t.hhi_max + ")");
         }
         var hhe_el = document.getElementById("inp_hhe");
         if (hhe_el && hhe_el.value !== "") {
             var hhe = parseFloat(hhe_el.value.replace(',', '.'));
             if (t.hhe_min != null && hhe < t.hhe_min) desvios.push("Hhe: " + hhe + " (Min: " + t.hhe_min + ")");
             if (t.hhe_max != null && hhe > t.hhe_max) desvios.push("Hhe: " + hhe + " (Max: " + t.hhe_max + ")");
         }
         
         var esc_deg_el = document.getElementById("inp_escuadra_deg");
         var esc_min_el = document.getElementById("inp_escuadra_min");
         
         if (mod.indexOf("MC") === 0 && esc_deg_el && esc_deg_el.offsetWidth > 0 && esc_deg_el.value !== "") {
             var esc_deg = parseInt(esc_deg_el.value, 10);
             var esc_min_str = esc_min_el && esc_min_el.value !== "" ? esc_min_el.value : "00";
             var esc_min = parseInt(esc_min_str, 10);
             
             if(esc_min_str.length === 1) esc_min_str = "0" + esc_min_str;
             
             val_escuadra = esc_deg + "." + esc_min_str;
             
             if (t.escuadra_nom !== undefined && t.escuadra_tol !== undefined) {
                 if (Math.abs(esc_deg - t.escuadra_nom) > t.escuadra_tol) {
                     desvios.push("Escuadra: " + esc_deg + "º " + esc_min_str + "' (Nom: " + t.escuadra_nom + "±" + t.escuadra_tol + "º)");
                 }
             }
         }
      } else {
         var gc_el = document.getElementById("inp_gc");
         if (gc_el && gc_el.value !== "") {
             var gc = parseFloat(gc_el.value.replace(',', '.'));
             if (t.gc_max !== undefined && gc > t.gc_max) desvios.push("Gc: " + gc + " (Max: " + t.gc_max + ")");
         }
      }
      
      if (mod.indexOf("FR") === 0) {
        var rc1_el = document.getElementById("inp_rc1");
        var rc2_el = document.getElementById("inp_rc2");
        if (rc1_el && rc1_el.value !== "") {
            var rc1 = parseFloat(rc1_el.value.replace(',', '.'));
            var r_min = t.r_foil_min !== undefined ? t.r_foil_min : 1.0;
            var r_max = t.r_foil_max !== undefined ? t.r_foil_max : 7.0;
            if (rc1 < r_min || rc1 > r_max) desvios.push("R1: " + rc1 + " (Tol: " + r_min + "-" + r_max + ")");
        }
        if (rc2_el && rc2_el.value !== "") {
            var rc2 = parseFloat(rc2_el.value.replace(',', '.'));
            var r_min = t.r_foil_min !== undefined ? t.r_foil_min : 1.0;
            var r_max = t.r_foil_max !== undefined ? t.r_foil_max : 7.0;
            if (rc2 < r_min || rc2 > r_max) desvios.push("R2: " + rc2 + " (Tol: " + r_min + "-" + r_max + ")");
        }
      }
      
      if (t.e_min !== undefined && prom_e > 0 && (prom_e < t.e_min || prom_e > t.e_max)) desvios.push("e: " + prom_e + " (Tol: " + t.e_min + "-" + t.e_max + ")");
      if (t.E_min !== undefined && E > 0 && (E < t.E_min || E > t.E_max)) desvios.push("E: " + E + " (Tol: " + t.E_min + "-" + t.E_max + ")");
      if (t.ancho_nom !== undefined && ancho > 0 && Math.abs(ancho - t.ancho_nom) > t.ancho_tol) desvios.push("Ancho: " + ancho + " (Nom: " + t.ancho_nom + "±" + t.ancho_tol + ")");
      if (aspecto !== "OK") desvios.push("Aspecto Visual NC");

      var def_el = document.getElementById("sel_tipo_defecto");
      var defectoReclamo = def_el && def_el.offsetWidth > 0 ? def_el.value : "";
      
      if (defectoReclamo && defectoReclamo !== "Ninguno / Conforme") {
          desvios.push("Motivo/Defecto: " + defectoReclamo);
      }
      
      var estado = "CONFORME";
      if (modoActual === "reclamo") {
          estado = "RECLAMO CLIENTE";
      } else {
          var selEstadoManual = document.getElementById("sel_estado_manual");
          if (selEstadoManual && selEstadoManual.value) {
              estado = selEstadoManual.value;
          } else {
              estado = desvios.length > 0 ? "NO CONFORME" : "CONFORME";
          }
      }

      var formData = new FormData();
      formData.append("tipo", modoActual);
      if(document.getElementById("inp_fecha")) formData.append("fecha", document.getElementById("inp_fecha").value.replace("T", " "));
      if(document.getElementById("inp_hora_control")) formData.append("hora_control", modoActual === "proceso" ? document.getElementById("inp_hora_control").value : "");
      formData.append("modelo", mod);
      if(document.getElementById("sel_resp")) formData.append("resp", document.getElementById("sel_resp").value);
      if(document.getElementById("inp_pv")) formData.append("pv", document.getElementById("inp_pv").value);
      if(document.getElementById("inp_ppto")) formData.append("ppto", document.getElementById("inp_ppto").value);
      if(document.getElementById("inp_cliente")) formData.append("cliente", document.getElementById("inp_cliente").value);
      if(document.getElementById("sel_nucleo")) formData.append("nucleo", document.getElementById("sel_nucleo").value);
      formData.append("defecto_reclamo", defectoReclamo);
      
      var etq_el = document.getElementById("inp_etiqueta");
      formData.append("etiqueta", etq_el && etq_el.offsetWidth > 0 ? etq_el.value : "");
      
      var m2c_el = document.getElementById("inp_m2_controlados");
      formData.append("m2_controlados", m2c_el && m2c_el.offsetWidth > 0 ? m2c_el.value : "");
      
      var m2r_el = document.getElementById("inp_m2_rechazados");
      formData.append("m2_rechazados", m2r_el && m2r_el.offsetWidth > 0 ? m2r_el.value : "");
      
      var e_id_el = document.getElementById("inp_edit_id");
      if (e_id_el && e_id_el.value) formData.append("edit_id", e_id_el.value);

      if (modoActual === "proceso") {
        if(document.getElementById("inp_reposo")) formData.append("reposo", document.getElementById("inp_reposo").value);
        if(document.getElementById("inp_densidad")) formData.append("densidad", document.getElementById("inp_densidad").value);
        if(document.getElementById("inp_vel")) formData.append("vel", document.getElementById("inp_vel").value);
      }
      
      if(document.getElementById("inp_largo")) formData.append("largo", document.getElementById("inp_largo").value);
      
      if(document.getElementById("inp_hmi")) formData.append("hmi", document.getElementById("inp_hmi").value);
      if(document.getElementById("inp_hme")) formData.append("hme", document.getElementById("inp_hme").value);
      if(document.getElementById("inp_hhi")) formData.append("hhi", document.getElementById("inp_hhi").value);
      if(document.getElementById("inp_hhe")) formData.append("hhe", document.getElementById("inp_hhe").value);
      if(document.getElementById("inp_gc")) formData.append("gc", document.getElementById("inp_gc").value);
      if(document.getElementById("inp_gci")) formData.append("gci", document.getElementById("inp_gci").value);
      if(document.getElementById("inp_gce")) formData.append("gce", document.getElementById("inp_gce").value);
      if(document.getElementById("inp_gn")) formData.append("gn", document.getElementById("inp_gn").value);
      if(document.getElementById("inp_r")) formData.append("r", document.getElementById("inp_r").value);
      
      formData.append("escuadra", val_escuadra);
      
      if(document.getElementById("inp_e_c")) formData.append("e_c", document.getElementById("inp_e_c").value);
      if(document.getElementById("inp_rc1")) formData.append("rc1", document.getElementById("inp_rc1").value);
      if(document.getElementById("inp_rc2")) formData.append("rc2", document.getElementById("inp_rc2").value);
      
      for(var i=1; i<=9; i++){
          var nx = document.getElementById("inp_n"+i);
          if(nx && nx.offsetWidth > 0) formData.append("n"+i, nx.value);
      }
      
      formData.append("aspecto", aspecto);
      formData.append("ancho", ancho);
      formData.append("E", E);
      if(document.getElementById("inp_e1")) formData.append("e1", document.getElementById("inp_e1").value);
      if(document.getElementById("inp_e2")) formData.append("e2", document.getElementById("inp_e2").value);
      if(document.getElementById("inp_e3")) formData.append("e3", document.getElementById("inp_e3").value);
      formData.append("prom_e", prom_e);
      if(document.getElementById("inp_obs")) formData.append("obs", document.getElementById("inp_obs").value);
      formData.append("estado", estado);
      formData.append("desvios", desvios.join(" | "));

      var fotos_el = document.getElementById("inp_fotos");
      if(fotos_el) {
          var archivos = fotos_el.files;
          for (var fIdx = 0; fIdx < Math.min(archivos.length, 12); fIdx++) formData.append("fotos", archivos[fIdx]);
      }

      var btn = document.getElementById("btn_guardar_hoja");
      if(btn) { btn.innerText = "Guardando..."; btn.disabled = true; }

      fetch('/api/guardar_registro', { method: 'POST', body: formData })
        .then(function(res) {
           if (!res.ok) {
               return res.text().then(function(text){ throw new Error(text); });
           }
           return res.json();
        })
        .then(function(data) {
          if (data.status === "error") throw new Error(data.message);
          var tag = (modoActual === 'reclamo') ? "[RECLAMO CLIENTE]" : (modoActual === 'terminado' ? "[PRODUCTO TERMINADO]" : "[PROCESO]");
          var msg = estado === "CONFORME"
            ? "✅ REGISTRO CONFORME " + tag + " (#" + data.id + ")\\nGuardado exitosamente."
            : "⚠️ REGISTRO " + tag + " (#" + data.id + "):\\n* " + desvios.join("\\n* ") + "\\nGuardado exitosamente.";
          alert(msg);
          resetearCeldas();
        })
        .catch(function(err) { alert("🚨 ERROR:\\n\\n" + err.message); })
        .finally(function() { 
            if(btn) { btn.disabled = false; btn.innerText = document.getElementById("inp_edit_id").value ? "🔄 ACTUALIZAR REGISTRO" : "💾 GUARDAR REGISTRO"; }
        });
    } catch (err) { alert("Error interno en JavaScript: " + err.message); }
  }

  function cambiarPagina(delta) {
    var newPage = paginaActual + delta;
    if(newPage < 1) newPage = 1;
    cargarHistorial(newPage);
  }

  function cargarHistorial(page) {
    if(page) paginaActual = page;
    var lbl_pag = document.getElementById("lbl_pagina_actual");
    if(lbl_pag) lbl_pag.innerText = "Página " + paginaActual;
    
    var tbody = document.getElementById("tbodyHistorial");
    if(tbody) tbody.innerHTML = "<tr><td colspan='7' style='text-align:center; padding:20px;'>Cargando registros...</td></tr>";

    fetch('/api/obtener_historial?tipo=' + modoActual + '&page=' + paginaActual)
      .then(function(r) { 
          if (!r.ok) throw new Error("Error HTTP " + r.status);
          return r.json(); 
      })
      .then(function(data) { registrosHistorial = data; renderizarTabla(registrosHistorial); })
      .catch(function(e) { 
          console.error("Error cargando historial: ", e); 
          if(tbody) tbody.innerHTML = "<tr><td colspan='7' style='text-align:center; color:red; font-weight:bold;'>⚠️ Error de conexión con el servidor. Intenta recargar la página.</td></tr>";
      });
  }

  function renderizarTabla(lista) {
    var tbody = document.getElementById("tbodyHistorial");
    if(!tbody) return;
    tbody.innerHTML = "";
    if (!lista || lista.length === 0 || lista.status === "error") {
      tbody.innerHTML = "<tr><td colspan='7' style='text-align:center;'>No se encontraron registros.</td></tr>";
      return;
    }
    for (var i = 0; i < lista.length; i++) {
      var r = lista[i]; 
      var estado = (r.estado || "").trim().toUpperCase(); 
      var colorEstado = estado === 'CONFORME' ? 'var(--success)' : (estado === 'RECLAMO CLIENTE' ? '#EF6C00' : 'var(--danger)');
      var tr = document.createElement("tr");
      
      var accionesHTML = '<div style="display: flex; gap: 6px; flex-wrap: wrap; justify-content: center; align-items: center;">';
      
      accionesHTML += '<a href="/certificado_pdf/' + r.id + '?descargar=1" target="_blank" class="btn-small" style="background:var(--primary); color:white; border:none; padding:8px 12px; border-radius:6px; text-decoration:none; font-weight:bold; box-shadow:0 2px 4px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 5px;">📄 PDF</a>';
      
      if (estado !== 'CONFORME') {
         accionesHTML += '<a href="/alerta_pdf/' + r.id + '" target="_blank" class="btn-small" style="background:var(--danger); color:white; border:none; padding:8px 12px; border-radius:6px; text-decoration:none; font-weight:bold; box-shadow:0 2px 4px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 5px;">⚠️ ALERTA</a>';
      }

      if (r.tiene_fotos) {
         accionesHTML += '<a href="/descargar_fotos/' + r.id + '" class="btn-small" style="background:#455A64; color:white; border:none; padding:8px 12px; border-radius:6px; text-decoration:none; font-weight:bold; box-shadow:0 2px 4px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 5px;">📸 FOTOS</a>';
      }
      
      accionesHTML += '</div>';

      if (canEdit || canDelete) {
         accionesHTML += '<div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; align-items: center; margin-top: 8px; padding-top: 8px; border-top: 1px dashed #CFD8DC;">';
         if (canEdit) accionesHTML += '<button class="btn-admin-edit" onclick="cargarEdicion(' + r.id + ')">✏️ Editar</button>';
         if (canDelete) accionesHTML += '<button class="btn-admin-del" onclick="borrarRegistro(' + r.id + ')">🗑️ Borrar</button>';
         accionesHTML += '</div>';
      }

      var desvios_html = "";
      if (estado !== 'CONFORME' && r.desvios) {
          var formattedDesvios = r.desvios.split(" | ").map(function(d) { return '(' + d + ')' }).join("<br>");
          desvios_html = '<div style="margin-top: 6px; font-size: 11.5px; color: var(--secondary); font-weight: 500; line-height: 1.4;">' + formattedDesvios + '</div>';
      }

      tr.innerHTML = '<td><b>#' + r.id + '</b></td>' +
        '<td>' + (r.fecha || "") + '</td>' +
        '<td><b>' + (r.modelo || "") + '</b></td>' +
        '<td>' + (r.pv || "") + '</td>' +
        '<td>' + (r.cliente || "") + '</td>' +
        '<td><span style="font-weight:bold; color:' + colorEstado + ';">' + estado + '</span>' + desvios_html + '</td>' +
        '<td>' + accionesHTML + '</td>';
      tbody.appendChild(tr);
    }
  }

  function filtrarHistorial() {
    var q_el = document.getElementById("filtro_busqueda");
    if(!q_el) return;
    var q = q_el.value.toLowerCase();
    var filtrados = registrosHistorial.filter(function(r) {
      return (r.pv && r.pv.toLowerCase().indexOf(q) !== -1) || 
             (r.cliente && r.cliente.toLowerCase().indexOf(q) !== -1) ||
             (r.resp && r.resp.toLowerCase().indexOf(q) !== -1);
    });
    renderizarTabla(filtrados);
  }

  // ---- EDICION Y BORRADO DE REGISTROS ----
  function cargarEdicion(id) {
    fetch('/api/registro/' + id).then(function(r){return r.json();}).then(function(data) {
      if(data.status === "error") return alert(data.message);
      cambiarTipoHoja(data.tipo);
      
      var editIdEl = document.getElementById("inp_edit_id");
      var btnCancel = document.getElementById("btn_cancelar_edicion");
      if(editIdEl) editIdEl.value = data.id;
      if(btnCancel) btnCancel.style.display = "block";
      
      actualizarBotonesFormulario(true);
      
      if(document.getElementById("inp_fecha")) document.getElementById("inp_fecha").value = data.fecha || "";
      if(document.getElementById("inp_hora_control")) document.getElementById("inp_hora_control").value = data.hora_control || "";
      if(document.getElementById("sel_modelo")) document.getElementById("sel_modelo").value = data.modelo || "";
      if(document.getElementById("sel_resp")) document.getElementById("sel_resp").value = data.resp || "";
      if(document.getElementById("inp_pv")) document.getElementById("inp_pv").value = data.pv || "";
      if(document.getElementById("inp_ppto")) document.getElementById("inp_ppto").value = data.ppto || "";
      if(document.getElementById("inp_cliente")) document.getElementById("inp_cliente").value = data.cliente || "";
      if(document.getElementById("sel_nucleo")) document.getElementById("sel_nucleo").value = data.nucleo || "";
      
      if(data.tipo === "reclamo" || data.tipo === "terminado") {
         if(document.getElementById("sel_tipo_defecto")) document.getElementById("sel_tipo_defecto").value = data.defecto_reclamo || "Ninguno / Conforme";
      }
      
      if(data.tipo === "terminado" || data.tipo === "reclamo") {
         if(document.getElementById("inp_etiqueta")) document.getElementById("inp_etiqueta").value = data.etiqueta || "";
         if(document.getElementById("inp_m2_controlados")) document.getElementById("inp_m2_controlados").value = data.m2_controlados || "";
         if(document.getElementById("inp_m2_rechazados")) document.getElementById("inp_m2_rechazados").value = data.m2_rechazados || "";
      }
      
      if(data.tipo === "proceso") {
        if(document.getElementById("inp_reposo")) document.getElementById("inp_reposo").value = data.reposo || "";
        if(document.getElementById("inp_densidad")) document.getElementById("inp_densidad").value = data.densidad || "";
        if(document.getElementById("inp_vel")) document.getElementById("inp_vel").value = data.vel || "";
      }
      
      if(document.getElementById("inp_largo")) document.getElementById("inp_largo").value = data.largo || "";
      
      if(document.getElementById("inp_hmi")) document.getElementById("inp_hmi").value = data.hmi || "";
      if(document.getElementById("inp_hme")) document.getElementById("inp_hme").value = data.hme || "";
      if(document.getElementById("inp_hhi")) document.getElementById("inp_hhi").value = data.hhi || "";
      if(document.getElementById("inp_hhe")) document.getElementById("inp_hhe").value = data.hhe || "";
      if(document.getElementById("inp_gc")) document.getElementById("inp_gc").value = data.gc || "";
      if(document.getElementById("inp_gci")) document.getElementById("inp_gci").value = data.gci || "";
      if(document.getElementById("inp_gce")) document.getElementById("inp_gce").value = data.gce || "";
      if(document.getElementById("inp_gn")) document.getElementById("inp_gn").value = data.gn || "";
      if(document.getElementById("inp_r")) document.getElementById("inp_r").value = data.r || "";
      
      if(data.escuadra) {
          var esc_str = parseFloat(data.escuadra).toFixed(2).split('.');
          if(document.getElementById("inp_escuadra_deg")) document.getElementById("inp_escuadra_deg").value = parseInt(esc_str[0], 10);
          if(document.getElementById("inp_escuadra_min")) document.getElementById("inp_escuadra_min").value = esc_str[1];
      } else {
          if(document.getElementById("inp_escuadra_deg")) document.getElementById("inp_escuadra_deg").value = "";
          if(document.getElementById("inp_escuadra_min")) document.getElementById("inp_escuadra_min").value = "";
      }
      
      if(document.getElementById("sel_aspecto")) document.getElementById("sel_aspecto").value = data.aspecto || "OK";
      if(document.getElementById("inp_ancho")) document.getElementById("inp_ancho").value = data.ancho || "";
      if(document.getElementById("inp_E")) document.getElementById("inp_E").value = data.E || "";
      if(document.getElementById("inp_e1")) document.getElementById("inp_e1").value = data.e1 || "";
      if(document.getElementById("inp_e2")) document.getElementById("inp_e2").value = data.e2 || "";
      if(document.getElementById("inp_e3")) document.getElementById("inp_e3").value = data.e3 || "";
      if(document.getElementById("inp_prom_e")) document.getElementById("inp_prom_e").value = data.prom_e || "";
      if(document.getElementById("inp_e_c")) document.getElementById("inp_e_c").value = data.e_c || "";
      if(document.getElementById("inp_rc1")) document.getElementById("inp_rc1").value = data.rc1 || "";
      if(document.getElementById("inp_rc2")) document.getElementById("inp_rc2").value = data.rc2 || "";
      if(document.getElementById("inp_obs")) document.getElementById("inp_obs").value = data.obs || "";
      
      for(var i=1; i<=9; i++) { 
          var n_el = document.getElementById("inp_n"+i);
          if(n_el) n_el.value = data["n"+i] || ""; 
      }
      
      var selEstadoManual = document.getElementById("sel_estado_manual");
      if (selEstadoManual && data.tipo !== "reclamo") {
          selEstadoManual.value = data.estado || "";
          cambiarColorDictamen(selEstadoManual);
      }
      
      verificarVisibilidadCampos();
      activarPestana('hoja');
      window.scrollTo(0, 0);
      alert("Modo edición activado. Las fotos anteriores se borrarán si subes nuevas.");
    }).catch(function(e) { alert("Error de conexión al cargar la edición."); });
  }

  function cancelarEdicion() { resetearCeldas(); }

  function borrarRegistro(id) {
    if(!confirm("⚠️ ¿Estás seguro de anular el registro #" + id + "? Esta acción quedará en la auditoría.")) return;
    fetch('/api/anular_registro/' + id, { method: 'POST' }).then(function(r){return r.json();}).then(function(res) {
       if(res.status==="ok"){ alert("Registro anulado."); cargarHistorial(); }
       else alert(res.message);
    }).catch(function(err) { alert("Error: " + err.message); });
  }

  // ---- PANEL ADMIN ----
  function cargarTolsAdmin() {
    var selAdmMod = document.getElementById("sel_adm_mod");
    if(!selAdmMod) return;
    var mod = selAdmMod.value;
    var t = (CONFIG.tolerancias && CONFIG.tolerancias[mod]) ? CONFIG.tolerancias[mod] : {};
    var keys = ["e_min", "e_max", "E_min", "E_max", "gc_max", "gn_max", "r_max", "ancho_nom", "ancho_tol", "r_foil_min", "r_foil_max", "hmi_min", "hmi_max", "hme_min", "hme_max", "hhi_min", "hhi_max", "hhe_min", "hhe_max", "escuadra_nom", "escuadra_tol"];
    for (var i = 0; i < keys.length; i++) {
      var input = document.getElementById("adm_" + keys[i]);
      if (input) input.value = t[keys[i]] !== undefined && t[keys[i]] !== null ? t[keys[i]] : '';
    }
  }

  function guardarTolsAdmin() {
    var selAdmMod = document.getElementById("sel_adm_mod");
    if(!selAdmMod) return;
    var m = selAdmMod.value;
    var tols = {};
    var keys = ["e_min", "e_max", "E_min", "E_max", "gc_max", "gn_max", "r_max", "ancho_nom", "ancho_tol", "r_foil_min", "r_foil_max", "hmi_min", "hmi_max", "hme_min", "hme_max", "hhi_min", "hhi_max", "hhe_min", "hhe_max", "escuadra_nom", "escuadra_tol"];
    for (var i = 0; i < keys.length; i++) {
      var input = document.getElementById("adm_" + keys[i]);
      if (input && input.value !== "") {
          tols[keys[i]] = parseFloat(input.value.replace(',', '.'));
      } else {
          tols[keys[i]] = null;
      }
    }
    if (!CONFIG.tolerancias) CONFIG.tolerancias = {};
    CONFIG.tolerancias[m] = tols;
    guardarConfigAPI("Tolerancias de " + m + " guardadas.");
  }

  function guardarListasAdmin() {
    var admPers = document.getElementById("adm_txt_personal");
    var admNuc = document.getElementById("adm_txt_nucleos");
    if(admPers) CONFIG.personal = admPers.value.split(",").map(function(s){return s.trim();}).filter(Boolean);
    if(admNuc) CONFIG.nucleos = admNuc.value.split(",").map(function(s){return s.trim();}).filter(Boolean);
    guardarConfigAPI("Listas actualizadas.");
  }

  function guardarConfigAPI(msg) {
    fetch('/api/guardar_config', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(CONFIG) })
      .then(function(r) { return r.json(); }).then(function() { alert(msg); }).catch(function(e) { alert("Error guardando"); });
  }

  function cargarUsuariosAdmin() {
    fetch('/api/usuarios').then(function(r){return r.json();}).then(function(users) {
       var tbody = document.getElementById("tbodyUsuarios");
       if(!tbody) return;
       tbody.innerHTML = "";
       for(var i=0; i<users.length; i++){
          var u = users[i];
          var pRaw = u.permisos || "";
          var permText = u.rol === 'admin' ? '<i>Acceso Total</i>' : (u.permisos ? u.permisos.replace(/,/g, ' | ') : 'Sin permisos');
          var userHTML = "<tr><td>" + u.username + "</td><td>" + u.rol + "</td><td>" + permText + "</td>";
          userHTML += "<td><div style='display:flex; gap:5px;'>";
          userHTML += "<button class='btn-admin-del' onclick='borrarUsuario("+u.id+")'>🗑️ Borrar</button>";
          userHTML += "</div></td></tr>";
          tbody.innerHTML += userHTML;
       }
    }).catch(function(e) { console.error("Error al cargar usuarios:", e); });
  }

  function crearUsuario() {
    var u = document.getElementById("usr_name").value.trim();
    var p = document.getElementById("usr_pass").value.trim();
    var r = document.getElementById("usr_rol").value;
    
    var p_list = [];
    if(document.getElementById("chk_escribir").checked) p_list.push("escribir");
    if(document.getElementById("chk_editar").checked) p_list.push("editar");
    if(document.getElementById("chk_borrar").checked) p_list.push("borrar");
    if(document.getElementById("chk_excel").checked) p_list.push("excel");
    var permisosStr = r === 'admin' ? "escribir,editar,borrar,excel" : p_list.join(",");
    
    if(!u) return alert("Completa el nombre de usuario.");
    if(!p) return alert("Completa la contraseña para el nuevo usuario.");
    
    fetch('/api/usuarios', {
       method: 'POST', headers: {'Content-Type': 'application/json'},
       body: JSON.stringify({username: u, password: p, rol: r, permisos: permisosStr})
    })
    .then(function(res){
        if (!res.ok) { return res.text().then(function(text) { throw new Error(text) }); }
        return res.json();
    })
    .then(function(d) {
       if(d.status==="ok") { 
           document.getElementById("usr_name").value = "";
           document.getElementById("usr_pass").value = "";
           cargarUsuariosAdmin();
           alert("Usuario creado correctamente.");
       } else {
           alert(d.message);
       }
    })
    .catch(function(e) { alert("Error: " + e.message); });
  }

  function borrarUsuario(id) {
    if(!confirm("⚠️ ¿Eliminar usuario permanentemente?")) return;
    fetch('/api/usuarios/' + id, {method: 'DELETE'})
    .then(function(r){return r.json();})
    .then(function(){cargarUsuariosAdmin();})
    .catch(function(e) { alert("Error de conexión"); });
  }

  function cargarAuditoria() {
    fetch('/api/auditoria').then(function(r){return r.json();}).then(function(logs) {
       var tbody = document.getElementById("tbodyAuditoria");
       if(!tbody) return;
       tbody.innerHTML = "";
       for(var i=0; i<logs.length; i++){
          var l = logs[i];
          tbody.innerHTML += "<tr><td style='white-space:nowrap;'>" + l.fecha + "</td><td><b>" + l.usuario + "</b></td><td>" + l.accion + "</td><td>" + l.detalle + "</td></tr>";
       }
    }).catch(function(e) { console.error("Error al cargar auditoría:", e); });
  }

  window.onload = function() {
    {% if current_user %}
      var admPersonal = document.getElementById("adm_txt_personal");
      if(admPersonal) admPersonal.value = (CONFIG.personal || []).join(", ");
      
      var admNucleos = document.getElementById("adm_txt_nucleos");
      if(admNucleos) admNucleos.value = (CONFIG.nucleos || []).join(", ");
      
      verificarVisibilidadCampos();
      actualizarBotonDescarga();
    {% endif %}
  };

} catch(err) {
  console.error(err);
  alert("Hubo un problema iniciando la aplicación. Por favor, recarga la página. Detalle: " + err.message);
}
</script>
{% endif %}
</body>
</html>
"""

# ------------------------------------------------------------------
# RUTAS DE FLASK Y API - NECESARIAS PARA QUE EL SISTEMA FUNCIONE
# ------------------------------------------------------------------

@app.route('/')
def index():
    try:
        cfg = load_config()
        perm_str = ""
        if 'user_id' in session:
            user = Usuario.query.get(session['user_id'])
            if user: perm_str = user.permisos or ""
                
        return render_template_string(HTML_MAIN, 
            config=cfg, config_json=json.dumps(cfg, ensure_ascii=False),
            defectos=DEFECTOS_RECLAMO,
            fecha_hoy=bsas_now().strftime("%Y-%m-%dT%H:%M"),
            hora_hoy=bsas_now().strftime("%H:%M"),
            current_user=session.get('username'),
            current_rol=session.get('rol'),
            current_permisos=perm_str,
            error_login=session.pop('error_login', None)
        )
    except Exception as e:
        db.session.rollback()
        return str(e), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user = Usuario.query.filter_by(username=username, activo=True).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['rol'] = user.rol
            session['permisos'] = user.permisos or ""
            log_auditoria(user.username, "LOGIN", "Inicio de sesión")
        else:
            session['error_login'] = "Usuario o contraseña incorrectos"
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        return str(e), 500

@app.route('/logout')
def logout():
    log_auditoria(session.get('username', 'Desconocido'), "LOGOUT", "Cierre de sesión")
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/guardar_registro', methods=['POST'])
@login_requerido
def api_guardar_registro():
    data = request.form.to_dict()
    edit_id = data.get("edit_id")
    
    es_admin = session.get('rol') == 'admin'
    permisos = session.get('permisos', '')

    if not es_admin:
        if edit_id and 'editar' not in permisos:
            return jsonify({"status": "error", "message": "No tienes permiso para editar registros"}), 403
        if not edit_id and 'escribir' not in permisos:
            return jsonify({"status": "error", "message": "No tienes permiso para crear registros"}), 403

    try:
        archivos = request.files.getlist('fotos')
        reg_id = guardar_registro(data, archivos, edit_id)
        return jsonify({"status": "ok", "id": reg_id})
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/obtener_historial')
@login_requerido
def api_obtener_historial():
    try:
        tipo = request.args.get('tipo', 'proceso')
        page = int(request.args.get('page', 1))
        per_page = 50
        offset = (page - 1) * per_page
        registros = Registro.query.filter_by(tipo=tipo, activo=True).order_by(Registro.id.desc()).offset(offset).limit(per_page).all()
        
        # PREVENCIÓN DE CONGELAMIENTO (Evita el problema N+1 descargando miles de megas)
        reg_ids = [r.id for r in registros]
        fotos_existentes = []
        if reg_ids:
            fotos_existentes = db.session.query(Foto.registro_id).filter(Foto.registro_id.in_(reg_ids)).distinct().all()
        ids_con_fotos = {f[0] for f in fotos_existentes}
        
        return jsonify([{
            "id": r.id, "fecha": r.fecha, "modelo": r.modelo, 
            "pv": r.pv, "cliente": r.cliente, "resp": r.resp, 
            "estado": r.estado, "desvios": r.desvios,
            "tiene_fotos": True if r.id in ids_con_fotos else False
        } for r in registros])
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/registro/<int:id>')
@login_requerido
def api_obtener_registro(id):
    try:
        r = Registro.query.get(id)
        if not r or not r.activo:
            return jsonify({"status": "error", "message": "Registro no encontrado"})
        return jsonify(r.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/anular_registro/<int:id>', methods=['POST'])
@login_requerido
def api_anular_registro(id):
    try:
        if session.get('rol') != 'admin' and 'borrar' not in session.get('permisos', ''):
            return jsonify({"status": "error", "message": "No tienes permiso para borrar registros"}), 403
        r = Registro.query.get(id)
        if not r: return jsonify({"status": "error", "message": "No encontrado"})
        r.activo = False
        log_auditoria(session.get('username'), "BORRADO", f"Anuló registro #{id} de {r.tipo}")
        db.session.commit()
        return jsonify({"status": "ok"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/guardar_config', methods=['POST'])
@admin_requerido
def api_guardar_config():
    try:
        save_config(request.json)
        log_auditoria(session.get('username'), "CONFIG", "Actualizó configuración del sistema")
        return jsonify({"status": "ok"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/usuarios', methods=['GET', 'POST'])
@admin_requerido
def api_usuarios():
    try:
        if request.method == 'GET':
            users = Usuario.query.filter_by(activo=True).all()
            return jsonify([{"id": u.id, "username": u.username, "rol": u.rol, "permisos": u.permisos} for u in users])
        else:
            data = request.json
            u = data.get("username")
            p = data.get("password")
            r = data.get("rol", "operador")
            perm = data.get("permisos", "")
            if Usuario.query.filter_by(username=u).first():
                return jsonify({"status": "error", "message": "El usuario ya existe"})
            nuevo = Usuario(username=u, password_hash=generate_password_hash(p), rol=r, permisos=perm)
            db.session.add(nuevo)
            db.session.commit()
            log_auditoria(session.get('username'), "USUARIOS", f"Creó usuario: {u} con permisos {perm}")
            return jsonify({"status": "ok"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/usuarios/<int:id>', methods=['DELETE'])
@admin_requerido
def api_borrar_usuario(id):
    try:
        u = Usuario.query.get(id)
        if not u: return jsonify({"status": "error", "message": "Usuario no encontrado"})

        if u.username == 'admin': return jsonify({"status": "error", "message": "No se puede borrar el admin principal"})
        db.session.delete(u)
        db.session.commit()
        log_auditoria(session.get('username'), "USUARIOS", f"Borró usuario: {u.username}")
        return jsonify({"status": "ok"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/auditoria')
@admin_requerido
def api_auditoria():
    try:
        logs = Auditoria.query.order_by(desc(Auditoria.id)).limit(30).all()
        return jsonify([{
            "fecha": l.fecha.strftime("%d/%m %H:%M"), "usuario": l.usuario, 
            "accion": l.accion, "detalle": l.detalle
        } for l in logs])
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/descargar_excel')
@login_requerido
def route_descargar_excel():
    if session.get('rol') != 'admin' and 'excel' not in session.get('permisos', ''):
        return "No tienes permiso para descargar Excel", 403
    tipo = request.args.get("tipo", "proceso")
    buf = generar_excel_bytes(tipo)
    return send_file(buf, as_attachment=True, download_name=f"Reporte_{tipo.capitalize()}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route('/descargar_alertas_excel')
@login_requerido
def route_descargar_alertas():
    if session.get('rol') != 'admin' and 'excel' not in session.get('permisos', ''):
        return "No tienes permiso para descargar Excel", 403
    buf = generar_excel_alertas_bytes()
    return send_file(buf, as_attachment=True, download_name="Alertas_Kingspan_Filtradas.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route('/certificado_pdf/<int:reg_id>')
@login_requerido
def route_certificado_pdf(reg_id):
    try:
        reg = Registro.query.get_or_404(reg_id)
        buf = generar_pdf_certificado(reg, es_alerta=False)
        return send_file(buf, as_attachment=True, download_name=f"Certificado_PV{reg.pv}.pdf", mimetype="application/pdf")
    except Exception as e:
        db.session.rollback()
        return str(e), 500

@app.route('/alerta_pdf/<int:reg_id>')
@login_requerido
def route_alerta_pdf(reg_id):
    try:
        reg = Registro.query.get_or_404(reg_id)
        
        # REQUERIMIENTO VITAL: Solo los que tocan el botón ALERTA entran al Excel de Alertas
        existe = AlertaLog.query.filter_by(registro_id=reg.id).first()
        if not existe:
            log_a = AlertaLog(usuario=session.get('username', 'Sistema'), registro_id=reg.id)
            db.session.add(log_a)
            db.session.commit()

        buf = generar_pdf_certificado(reg, es_alerta=True)
        return send_file(buf, as_attachment=True, download_name=f"Alerta_PV{reg.pv}.pdf", mimetype="application/pdf")
    except Exception as e:
        db.session.rollback()
        return str(e), 500

# ==========================================
# RUTAS DE FOTOS Y EXPLORADOR
# ==========================================

@app.route('/descargar_fotos/<int:reg_id>')
@login_requerido
def route_descargar_fotos_zip(reg_id):
    try:
        reg = Registro.query.get_or_404(reg_id)
        if not reg.fotos:
            return "Este registro no tiene fotos adjuntas.", 404

        mem_zip = io.BytesIO()
        with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for foto in reg.fotos:
                zf.writestr(foto.nombre, foto.contenido)
        
        mem_zip.seek(0)
        return send_file(
            mem_zip,
            as_attachment=True,
            download_name=f"Fotos_Alerta_{reg.id}_PV{reg.pv}.zip",
            mimetype="application/zip"
        )
    except Exception as e:
        db.session.rollback()
        return str(e), 500

@app.route('/api/admin_dump')
@admin_requerido
def route_admin_dump():
    try:
        page = int(request.args.get('page', 1))
        per_page = 50
        offset = (page - 1) * per_page
        
        total_fotos = Foto.query.count()
        total_pages = math.ceil(total_fotos / per_page)
        
        fotos = Foto.query.with_entities(Foto.id, Foto.registro_id, Foto.nombre).order_by(desc(Foto.id)).offset(offset).limit(per_page).all()
        
        html_content = """
        <div style="font-family: Arial; padding: 20px; max-width: 800px; margin: 0 auto; background: #F0F4F8; border-radius: 8px;">
            <h2 style="color: #002D62; margin-bottom: 5px;">📸 Explorador de Fotos</h2>
            <p style="color: #455A64; font-size:14px; margin-top: 0;">Total en sistema: {{ total }} fotos. Página {{ page }} de {{ total_pages }}.</p>
            
            <table border="1" cellpadding="10" style="border-collapse: collapse; width: 100%; text-align: left; background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px;">
                <tr style="background-color: #002D62; color: white;">
                    <th>ID Foto</th><th>Alerta / Panel</th><th>Nombre Archivo</th><th>Acción</th>
                </tr>
                {% for f in fotos %}
                <tr id="row-{{ f.id }}">
                    <td><b>#{{ f.id }}</b></td>
                    <td>Reg. #{{ f.registro_id }}</td>
                    <td style="font-size:12px; color:#546E7A;">{{ f.nombre }}</td>
                    <td style="display: flex; gap: 10px;">
                        <a href="/api/foto_raw/{{ f.id }}" target="_blank" style="background: #2E7D32; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none; font-size: 13px; font-weight:bold;">👁️ Abrir</a>
                        <button onclick="borrarFoto({{ f.id }})" style="background: #C62828; color: white; padding: 5px 10px; border-radius: 4px; border: none; font-size: 13px; font-weight:bold; cursor: pointer;">🗑️</button>
                    </td>
                </tr>
                {% endfor %}
                {% if not fotos %}
                <tr><td colspan="4" style="text-align:center;">No hay fotos registradas.</td></tr>
                {% endif %}
            </table>
            
            <div style="display:flex; justify-content: space-between;">
                {% if page > 1 %}
                <a href="?page={{ page - 1 }}" style="background: #002D62; color: white; padding: 10px 15px; border-radius: 6px; text-decoration: none; font-weight:bold;">&laquo; Anterior</a>
                {% else %} <div></div> {% endif %}
                
                {% if page < total_pages %}
                <a href="?page={{ page + 1 }}" style="background: #002D62; color: white; padding: 10px 15px; border-radius: 6px; text-decoration: none; font-weight:bold;">Siguiente &raquo;</a>
                {% endif %}
            </div>
        </div>
        
        <script>
            function borrarFoto(id) {
                if(!confirm('⚠️ ¿Estás seguro de eliminar PERMANENTEMENTE esta foto de la base de datos? Esta acción no se puede deshacer.')) return;
                fetch('/api/foto_raw/' + id, {method: 'DELETE'})
                .then(r => r.json())
                .then(data => {
                    if(data.status === 'ok') {
                        document.getElementById('row-' + id).style.display = 'none';
                    } else {
                        alert('Error: ' + data.message);
                    }
                }).catch(e => alert('Error de conexión'));
            }
        </script>
        """
        return render_template_string(html_content, fotos=fotos, page=page, total_pages=total_pages, total=total_fotos)
    except Exception as e:
        db.session.rollback()
        return str(e), 500

@app.route('/api/foto_raw/<int:foto_id>', methods=['GET', 'DELETE'])
@admin_requerido
def route_foto_raw(foto_id):
    try:
        foto = Foto.query.get_or_404(foto_id)
        if request.method == 'DELETE':
            db.session.delete(foto)
            db.session.commit()
            log_auditoria(session.get('username'), "BORRADO_FOTO", f"Eliminó foto ID #{foto_id} permanentemente")
            return jsonify({"status": "ok"})
        else:
            return send_file(
                io.BytesIO(foto.contenido), 
                mimetype=foto.mime or 'image/jpeg', 
                as_attachment=False, 
                download_name=foto.nombre
            )
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
