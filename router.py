#!/usr/bin/env python3
"""
Web Meshtastic
--------------------------
Connect to a Meshtastic node (USB or TCP), listen mesages of network, store them in a SQLite base (un device/node history) and expose them in a web interface(Flask +
Socket.IO) on the local netwok.

environement variables :
    MESHTASTIC_CONNECTION = "serial" (default) or TCP
    MESHTASTIC_PORT       = serial port path, ex: /dev/ttyUSB0
                            (leave blank for auto detection)
    MESHTASTIC_HOST       = IP adress/node hostname if TCP connexion
    WEB_HOST              = web server listener (default 0.0.0.0)
    WEB_PORT              = web server port (default 5000)
"""

import os
import time
import sqlite3
import threading
from datetime import datetime

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from pubsub import pub

import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "messages.db")

CONNECTION_TYPE = os.environ.get("MESHTASTIC_CONNECTION", "serial").lower()
SERIAL_PORT = os.environ.get("MESHTASTIC_PORT") or None
TCP_HOST = os.environ.get("MESHTASTIC_HOST") or "meshtastic.local"
WEB_HOST = os.environ.get("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("WEB_PORT", "5000"))

BROADCAST_ID = "broadcast"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "meshtastic-web-secret")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

interface = None
interface_lock = threading.Lock()
nodes_cache = {}
connection_status = {"connected": False, "detail": "Démarrage en cours..."}


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            node_name TEXT,
            direction TEXT NOT NULL,   -- 'in' ou 'out'
            text TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_message(node_id, node_name, direction, text):
    conn = get_db()
    ts = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO messages (node_id, node_name, direction, text, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        (node_id, node_name, direction, text, ts),
    )
    conn.commit()
    conn.close()
    return ts


