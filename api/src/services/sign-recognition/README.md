#SISTEMA DE RECONOCIMIENTO Y TRADUCCION DE LENGUAJE DE SEÑAS A LENGUAJE NATURAL

##Pasos a seguir para activar el microservicio

1. **Activar el entorno virtual de python(windows):**
```bash
venv\Scripts\activate
```

2. **Ejecutar el servicio, en el entorno virtual activo:**
```bash
uvicorn app.main:app --reload --host 192.168.56.1 --port 8000
```

