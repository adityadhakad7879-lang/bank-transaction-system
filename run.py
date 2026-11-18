import os
from app import create_app
from app.config import Config
from app.db import init_db

app = create_app()

if __name__ == '__main__':
    # Auto-initialize database schema if database file does not exist
    if not os.path.exists(Config.DATABASE_PATH):
        print("[*] Database not detected. Initializing schema...")
        init_db(app)
        print("[✔] Database initialized. Running seed_data is recommended for initial demo records.")

    port = int(os.environ.get('PORT', 5000))
    print(f"[*] Starting {Config.BANK_NAME} portal at http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port, debug=True)
