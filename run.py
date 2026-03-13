#!/usr/bin/env python3
import os
from app import create_app
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create app
app, login_manager = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_ENV') == 'development'
    )
