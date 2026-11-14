"""
Intelligent Queue Prediction & Management System
Unified Application Launcher
"""
import os
import sys
import webbrowser
import uvicorn

if __name__ == "__main__":
    # Add project root to sys.path
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    print("=" * 70)
    print("  Intelligent Queue Prediction & Management System")
    print("  Supervised Machine Learning Coursework Project")
    print("=" * 70)
    print("  Backend API:   http://localhost:8000")
    print("  API Docs:      http://localhost:8000/docs")
    print("  Student UI:    http://localhost:8000  (Production React Build)")
    print("  Frontend Dev:  Run 'npm run dev' inside 'frontend' (port 5173)")
    print("=" * 70)

    # Launch uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=False)
