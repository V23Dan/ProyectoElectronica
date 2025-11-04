/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useEffect, useState, useRef } from 'react';

const SocketContext = createContext();

export const useSocket = () => {
  const context = useContext(SocketContext);
  if (!context) {
    throw new Error('useSocket debe usarse dentro de SocketProvider');
  }
  return context;
};

export const SocketProvider = ({ children }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [systemStatus, setSystemStatus] = useState({});
  const videoSocketRef = useRef(null);
  const controlSocketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const connectWebSockets = () => {
    // Conexión para video
    videoSocketRef.current = new WebSocket('ws://192.168.56.1:8000/ws/video');
    
    // Conexión para control
    controlSocketRef.current = new WebSocket('ws://192.168.56.1:8000/ws/control');

    // Eventos para WebSocket de Video
    videoSocketRef.current.onopen = () => {
      console.log('✅ Conectado al WebSocket de video');
      setIsConnected(true);
    };

    videoSocketRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Manejar diferentes tipos de mensajes
        switch (data.type) {
          case 'video_frame':
            // Este lo manejará el componente de Translation
            break;
          case 'camera_status':
            setSystemStatus(prev => ({ ...prev, camera_status: data.camera_status }));
            break;
          case 'session_started':
            console.log('Sesión iniciada:', data.session_id);
            break;
          case 'error':
            console.error('Error del servidor:', data.message);
            break;
          default:
            console.log('Mensaje recibido:', data);
        }
      } catch (error) {
        console.error('Error parsing message:', error);
      }
    };

    videoSocketRef.current.onclose = () => {
      console.log('❌ Desconectado del WebSocket de video');
      setIsConnected(false);
      
      // Reconexión automática después de 3 segundos
      reconnectTimeoutRef.current = setTimeout(() => {
        console.log('🔄 Intentando reconectar...');
        connectWebSockets();
      }, 3000);
    };

    videoSocketRef.current.onerror = (error) => {
      console.error('❌ Error en WebSocket de video:', error);
    };

    // Eventos para WebSocket de Control
    controlSocketRef.current.onopen = () => {
      console.log('✅ Conectado al WebSocket de control');
    };

    controlSocketRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'system_status') {
          setSystemStatus(data);
        }
      } catch (error) {
        console.error('Error parsing control message:', error);
      }
    };
  };

  useEffect(() => {
    connectWebSockets();

    return () => {
      // Limpiar timeouts y conexiones
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (videoSocketRef.current) {
        videoSocketRef.current.close();
      }
      if (controlSocketRef.current) {
        controlSocketRef.current.close();
      }
    };
  }, []);

  // Función para enviar comandos al WebSocket de control
  const sendControlCommand = (command, data = {}) => {
    if (controlSocketRef.current && controlSocketRef.current.readyState === WebSocket.OPEN) {
      controlSocketRef.current.send(JSON.stringify({ command, ...data }));
    } else {
      console.warn('WebSocket de control no está conectado');
    }
  };

  return (
    <SocketContext.Provider value={{ 
      isConnected, 
      systemStatus,
      videoSocket: videoSocketRef.current,
      controlSocket: controlSocketRef.current,
      sendControlCommand 
    }}>
      {children}
    </SocketContext.Provider>
  );
};