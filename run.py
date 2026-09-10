"""Ponto de entrada do sistema de Certificacao ANATEL.

Por padrao o servidor sobe em 0.0.0.0, ou seja: abre nesta maquina em
http://127.0.0.1:5000 e tambem pelos outros computadores da rede, em
http://<ip-desta-maquina>:5000 (o endereco e mostrado ao iniciar).

Para deixar o sistema restrito a esta maquina:
    set ANATEL_HOST=127.0.0.1
    python run.py

O modo de depuracao fica DESLIGADO por padrao. Ele e util no desenvolvimento, mas expoe um
console que executa codigo no servidor - nunca deixe ligado com o sistema aberto na rede.
Para ligar durante o desenvolvimento: set ANATEL_DEBUG=1
"""
import os
import socket

from app import create_app

app = create_app()


def _ip_da_maquina():
    """Descobre o IP que os outros computadores usam para chegar aqui."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))       # nao envia nada, so escolhe a placa de rede
            return s.getsockname()[0]
    except OSError:
        return None


if __name__ == "__main__":
    host = os.environ.get("ANATEL_HOST", "0.0.0.0")
    porta = int(os.environ.get("ANATEL_PORTA", "5000"))
    debug = os.environ.get("ANATEL_DEBUG") == "1"

    if debug and host != "127.0.0.1":
        print("[aviso] modo de depuração ligado com acesso pela rede — desligue "
              "(ANATEL_DEBUG) antes de deixar o sistema no ar.")
    if host == "0.0.0.0":
        ip = _ip_da_maquina()
        print(f"[nesta máquina] http://127.0.0.1:{porta}")
        print(f"[na rede]       http://{ip or '<ip-desta-maquina>'}:{porta}")
    else:
        print(f"[somente nesta máquina] http://{host}:{porta}")

    app.run(host=host, port=porta, debug=debug)
