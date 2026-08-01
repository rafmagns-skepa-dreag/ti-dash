import uvicorn

from ti_dash.web.app import create_app

app = create_app("dashboard.db")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
