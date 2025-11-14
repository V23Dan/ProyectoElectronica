# Micro-servicio de python para traduccion de lengua de señas a lenguaje natural

## Servicio hecho en python con servidor FastApi para acceder a el mediante end-points http, se usa MediaPipe solutions para deteccion de manos y creacion de landmarks que permiten reconocer señas 

## --------------------------------------------------------------

> Pasos para activar el microservicio:

1. Entrar a la carpeta de del micro-servicio:
```bash
cd api\src\services\sign-recognition-python
```

2. Activar el micro-servicio:
```bash
env\Scripts\activate
```

3. Activar el servidor FastApi:
```bash
uvicorn app.main:app --host 192.168.56.1 --port 8000
```

Apagar servidor FastApi:
```bash
ctrl + c
```
## ---------------------------------------------------------------

Desactivar microservicio:
```bash
deactivate
```