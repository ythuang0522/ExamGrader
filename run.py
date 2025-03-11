#!/usr/bin/env python3
"""Entry point script for the ExamGrader application."""

import sys
from examgrader.main import main
from examgrader.web import app

if __name__ == '__main__':
    if '--web' in sys.argv:
        import argparse
        parser = argparse.ArgumentParser(description='ExamGrader - Web Interface')
        parser.add_argument('--web', action='store_true', help='Start web interface')
        parser.add_argument('--host', default='127.0.0.1', help='Host for web interface')
        parser.add_argument('--port', type=int, default=5000, help='Port for web interface')
        args = parser.parse_args()
        
        print(f"Starting web interface at http://{args.host}:{args.port}")
        app.run(host=args.host, port=args.port)
    else:
        # Pass all arguments to main() function
        sys.exit(main()) 