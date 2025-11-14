/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useEffect, useState, useRef } from 'react';

const SocketContext = createContext();

export const useSocket = () => {
  const context = useContext(SocketContext);
  if (!context) throw new Error('useSocket debe usarse dentro de SocketProvider');
  return context;
};

export const SocketProvider = ({ children }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [systemStatus, setSystemStatus] = useState({});
  const videoSocketRef = useRef(null);
  const controlSocketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const BACKEND_URL = import.meta.env.VITE_BACKEND_WS || "http://192.168.56.1:8000";

  const connectWebSockets = () => {
    console.log("Intentando conectar a backend:", BACKEND_URL);

    videoSocketRef.current = new WebSocket(`${BACKEND_URL}/ws/video`);
    controlSocketRef.current = new WebSocket(`${BACKEND_URL}/ws/control`);

    // --- VIDEO SOCKET ---
    videoSocketRef.current.onopen = () => {
      console.log("Conectado al WebSocket de video");
      setIsConnected(true);
    };

    videoSocketRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "camera_status") {
          setSystemStatus(prev => ({ ...prev, camera_status: data.camera_status }));
        }
        // el resto (video_frame) se maneja desde Translation.jsx
      } catch (error) {
        console.error("Error parseando mensaje de video:", error);
      }
    };

    videoSocketRef.current.onclose = () => {
      console.warn("WS de video desconectado, reintentando...");
      setIsConnected(false);
      reconnectTimeoutRef.current = setTimeout(connectWebSockets, 3000);
    };

    // --- CONTROL SOCKET ---
    controlSocketRef.current.onopen = () => {
      console.log("Conectado al WebSocket de control");
    };

    controlSocketRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "system_status") setSystemStatus(data);
        if (data.type === "camera_status") setSystemStatus(prev => ({ ...prev, camera_status: data.camera_status }));
        if (data.type === "error") console.error("Error del backend:", data.message);
      } catch (error) {
        console.error("Error parseando mensaje de control:", error);
      }
    };
  };

  // --- Montaje / desmontaje ---
  useEffect(() => {
    connectWebSockets();
    return () => {
      clearTimeout(reconnectTimeoutRef.current);
      videoSocketRef.current?.close();
      controlSocketRef.current?.close();
    };
  }, []);

  // --- Enviar comandos ---
  const sendControlCommand = (command, data = {}) => {
    if (controlSocketRef.current?.readyState === WebSocket.OPEN) {
      controlSocketRef.current.send(JSON.stringify({ command, ...data }));
    } else {
      console.warn("WebSocket de control no está conectado");
    }
  };

  return (
    <SocketContext.Provider
      value={{
        isConnected,
        systemStatus,
        videoSocket: videoSocketRef.current,
        controlSocket: controlSocketRef.current,
        sendControlCommand,
      }}
    >
      {children}
    </SocketContext.Provider>
  );
};
