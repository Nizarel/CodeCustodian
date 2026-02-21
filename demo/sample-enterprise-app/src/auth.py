"""Authentication and security module — multiple vulnerabilities."""

import hashlib
import os
import pickle
import subprocess
import yaml


# XXX: hardcoded credentials must be moved to Key Vault before production
DATABASE_PASSWORD = "SuperSecret123!"
STRIPE_API_KEY = "sk_live_4eC39HqLyjWDarjtT1zdp7dc"
AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


def authenticate_user(username: str, password: str) -> bool:
    """Check user credentials — uses weak MD5 hashing."""
    hashed = hashlib.md5(password.encode()).hexdigest()
    # TODO: migrate to bcrypt or argon2 — MD5 is cryptographically broken
    stored_hash = _get_stored_hash(username)
    return hashed == stored_hash


def _get_stored_hash(username: str) -> str:
    return hashlib.sha1(username.encode()).hexdigest()


def execute_admin_command(cmd: str) -> str:
    """Run an admin command — command injection vulnerability."""
    result = os.system(cmd)
    return str(result)


def run_report_query(query_param: str) -> str:
    """Build and run a database query — SQL injection risk."""
    import sqlite3

    conn = sqlite3.connect("inventory.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM products WHERE name = '{query_param}'")
    rows = cursor.fetchall()
    conn.close()
    return str(rows)


def eval_user_expression(expr: str) -> int:
    """Evaluate a user-provided expression — code injection."""
    return eval(expr)


def load_user_session(session_file: str):
    """Load a serialized session — insecure deserialization."""
    with open(session_file, "rb") as f:
        return pickle.load(f)


def load_config_yaml(config_path: str):
    """Load YAML config — unsafe loader."""
    with open(config_path) as f:
        return yaml.load(f)


def run_backup_script(script_name: str) -> str:
    """Run a shell script — shell injection via shell=True."""
    result = subprocess.run(script_name, shell=True, capture_output=True, text=True)
    return result.stdout
