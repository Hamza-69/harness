import uvicorn


def main() -> None:
    uvicorn.run(
        "harnesslocal.app:app",
        host="127.0.0.1",
        port=43827,
        log_level="info",
    )
