import asyncpg
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

    # Definir la conexión a la base de datos Postgres
    async def postgres_connection(self):
        if not self.connection:
            try:
                self.connection = await asyncpg.connect(**self.db_config)
                logging.info("Conexión a la base de datos Postgres establecida")
            except Exception as e:
                logging.error(f"Error al conectar a la base de datos: {e}")
                raise
            
    # Crear una nueva sesión en la base de datos
    async def create_session(self) -> int:
        await self.postgres_connection()
        try:
            result = await self.connection.fetchrow(
                "INSERT INTO sessions (start_time, end_time) VALUES (NOW(), NOW() + INTERVAL '1 hour') RETURNING id"
            )
            session_id = result['id']
            logging.info(f"Nueva sesión creada con ID: {session_id}")
            return session_id
        except Exception as e:
            logging.error(f"Error al crear una nueva sesión: {e}")
            raise   
    
    # Finalizar una sesión en la base de datos
    async def end_session(self, session_id: int):
        await self.postgres_connection()
        try:
            await self.connection.execute(
                "UPDATE sessions SET end_time = NOW() WHERE id = $1",
                session_id
            )
            logging.info(f"Sesión {session_id} finalizada")
        except Exception as e:
            logging.error(f"Error al finalizar la sesión {session_id}: {e}")
            raise
        
    # Guardar la traducción en la base de datos
    async def save_translation(self, session_id: int, text_output: str, confidence: float):
        await self.postgres_connection()
        try:
            await self.connection.execute(
                "INSERT INTO translations (sessionId, textOutput, confidence) VALUES ($1, $2, $3)",
                session_id, text_output, confidence
            )
            logging.info(f"Traducción guardada para la sesión {session_id}: '{text_output}' (confianza: {confidence:.2f})")
        except Exception as e:
            logging.error(f"Error al guardar la traducción para la sesión {session_id}: {e}")
            raise    
        
    # Registrar un evento del sistema en la base de datos
    async def log_system_event(self, session_id: int, event_type: str, message: str, severity: str = "INFO"):
        await self.postgres_connection()
        try:
            await self.connection.execute(
                "INSERT INTO system_logs (sessionId, eventType, message, severity) VALUES ($1, $2, $3, $4)",
                session_id, event_type, message, severity
            )
            logging.info(f"Evento del sistema registrado para la sesión {session_id}: {event_type} - {message}")
        except Exception as e:
            logging.error(f"Error al registrar el evento del sistema para la sesión {session_id}: {e}")
            raise

    # Obtener traducciones de una sesión (método adicional si lo necesitas)
    async def get_session_translations(self, session_id: int) -> List[Dict]:
        await self.postgres_connection()
        try:
            rows = await self.connection.fetch(
                "SELECT id, textOutput, confidence, created_at FROM translations WHERE sessionId = $1 ORDER BY created_at DESC",
                session_id
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logging.error(f" Error obteniendo traducciones: {e}")
            return []
        
    async def close_connection(self):
        if self.connection:
            try:
                await self.connection.close()
                logging.info("Conexión a la base de datos Postgres cerrada")
            except Exception as e:
                logging.error(f"Error al cerrar la conexión a la base de datos: {e}")
                raise