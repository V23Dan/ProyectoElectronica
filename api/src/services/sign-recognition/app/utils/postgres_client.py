import psycopg2
from typing import Optional, List, Dict
import logging

class PostgresClient: 
    def __init__(self):
        self.connection = None
        self.db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'TraductionSigns',
        'user': 'postgres',
        'password': 'admin'
        }

    #Definir la connexion a la base de datos Postgres
    async def postgres_connection(self):
        if not self.connection:
            try:
                self.connection = psycopg2.connect(**self.db_config)
                logging.info("Conexión a la base de datos Postgres establecida")
            except Exception as e:
                logging.error(f"Error al conectar a la base de datos: {e}")
                raise
            
            
    #Crear una nueva sesion en la base de datos
    async def create_session(self):
        await self.postgres_connection()
        try:
            result = await self.connection.fetchrow("INSERT INTO sessions (startTime, endTime) VALUES (NOW(), NOW() + INTERVAL '1 hour') RETURNING id")
            logging.info(f"Nueva sesión creada con ID: {result['id']}")
            return result['id']   
        except Exception as e:
            logging.error(f"Error al crear una nueva sesión: {e}")
            raise   
    
    #Finalizar una sesion en la base de datos
    async def end_session(self, session_id: int):
        await self.postgres_connection()
        try:
            await self.connection.execute(
            "UPDATE sessions SET endTime = NOW() WHERE id = $1",
            session_id
            )
            logging.info(f"Sesión {session_id} finalizada")
        except Exception as e:
            logging.error(f"Error al finalizar la sesión {session_id}: {e}")
            raise
        
    
    #Guardar la traduccion en la base de datos
    async def save_translation(self, session_id: int, text_output: str, confidence: float):
        await self.postgres_connection()
        try:
            await self.conn.execute(
            "INSERT INTO translations (sessionId, textOutput, confidence) VALUES ($1, $2, $3)",
            session_id, text_output, confidence
            )
            logging.info(f"Traducción guardada para la sesión {session_id}")
        except Exception as e:
            logging.error(f"Error al guardar la traducción para la sesión {session_id}: {e}")
            raise    
        
    #Registrar un evento del sistema en la base de datos
    async def log_system_event(self, session_id: int, event_type: str, message: str, severity: str = "INFO"):
        await self.postgres_connection()
        try:
            await self.conn.execute(
            "INSERT INTO system_logs (sessionId, eventType, message, severity) VALUES ($1, $2, $3, $4)",
            session_id, event_type, message, severity
            )
            logging.info(f"Evento del sistema registrado para la sesión {session_id}: {event_type} - {message}")
        except Exception as e:
            logging.error(f"Error al registrar el evento del sistema para la sesión {session_id}: {e}")
            raise
        
    async def close_connection(self):
        if self.connection:
            try:
                await self.connection.close()
                logging.info("Conexión a la base de datos Postgres cerrada")
            except Exception as e:
                logging.error(f"Error al cerrar la conexión a la base de datos: {e}")
                raise
        



