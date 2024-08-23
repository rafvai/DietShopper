import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    # Get the port from the environment variable or use 5000 by default
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
