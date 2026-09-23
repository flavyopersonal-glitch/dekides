"""Um serviço Render: Streamlit público e API somente na interface local."""
import os
import signal
import subprocess
import sys
import time
import urllib.request


def commands(environ):
    port = int(environ.get("PORT", "10000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT inválida")
    api_port = 8001 if port == 8000 else 8000
    env = dict(environ, DEKIDS_API_URL=f"http://127.0.0.1:{api_port}")
    api = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(api_port)]
    ui = [sys.executable, "-m", "streamlit", "run", "frontend/Home.py", "--server.address=0.0.0.0",
          f"--server.port={port}", "--server.headless=true", "--browser.gatherUsageStats=false"]
    return api, ui, env


def main():
    required = ("DATABASE_URL", "NEON_AUTH_BASE_URL")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise SystemExit("Configure no Render: " + ", ".join(missing))
    api, ui, env = commands(os.environ)
    children = []

    def stop(signum=None, frame=None):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        children.append(subprocess.Popen(api, env=env))
        # Só publica a tela quando o banco e a API estão prontos.
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if children[0].poll() is not None:
                raise RuntimeError("A API encerrou durante a inicialização.")
            try:
                with urllib.request.urlopen(env["DEKIDS_API_URL"] + "/health/ready/", timeout=10) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError("API/banco indisponível. Confira DATABASE_URL e as migrações.")
        children.append(subprocess.Popen(ui, env=env))
        while all(child.poll() is None for child in children):
            time.sleep(1)
        raise RuntimeError("Um serviço encerrou; o Render deve reiniciar a aplicação.")
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
