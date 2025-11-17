/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';

const SocketContext = createContext();

export const useSocket = () => {
  const context = useContext(SocketContext);
  if (!context) throw new Error('useSocket debe usarse dentro de SocketProvider');
  return context;
};

export const SocketProvider = ({ children }) => {
  // Estados
  const [isConnected, setIsConnected] = useState(false);
  const [systemStatus, setSystemStatus] = useState({});
  const [currentSession, setCurrentSession] = useState(null);
  const [notifications, setNotifications] = useState([]);
  
  // Referencias
  const videoSocketRef = useRef(null);
  const controlSocketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);

  const BACKEND_URL = import.meta.env.VITE_BACKEND_WS || "ws://192.168.56.1:8000";
  const MAX_RECONNECT_ATTEMPTS = 5;
  const RECONNECT_DELAY = 3000;

  // Agregar notificación
  const addNotification = useCallback((type, message) => {
    const notification = {
      id: Date.now(),
      type, // 'success', 'error', 'info', 'warning'
      message,
      timestamp: new Date().toLocaleTimeString()
    };
    
    setNotifications(prev => [notification, ...prev.slice(0, 4)]);
    
    // Auto-remover después de 5 segundos
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== notification.id));
    }, 5000);
  }, []);

  // Conectar WebSockets
  const connectWebSockets = useCallback(() => {
    if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
      console.error("Máximo de intentos de reconexión alcanzado");
      addNotification('error', 'No se pudo conectar al servidor. Recarga la página.');
      return;
    }

    console.log(`🔌 Conectando a backend: ${BACKEND_URL} (intento ${reconnectAttemptsRef.current + 1})`);

    // Cerrar conexiones previas si existen
    videoSocketRef.current?.close();
    controlSocketRef.current?.close();

    // VIDEO SOCKET
    try {
      videoSocketRef.current = new WebSocket(`${BACKEND_URL}/ws/video`);

      videoSocketRef.current.onopen = () => {
        console.log("Conectado al WebSocket de video");
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        addNotification('success', 'Conectado al servidor de video');
      };

      videoSocketRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Manejar diferentes tipos de mensajes
          switch(data.type) {
            case 'init':
              setSystemStatus(prev => ({
                ...prev,
                camera_status: data.camera_status,
                model_info: data.model_info
              }));
              console.log("Estado inicial recibido:", data);
              break;
            
            case 'camera_status':
              setSystemStatus(prev => ({
                ...prev,
                camera_status: data.camera_status
              }));
              break;
            
            // video_frame se maneja en Translation.jsx
            default:
              break;
          }
        } catch (error) {
          console.error("Error parseando mensaje de video:", error);
        }
      };

      videoSocketRef.current.onerror = (error) => {
        console.error("Error en WebSocket de video:", error);
        addNotification('error', 'Error de conexión al servidor de video');
      };

      videoSocketRef.current.onclose = (event) => {
        console.warn(`WS de video cerrado (código: ${event.code})`);
        setIsConnected(false);
        
        // Intentar reconectar
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current++;
          addNotification('warning', `Reconectando... (${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`);
          reconnectTimeoutRef.current = setTimeout(connectWebSockets, RECONNECT_DELAY);
        }
      };
    } catch (error) {
      console.error("Error creando WebSocket de video:", error);
      addNotification('error', 'Error al crear conexión de video');
    }

    // CONTROL SOCKET
    try {
      controlSocketRef.current = new WebSocket(`${BACKEND_URL}/ws/control`);

      controlSocketRef.current.onopen = () => {
        console.log("Conectado al WebSocket de control");
        addNotification('success', 'Conectado al servidor de control');
      };

      controlSocketRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("Mensaje de control recibido:", data);
          
          switch(data.type) {
            case 'system_status':
              setSystemStatus(data);
              break;
            
            case 'camera_status':
              setSystemStatus(prev => ({
                ...prev,
                camera_status: data.camera_status
              }));
              if (data.success !== undefined) {
                addNotification(
                  data.success ? 'success' : 'error',
                  data.success ? 'Cámara cambiada correctamente' : 'Error cambiando cámara'
                );
              }
              break;
            
            case 'session_started':
              setCurrentSession(data.session_id);
              addNotification('success', `Sesión iniciada: ${data.session_id}`);
              break;
            
            case 'session_ended':
              setCurrentSession(null);
              addNotification('info', 'Sesión finalizada');
              break;
            
            case 'info':
              addNotification('info', data.message);
              break;
            
            case 'error':
              console.error("Error del backend:", data.message);
              addNotification('error', data.message);
              break;
            
            default:
              console.log("Tipo de mensaje desconocido:", data.type);
              break;
          }
        } catch (error) {
          console.error("Error parseando mensaje de control:", error);
        }
      };

      controlSocketRef.current.onerror = (error) => {
        console.error("Error en WebSocket de control:", error);
      };

      controlSocketRef.current.onclose = () => {
        console.warn("WS de control cerrado");
      };
    } catch (error) {
      console.error("Error creando WebSocket de control:", error);
      addNotification('error', 'Error al crear conexión de control');
    }
  }, [BACKEND_URL, addNotification]);

  // Montaje / desmontaje
  useEffect(() => {
    connectWebSockets();
    
    return () => {
      clearTimeout(reconnectTimeoutRef.current);
      videoSocketRef.current?.close();
      controlSocketRef.current?.close();
    };
  }, [connectWebSockets]);

  // Enviar comandos de control
  const sendControlCommand = useCallback((command, data = {}) => {
    if (controlSocketRef.current?.readyState === WebSocket.OPEN) {
      const payload = { command, ...data };
      console.log("Enviando comando:", payload);
      controlSocketRef.current.send(JSON.stringify(payload));
    } else {
      console.warn("WebSocket de control no está conectado");
      addNotification('warning', 'No hay conexión con el servidor de control');
    }
  }, [addNotification]);

  // Comandos específicos (helpers)
  const getStatus = useCallback(() => {
    sendControlCommand('get_status');
  }, [sendControlCommand]);

  const resetClassifier = useCallback(() => {
    sendControlCommand('reset_classifier');
  }, [sendControlCommand]);

  const switchCamera = useCallback((cameraConfig) => {
    sendControlCommand('switch_camera', { camera: cameraConfig });
  }, [sendControlCommand]);

  const startSession = useCallback(() => {
    sendControlCommand('start_session');
  }, [sendControlCommand]);

  const stopSession = useCallback(() => {
    if (currentSession) {
      sendControlCommand('stop_session', { session_id: currentSession });
    } else {
      sendControlCommand('stop_session');
    }
  }, [sendControlCommand, currentSession]);

  // Limpiar notificación específica
  const removeNotification = useCallback((id) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  const value = {
    // Estados
    isConnected,
    systemStatus,
    currentSession,
    notifications,
    
    // Referencias
    videoSocket: videoSocketRef.current,
    controlSocket: controlSocketRef.current,
    
    // Funciones
    sendControlCommand,
    getStatus,
    resetClassifier,
    switchCamera,
    startSession,
    stopSession,
    removeNotification,
    addNotification
  };

  return (
    <SocketContext.Provider value={value}>
      {children}
    </SocketContext.Provider>
  );
};