def get_messages(node_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT node_name, direction, text, timestamp FROM messages "
        "WHERE node_id = ? ORDER BY id ASC",
        (node_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_last_message_per_node():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT m.node_id, m.text, m.direction, m.timestamp
        FROM messages m
        INNER JOIN (
            SELECT node_id, MAX(id) AS max_id FROM messages GROUP BY node_id
        ) latest ON m.node_id = latest.node_id AND m.id = latest.max_id
        """
    ).fetchall()
    conn.close()
    return {row["node_id"]: dict(row) for row in rows}


# ---------------------------------------------------------------------------
# Meshtastic : connexion an element
# ---------------------------------------------------------------------------
def node_display_name(node_id):
    """Renvoie un nom lisible pour un noeud (long name, sinon short name, sinon id)."""
    if node_id == BROADCAST_ID:
        return "Diffusion générale"
    with interface_lock:
        if interface is not None:
            node = interface.nodes.get(node_id) if interface.nodes else None
            if node:
                user = node.get("user", {})
                return user.get("longName") or user.get("shortName") or node_id
    return node_id


def refresh_nodes_cache():
    global nodes_cache
    with interface_lock:
        if interface is None or not interface.nodes:
            return
        new_cache = {}
        my_id = interface.myInfo.my_node_num if interface.myInfo else None
        for node_id, node in interface.nodes.items():
            user = node.get("user", {})
            new_cache[node_id] = {
                "id": node_id,
                "name": user.get("longName") or user.get("shortName") or node_id,
                "shortName": user.get("shortName", ""),
                "lastHeard": node.get("lastHeard"),
                "snr": node.get("snr"),
                "isSelf": node.get("num") == my_id,
            }
        nodes_cache = new_cache
    socketio.emit("nodes_update", list(nodes_cache.values()))


def on_receive(packet, interface_ref=None):
    try:
        decoded = packet.get("decoded", {})
        if decoded.get("portnum") != "TEXT_MESSAGE_APP":
            return

        text = decoded.get("text", "")
        to_num = packet.get("to")
        from_id = packet.get("fromId") or str(packet.get("from"))

        # A message sent to diffusion adress (broadcast) is sort
        # in the conversation "general", private messages are
        # sort under the sender device ID
        is_broadcast = to_num in (0xFFFFFFFF, None)
        conv_id = BROADCAST_ID if is_broadcast else from_id
        name = node_display_name(from_id)

        ts = save_message(conv_id, name, "in", text)
        socketio.emit(
            "new_message",
            {
                "node_id": conv_id,
                "node_name": name,
                "direction": "in",
                "text": text,
                "timestamp": ts,
            },
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[meshtastic] erreur de traitement d'un message reçu : {exc}")


def on_connection_established(interface_ref=None, topic=pub.AUTO_TOPIC):
    connection_status["connected"] = True
    connection_status["detail"] = "Connecté au module Meshtastic"
    print("[meshtastic] connexion établie")
    refresh_nodes_cache()
    socketio.emit("connection_status", connection_status)


def on_connection_lost(interface_ref=None, topic=pub.AUTO_TOPIC):
    connection_status["connected"] = False
    connection_status["detail"] = "Lost connexion, reconect..."
    print("[meshtastic] lost connexion")
    socketio.emit("connection_status", connection_status)


def connect_meshtastic():
    """connection loop : retry forever"""
    global interface

    pub.subscribe(on_receive, "meshtastic.receive")
    pub.subscribe(on_connection_established, "meshtastic.connection.established")
    pub.subscribe(on_connection_lost, "meshtastic.connection.lost")

    while True:
        try:
            connection_status["detail"] = "Connexion to Meshtastic device..."
            socketio.emit("connection_status", connection_status)

            with interface_lock:
                if CONNECTION_TYPE == "tcp":
                    interface = meshtastic.tcp_interface.TCPInterface(hostname=TCP_HOST)
                else:
                    interface = meshtastic.serial_interface.SerialInterface(devPath=SERIAL_PORT)

            # Attend tant que la connexion est active ; l'objet interface
            # lève une exception ou se ferme si le module se déconnecte.
            while connection_status["connected"] is not False or interface is not None:
                time.sleep(5)
                if interface is None:
                    break
                # petite vérification périodique de vivacité
                try:
                    _ = interface.nodes
                except Exception:
                    raise ConnectionError("Meshtastic interface unjoinable")

        except Exception as exc:  # noqa: BLE001
            connection_status["connected"] = False
            connection_status["detail"] = f"Connexion error : {exc}"
            print(f"[meshtastic] {connection_status['detail']}")
            socketio.emit("connection_status", connection_status)
            with interface_lock:
                interface = None
            time.sleep(10)


def periodic_node_refresh():
    while True:
        time.sleep(30)
        refresh_nodes_cache()


# ---------------------------------------------------------------------------
# Web path
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("routeurMeshtastic.html")


@app.route("/api/status")
def api_status():
    return jsonify(connection_status)


@app.route("/api/nodes")
def api_nodes():
    refresh_nodes_cache()
    last_messages = get_last_message_per_node()
    nodes = list(nodes_cache.values())

    # Always the general channel first
    broadcast_entry = {
        "id": BROADCAST_ID,
        "name": "General channel",
        "shortName": "ALL",
        "lastHeard": None,
        "isSelf": False,
    }
    result = [broadcast_entry] + nodes
    for n in result:
        last = last_messages.get(n["id"])
        n["lastMessage"] = last["text"] if last else None
        n["lastMessageAt"] = last["timestamp"] if last else None
    return jsonify(result)


@app.route("/api/messages/<node_id>")
def api_messages(node_id):
    return jsonify(get_messages(node_id))


@app.route("/api/send", methods=["POST"])
def api_send():
    data = request.get_json(force=True)
    node_id = (data or {}).get("node_id", BROADCAST_ID)
    text = (data or {}).get("text", "").strip()

    if not text:
        return jsonify({"error": "Empty message"}), 400

    with interface_lock:
        if interface is None:
            return jsonify({"error": "Meshtastic device not connected"}), 503
        try:
            if node_id == BROADCAST_ID:
                interface.sendText(text)
            else:
                interface.sendText(text, destinationId=node_id)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": f"Send issue : {exc}"}), 500

    name = node_display_name(node_id)
    ts = save_message(node_id, name, "out", text)
    payload = {
        "node_id": node_id,
        "node_name": name,
        "direction": "out",
        "text": text,
        "timestamp": ts,
    }
    socketio.emit("new_message", payload)
    return jsonify({"status": "ok", **payload})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()

    threading.Thread(target=connect_meshtastic, daemon=True).start()
    threading.Thread(target=periodic_node_refresh, daemon=True).start()

    print(f"Interface web disponible sur http://{WEB_HOST}:{WEB_PORT}")
    socketio.run(app, host=WEB_HOST, port=WEB_PORT)
