import React, { useEffect, useRef, useState } from "react";
import { useSocket } from "../../context/SocketContext";
import Notifications from "../../components/Notifications/Notifications";
import {
  Play,
  Square,
  RotateCcw,
  Camera,
  Activity,
  Zap,
  Settings,
  Wifi,
  WifiOff,
  Cpu,
} from "lucide-react";
import "./Translation.css";

const Translation = () => {
  const {
    videoSocket,
    isConnected,
    systemStatus,
    currentSession,
    notifications,
    removeNotification,
    getStatus,
    resetClassifier,
    startSession,
    stopSession,
  } = useSocket();

  const videoCanvasRef = useRef(null);
  const [currentTranslation, setCurrentTranslation] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [translationsHistory, setTranslationsHistory] = useState([]);
  const [showAdvancedInfo, setShowAdvancedInfo] = useState(false);
  const [stats, setStats] = useState({
    fps: 0,
    cpu: 0,
    ram: 0,
    inference_time_ms: 0,
    buffer_current: 0,
    buffer_max: 30,
  });

  // 🧠 Manejar mensajes del WebSocket de video
  useEffect(() => {
    if (!videoSocket) return;

    const handleMessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "video_frame") {
          // 🎥 Renderizar frame en canvas
          if (data.frame && videoCanvasRef.current) {
            const ctx = videoCanvasRef.current.getContext("2d");
            const img = new Image();
            img.onload = () => {
              ctx.clearRect(
                0,
                0,
                videoCanvasRef.current.width,
                videoCanvasRef.current.height
              );
              ctx.drawImage(
                img,
                0,
                0,
                videoCanvasRef.current.width,
                videoCanvasRef.current.height
              );
            };
            img.src = data.frame;
          }

          // ✋ Actualizar predicción
          if (data.prediction) {
            setCurrentTranslation(data.prediction);
            setConfidence(data.confidence || 0);

            // Guardar en historial solo predicciones válidas y de alta confianza
            if (
              data.confidence > 0.7 &&
              data.prediction !== "NO_HANDS_DETECTED" &&
              data.prediction !== "LOADING_SEQUENCE" &&
              data.prediction !== "BAJA_CONFIANZA" &&
              !data.prediction.startsWith("ERROR")
            ) {
              setTranslationsHistory((prev) => {
                // Evitar duplicados consecutivos
                if (prev.length > 0 && prev[0].text === data.prediction) {
                  return prev;
                }
                
                return [
                  {
                    text: data.prediction,
                    confidence: data.confidence,
                    timestamp: new Date().toLocaleTimeString(),
                  },
                  ...prev.slice(0, 14), // Mantener últimas 15
                ];
              });
            }
          }

          // 📊 Actualizar métricas de rendimiento
          if (data.performance) {
            setStats({
              fps: data.performance.fps || 0,
              cpu: data.performance.cpu || 0,
              ram: data.performance.ram || 0,
              inference_time_ms: data.performance.inference_time_ms || 0,
              buffer_current: data.buffer_status?.current || 0,
              buffer_max: data.buffer_status?.max || 30,
            });
          }
        }
      } catch (err) {
        console.error("Error procesando mensaje de video:", err);
      }
    };

    videoSocket.addEventListener("message", handleMessage);
    return () => videoSocket.removeEventListener("message", handleMessage);
  }, [videoSocket]);

  // 🔘 Controladores de sesión
  const handleStartSession = () => {
    setIsProcessing(true);
    startSession();
  };

  const handleStopSession = () => {
    setIsProcessing(false);
    stopSession();
  };

  const handleResetClassifier = () => {
    resetClassifier();
    setTranslationsHistory([]);
    setCurrentTranslation("");
    setConfidence(0);
  };

  // 🎨 Utilidades de UI
  const getConfidenceColor = (conf) => {
    if (conf > 0.8) return "#10b981"; // verde
    if (conf > 0.6) return "#f59e0b"; // amarillo
    return "#ef4444"; // rojo
  };

  const getPredictionStatus = (text) => {
    if (text === "NO_HANDS_DETECTED") return "sin-manos";
    if (text === "LOADING_SEQUENCE") return "cargando";
    if (text === "BAJA_CONFIANZA") return "baja-confianza";
    if (text.startsWith("ERROR")) return "error";
    return "detectado";
  };

  // 🟢 Pedir estado al conectarse
  useEffect(() => {
    if (isConnected) {
      getStatus();
    }
  }, [isConnected, getStatus]);

  // 🔄 Sincronizar estado de sesión
  useEffect(() => {
    if (currentSession !== null) {
      setIsProcessing(true);
    } else {
      setIsProcessing(false);
    }
  }, [currentSession]);

  return (
    <div className="translation-page">
      {/* Sistema de notificaciones */}
      {/* <Notifications
        notifications={notifications}
        onRemove={removeNotification}
      /> */}

      <div className="translation-layout">
        {/* === SECCIÓN PRINCIPAL === */}
        <div className="main-display">
          {/* --- VIDEO --- */}
          <div className="video-section">
            <div className="video-container">
              <div className="video-header">
                <Camera size={20} />
                <h2>Video en Tiempo Real</h2>
                <div className="connection-badge">
                  {isConnected ? (
                    <>
                      <Wifi size={16} className="icon-connected" />
                      <span className="status-text connected">Conectado</span>
                    </>
                  ) : (
                    <>
                      <WifiOff size={16} className="icon-disconnected" />
                      <span className="status-text disconnected">
                        Desconectado
                      </span>
                    </>
                  )}
                </div>
              </div>

              <div className="video-wrapper">
                <canvas
                  ref={videoCanvasRef}
                  width="640"
                  height="480"
                  className="video-canvas"
                />
                
                {/* Overlay con información */}
                <div className="video-overlay">
                  <div className="overlay-item fps">
                    <Zap size={14} />
                    FPS: {stats.fps?.toFixed(1) || "0"}
                  </div>
                  <div className="overlay-item buffer">
                    Buffer: {stats.buffer_current}/{stats.buffer_max}
                  </div>
                  {systemStatus?.model_info && (
                    <div className="overlay-item model">
                      <Cpu size={14} />
                      Modelo: {systemStatus.model_info.type} (
                      {systemStatus.model_info.features} features)
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* --- TRADUCCIÓN --- */}
          <div className="translation-section">
            <div className="current-translation">
              <div className="translation-header">
                <Activity size={20} />
                <h2>Traducción Actual</h2>
                <button
                  className="info-toggle"
                  onClick={() => setShowAdvancedInfo(!showAdvancedInfo)}
                  title="Información avanzada"
                >
                  <Settings size={16} />
                </button>
              </div>

              <div className="translation-content">
                {/* Texto de predicción */}
                <div
                  className={`translation-text status-${getPredictionStatus(
                    currentTranslation
                  )}`}
                >
                  {currentTranslation || "Esperando detección..."}
                </div>

                {/* Barra de confianza */}
                {confidence > 0 && (
                  <div className="confidence-section">
                    <div className="confidence-bar">
                      <div
                        className="confidence-fill"
                        style={{
                          width: `${confidence * 100}%`,
                          backgroundColor: getConfidenceColor(confidence),
                        }}
                      />
                    </div>
                    <span className="confidence-value">
                      {Math.round(confidence * 100)}% confianza
                    </span>
                  </div>
                )}

                {/* Estado de sesión */}
                {currentSession && (
                  <div className="session-info">
                    <div className="session-badge">
                      <div className="recording-indicator" />
                      <span>Sesión activa: #{currentSession}</span>
                    </div>
                  </div>
                )}

                {/* Info avanzada */}
                {showAdvancedInfo && (
                  <div className="advanced-info">
                    <h4>Métricas del Sistema</h4>
                    <div className="info-grid">
                      <div className="info-item">
                        <label>FPS:</label>
                        <span>{stats.fps?.toFixed(1) || "0"}</span>
                      </div>
                      <div className="info-item">
                        <label>Inferencia:</label>
                        <span>{stats.inference_time_ms?.toFixed(1)} ms</span>
                      </div>
                      <div className="info-item">
                        <label>CPU:</label>
                        <span>{stats.cpu?.toFixed(1) || "0"}%</span>
                      </div>
                      <div className="info-item">
                        <label>RAM:</label>
                        <span>{stats.ram?.toFixed(1) || "0"}%</span>
                      </div>
                      <div className="info-item">
                        <label>Buffer:</label>
                        <span>
                          {stats.buffer_current}/{stats.buffer_max}
                        </span>
                      </div>
                      {systemStatus?.model_info && (
                        <div className="info-item">
                          <label>Clases:</label>
                          <span>{systemStatus.model_info.classes}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* === CONTROLES === */}
        <div className="controls-section">
          <div className="video-controls">
            <button
              className={`control-btn ${isProcessing ? "stop" : "start"}`}
              onClick={isProcessing ? handleStopSession : handleStartSession}
              disabled={!isConnected}
              title={
                isProcessing
                  ? "Detener sesión de grabación"
                  : "Iniciar sesión de grabación"
              }
            >
              {isProcessing ? <Square size={16} /> : <Play size={16} />}
              {isProcessing ? "Detener Sesión" : "Iniciar Sesión"}
            </button>

            <button
              className="control-btn secondary"
              onClick={handleResetClassifier}
              disabled={!isConnected}
              title="Reiniciar buffer del clasificador"
            >
              <RotateCcw size={16} />
              Reiniciar
            </button>

            <button
              className="control-btn secondary"
              onClick={getStatus}
              disabled={!isConnected}
              title="Obtener estado del sistema"
            >
              <Activity size={16} />
              Estado
            </button>
          </div>
        </div>

        {/* === HISTORIAL === */}
        <div className="history-section">
          <div className="history-container">
            <div className="history-header">
              <h3>Historial de Traducciones</h3>
              <span className="history-count">
                {translationsHistory.length} registro
                {translationsHistory.length !== 1 ? "s" : ""}
              </span>
            </div>

            <div className="translations-list">
              {translationsHistory.length === 0 ? (
                <div className="empty-history">
                  <p>No hay traducciones recientes</p>
                  <span>Las señas detectadas aparecerán aquí</span>
                </div>
              ) : (
                translationsHistory.map((t, i) => (
                  <div key={`${t.timestamp}-${i}`} className="translation-item">
                    <div className="translation-main">
                      <span className="item-text">{t.text}</span>
                      <span
                        className="confidence-badge"
                        style={{
                          backgroundColor: getConfidenceColor(t.confidence),
                        }}
                      >
                        {Math.round(t.confidence * 100)}%
                      </span>
                    </div>
                    <div className="translation-meta">
                      <span className="timestamp">{t.timestamp}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Translation;